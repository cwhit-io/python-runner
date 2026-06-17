"""
Script execution service with virtual environment management.
"""

import os
import subprocess
import sys
import threading
import time
import hashlib
import json
import psutil
import signal
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional
from django.conf import settings
from django.utils import timezone
from app.models import Script, ScriptExecution, ScriptSchedule
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)


class ScriptRunner:
    """Manages script execution in isolated virtual environments."""

    def __init__(self, script: Script):
        self.script = script
        self.execution = None

    def _send_websocket_update(self, message_type, data):
        """Send WebSocket update for execution progress."""
        try:
            channel_layer = get_channel_layer()
            if channel_layer and self.execution:
                async_to_sync(channel_layer.group_send)(
                    f"execution_{self.execution.id}",
                    {
                        "type": "execution_update",
                        "message_type": message_type,
                        **data,
                    },
                )
        except Exception:
            # Silently ignore WebSocket errors
            pass

    def _clear_overdue_schedules(self):
        """Update next_run for overdue schedules after a successful execution."""
        try:
            # Import here to avoid circular import (scheduler imports script_runner)
            from app.services.scheduler import schedule_job

            now = timezone.now()
            # Get all active schedules for this script that are overdue
            overdue_schedules = self.script.schedules.filter(
                is_active=True, next_run__lt=now
            )

            for schedule in overdue_schedules:
                # Re-schedule the job to recalculate next_run
                try:
                    schedule_job(schedule)
                except Exception as e:
                    # Log but don't fail the execution if we can't reschedule
                    logger.warning(
                        f"Failed to reschedule overdue schedule {schedule.id}: {e}"
                    )
        except Exception:
            # Silently ignore errors in clearing overdue schedules
            pass

    def _calculate_dependencies_hash(self) -> str:
        """Calculate SHA-256 hash of dependencies string."""
        if not self.script.dependencies:
            return ""
        return hashlib.sha256(self.script.dependencies.encode("utf-8")).hexdigest()

    def _parse_dependencies(self) -> List[Dict[str, str]]:
        """Parse dependencies string into structured format."""
        deps = []
        if not self.script.dependencies:
            return deps

        for line in self.script.dependencies.strip().split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Parse package name and version spec
            # Handle formats like: package==1.0.0, package>=1.0.0, package
            if "==" in line:
                package, version = line.split("==", 1)
                deps.append(
                    {"name": package.strip(), "spec": "==", "version": version.strip()}
                )
            elif ">=" in line:
                package, version = line.split(">=", 1)
                deps.append(
                    {"name": package.strip(), "spec": ">=", "version": version.strip()}
                )
            elif "<=" in line:
                package, version = line.split("<=", 1)
                deps.append(
                    {"name": package.strip(), "spec": "<=", "version": version.strip()}
                )
            elif ">" in line:
                package, version = line.split(">", 1)
                deps.append(
                    {"name": package.strip(), "spec": ">", "version": version.strip()}
                )
            elif "<" in line:
                package, version = line.split("<", 1)
                deps.append(
                    {"name": package.strip(), "spec": "<", "version": version.strip()}
                )
            else:
                # Just package name
                deps.append({"name": line.strip(), "spec": "", "version": ""})

        return deps

    def _detect_dependency_conflicts(
        self, dependencies: List[Dict[str, str]]
    ) -> List[str]:
        """Detect potential dependency conflicts."""
        conflicts = []
        package_versions = {}

        # Group by package name
        for dep in dependencies:
            name = dep["name"].lower()
            if name not in package_versions:
                package_versions[name] = []
            package_versions[name].append(dep)

        # Check for conflicts within same package
        for name, deps in package_versions.items():
            if len(deps) > 1:
                specs = [
                    f"{dep['spec']}{dep['version']}" for dep in deps if dep["spec"]
                ]
                if len(set(specs)) > 1:
                    conflicts.append(
                        f"Package '{name}' has conflicting version specs: {', '.join(specs)}"
                    )

        return conflicts

    def _dependencies_changed(self) -> bool:
        """Check if dependencies have changed since last installation."""
        current_hash = self._calculate_dependencies_hash()
        return current_hash != self.script.dependencies_hash

    def ensure_venv(self):
        """Create or update virtual environment for the script."""
        venv_path = self.script.get_venv_path()

        # Create venv if it doesn't exist
        if not os.path.exists(venv_path):
            os.makedirs(os.path.dirname(venv_path), exist_ok=True)
            subprocess.run(
                [sys.executable, "-m", "venv", venv_path],
                check=True,
                capture_output=True,
            )
            self.script.venv_created = True
            self.script.venv_updated_at = timezone.now()
            self.script.save(update_fields=["venv_created", "venv_updated_at"])

        # Check and install/update dependencies if specified
        if self.script.dependencies:
            # Parse dependencies and check for conflicts
            parsed_deps = self._parse_dependencies()
            conflicts = self._detect_dependency_conflicts(parsed_deps)

            # Store conflicts in the script model
            self.script.dependency_conflicts = (
                json.dumps(conflicts) if conflicts else ""
            )

            # Only install if dependencies have changed
            if self._dependencies_changed():
                try:
                    self._install_dependencies(venv_path)
                    # Update hash after successful installation
                    self.script.dependencies_hash = self._calculate_dependencies_hash()
                    self.script.save(
                        update_fields=["dependencies_hash", "dependency_conflicts"]
                    )
                except Exception as e:
                    # Store installation error in conflicts
                    error_conflicts = conflicts + [f"Installation failed: {str(e)}"]
                    self.script.dependency_conflicts = json.dumps(error_conflicts)
                    self.script.save(update_fields=["dependency_conflicts"])
                    raise
            else:
                # Just save conflicts if they exist
                self.script.save(update_fields=["dependency_conflicts"])

    def _install_dependencies(self, venv_path):
        """Install dependencies in the virtual environment."""
        pip_path = os.path.join(venv_path, "bin", "pip")

        # Create a temporary requirements file
        requirements_file = os.path.join(venv_path, "requirements.txt")
        with open(requirements_file, "w") as f:
            f.write(self.script.dependencies)

        # Install dependencies
        subprocess.run(
            [pip_path, "install", "-r", requirements_file],
            check=True,
            capture_output=True,
            text=True,
        )

        self.script.venv_updated_at = timezone.now()
        self.script.save(update_fields=["venv_updated_at"])

    def execute(
        self,
        triggered_by=None,
        trigger_type="manual",
        timeout_seconds=None,
        input_text: Optional[str] = None,
    ):
        """
        Execute the script in its environment (virtual environment for Python, system for bash).
        Returns the ScriptExecution object.

        Args:
            triggered_by: User who triggered the execution
            trigger_type: How the execution was triggered (manual, scheduled, api)
            timeout_seconds: Maximum execution time in seconds (None for no timeout)
            input_text: Optional text to send to the script via stdin
        """
        self.input_text = input_text

        # Ensure environment is ready (venv for Python, skip for bash)
        if self.script.language == "python":
            try:
                self.ensure_venv()
            except Exception as e:
                # Create failed execution record
                execution = ScriptExecution.objects.create(
                    script=self.script,
                    triggered_by=triggered_by,
                    trigger_type=trigger_type,
                    status="failed",
                    error_message=f"Failed to create/update virtual environment: {str(e)}",
                )
                return execution

        # Create execution record
        self.execution = ScriptExecution.objects.create(
            script=self.script,
            triggered_by=triggered_by,
            trigger_type=trigger_type,
            status="running",
            started_at=timezone.now(),
            timeout_seconds=timeout_seconds,
        )

        # Update script status
        self.script.last_status = "running"
        self.script.save(update_fields=["last_status"])

        # Run script in a separate thread to not block
        thread = threading.Thread(target=self._run_script)
        thread.daemon = True
        thread.start()

        return self.execution

    def _run_script(self):
        """Run the script in a separate thread."""
        try:
            # Determine execution command based on script language
            if self.script.language == "bash":
                # For bash scripts, run the executable script directly
                script_file = self._create_script_file(".sh")
                cmd = [script_file]
                env = os.environ.copy()
            else:
                # For Python scripts, use virtual environment
                python_path = self.script.get_python_executable()
                script_file = self._create_script_file(".py")
                cmd = [python_path, "-u", script_file]  # -u flag for unbuffered
                env = os.environ.copy()
                env["PYTHONUNBUFFERED"] = "1"  # Force Python to use unbuffered output

            # Load script-specific secrets into the environment
            from app.services.secret_store import list_script_secrets, get_script_secret, get_all_credentials_for_script
            try:
                for name in list_script_secrets(self.script.id):
                    value = get_script_secret(self.script.id, name)
                    if value is not None:
                        env[name] = value
            except Exception:
                # Silently ignore if secrets can't be loaded (e.g., key issues)
                pass
            
            # Load global credentials into the environment
            try:
                credentials_data = get_all_credentials_for_script(self.script.id)
                for cred_name, cred_data in credentials_data.items():
                    # For each credential, inject its values into the environment
                    # Using credential name as prefix to avoid conflicts
                    if isinstance(cred_data, dict):
                        for key, value in cred_data.items():
                            if value is not None:
                                # Convert to string and use uppercase key with prefix
                                env_key = f"{cred_name}_{key}".upper()
                                env[env_key] = str(value)
                                # Also set without prefix for convenience
                                env[key.upper()] = str(value)
                    else:
                        env[cred_name.upper()] = str(cred_data)
            except Exception:
                # Silently ignore credential loading errors
                pass

            # Run the script
            start_time = time.time()
            stdin_pipe = subprocess.PIPE if getattr(self, "input_text", None) is not None else None
            process = subprocess.Popen(
                cmd,
                stdin=stdin_pipe,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,  # Line buffered
                universal_newlines=True,
                env=env,
            )

            # Feed input to the process if provided
            if getattr(self, "input_text", None) is not None and process.stdin:
                try:
                    process.stdin.write(self.input_text)
                    process.stdin.close()
                except Exception:
                    pass

            # Store process ID
            self.execution.process_id = process.pid
            self.execution.save(update_fields=["process_id"])

            # Send start notification
            self._send_websocket_update(
                "started",
                {
                    "process_id": process.pid,
                    "started_at": self.execution.started_at.isoformat()
                    if self.execution.started_at
                    else None,
                },
            )

            # Collect stdout/stderr in real-time
            stdout_lines = []
            stderr_lines = []

            def read_stdout():
                """Read stdout in real-time and send updates."""
                for line in iter(process.stdout.readline, ""):
                    if line:
                        stdout_lines.append(line)
                        # Update execution stdout in DB periodically
                        self.execution.stdout = "".join(stdout_lines)
                        self.execution.save(update_fields=["stdout"])
                        self._send_websocket_update(
                            "output", {"stream": "stdout", "line": line.rstrip("\n")}
                        )
                process.stdout.close()

            def read_stderr():
                """Read stderr in real-time and send updates."""
                for line in iter(process.stderr.readline, ""):
                    if line:
                        stderr_lines.append(line)
                        # Update execution stderr in DB periodically
                        self.execution.stderr = "".join(stderr_lines)
                        self.execution.save(update_fields=["stderr"])
                        self._send_websocket_update(
                            "output", {"stream": "stderr", "line": line.rstrip("\n")}
                        )
                process.stderr.close()

            # Start stdout/stderr reader threads
            stdout_thread = threading.Thread(target=read_stdout)
            stderr_thread = threading.Thread(target=read_stderr)
            stdout_thread.daemon = True
            stderr_thread.daemon = True
            stdout_thread.start()
            stderr_thread.start()

            # Monitor resource usage in parallel
            psutil_process = psutil.Process(process.pid)
            monitor_thread = threading.Thread(
                target=lambda: setattr(
                    self,
                    "_resource_stats",
                    self._monitor_process(psutil_process, start_time),
                )
            )
            monitor_thread.daemon = True
            monitor_thread.start()

            # Wait for completion
            process.wait()
            end_time = time.time()

            # Wait for output threads to finish
            stdout_thread.join(timeout=1.0)
            stderr_thread.join(timeout=1.0)

            # Wait for monitoring thread to finish
            monitor_thread.join(timeout=1.0)
            peak_cpu, peak_memory = getattr(self, "_resource_stats", (0.0, 0.0))

            # Combine all output lines
            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)

            # Update execution record
            self.execution.stdout = stdout
            self.execution.stderr = stderr
            self.execution.exit_code = process.returncode
            self.execution.completed_at = timezone.now()
            self.execution.duration_seconds = end_time - start_time
            self.execution.peak_cpu_percent = peak_cpu
            self.execution.peak_memory_mb = peak_memory

            # Determine status
            if self.execution.timed_out:
                self.execution.status = "cancelled"
            else:
                self.execution.status = (
                    "success" if process.returncode == 0 else "failed"
                )

            self.execution.save()

            # Send completion notification
            duration = self.execution.duration_seconds
            self._send_websocket_update(
                "completed",
                {
                    "status": self.execution.status,
                    "exit_code": process.returncode,
                    "duration_seconds": round(duration, 2) if duration is not None else None,
                    "peak_cpu_percent": round(peak_cpu, 2),
                    "peak_memory_mb": round(peak_memory, 2),
                },
            )

            # Update script status
            self.script.last_status = self.execution.status
            self.script.last_run = timezone.now()
            self.script.execution_count += 1
            if process.returncode == 0 and not self.execution.timed_out:
                self.script.last_success = timezone.now()
            self.script.save(
                update_fields=[
                    "last_status",
                    "last_run",
                    "execution_count",
                    "last_success",
                ]
            )

            # Clear overdue schedules on successful run
            if process.returncode == 0 and not self.execution.timed_out:
                self._clear_overdue_schedules()

        except Exception as e:
            # Handle execution errors
            self.execution.status = "failed"
            self.execution.error_message = str(e)
            self.execution.completed_at = timezone.now()
            self.execution.save()

            self._send_websocket_update("error", {"error_message": str(e)})

            self.script.last_status = "failed"
            self.script.last_run = timezone.now()
            self.script.save(update_fields=["last_status", "last_run"])

        finally:
            # Clean up script file
            if os.path.exists(script_file):
                os.remove(script_file)

    def _create_script_file(self, extension):
        """Create a temporary script file for execution."""
        # For bash scripts, use system temp directory
        if self.script.language == "bash":
            tmp_dir = "/tmp"
        else:
            # For Python scripts, use venv tmp directory
            venv_path = self.script.get_venv_path()
            tmp_dir = os.path.join(venv_path, "tmp")
            os.makedirs(tmp_dir, exist_ok=True)

        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
        exec_id = getattr(self.execution, "id", None) or "unknown"
        script_file = os.path.join(tmp_dir, f"script_{exec_id}_{ts}{extension}")

        # Normalize line endings for bash scripts to avoid carriage return issues
        code = self.script.code
        if self.script.language == "bash":
            # Convert CRLF to LF for bash scripts
            code = code.replace("\r\n", "\n").replace("\r", "\n")

            # Ensure proper shebang if not present
            if not code.startswith("#!"):
                code = "#!/bin/bash\n" + code
            else:
                # Fix shebang line if it has carriage returns
                lines = code.split("\n")
                lines[0] = lines[0].replace("\r", "")
                code = "\n".join(lines)

        # Write with binary mode to ensure Unix line endings
        with open(script_file, "wb") as f:
            f.write(code.encode("utf-8"))

        # Make bash scripts executable
        if self.script.language == "bash":
            os.chmod(script_file, 0o755)

        return script_file

    def _monitor_process(
        self, process: psutil.Process, start_time: float
    ) -> Tuple[float, float]:
        """
        Monitor process resource usage.
        Returns (peak_cpu_percent, peak_memory_mb).
        """
        peak_cpu = 0.0
        peak_memory = 0.0
        timeout = self.execution.timeout_seconds

        # Initialize CPU monitoring (first call returns 0)
        try:
            process.cpu_percent()
        except:
            pass

        try:
            while process.is_running() and process.status() != psutil.STATUS_ZOMBIE:
                try:
                    # Get resource usage including children
                    cpu_percent = process.cpu_percent(interval=0.5)

                    # Get memory including all children
                    memory_mb = process.memory_info().rss / (1024 * 1024)
                    try:
                        for child in process.children(recursive=True):
                            try:
                                memory_mb += child.memory_info().rss / (1024 * 1024)
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                pass
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                    peak_cpu = max(peak_cpu, cpu_percent)
                    peak_memory = max(peak_memory, memory_mb)

                    # Check timeout
                    if timeout and (time.time() - start_time) > timeout:
                        # Kill the process
                        process.terminate()
                        time.sleep(0.5)
                        if process.is_running():
                            process.kill()

                        # Mark as timed out
                        self.execution.timed_out = True
                        self.execution.error_message = (
                            f"Execution timed out after {timeout} seconds"
                        )
                        self.execution.save(
                            update_fields=["timed_out", "error_message"]
                        )

                        self._send_websocket_update(
                            "timeout",
                            {
                                "timeout_seconds": timeout,
                                "elapsed_seconds": time.time() - start_time,
                            },
                        )
                        break

                    # Send periodic resource updates
                    self._send_websocket_update(
                        "resource_update",
                        {
                            "cpu_percent": round(cpu_percent, 2),
                            "memory_mb": round(memory_mb, 2),
                            "elapsed_seconds": round(time.time() - start_time, 2),
                        },
                    )

                    # cpu_percent(interval=0.5) already sleeps, no additional sleep needed

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break
        except Exception as e:
            print(f"Error monitoring process: {e}")

        return peak_cpu, peak_memory


def execute_script(
    script_id, triggered_by=None, trigger_type="manual", timeout_seconds=None
):
    """
    Convenience function to execute a script by ID.

    Args:
        script_id: ID of the script to execute
        triggered_by: User who triggered the execution
        trigger_type: How the execution was triggered (manual, scheduled, api)
        timeout_seconds: Maximum execution time in seconds (None for no timeout)
    """
    try:
        script = Script.objects.get(id=script_id)
        runner = ScriptRunner(script)
        return runner.execute(
            triggered_by=triggered_by,
            trigger_type=trigger_type,
            timeout_seconds=timeout_seconds,
        )
    except Script.DoesNotExist:
        return None


def kill_execution(execution_id: int) -> bool:
    """
    Kill a running script execution.

    Args:
        execution_id: ID of the execution to kill

    Returns:
        True if execution was killed, False otherwise
    """
    try:
        execution = ScriptExecution.objects.get(id=execution_id)

        if execution.status != "running" or not execution.process_id:
            return False

        try:
            # Try to kill the process
            process = psutil.Process(execution.process_id)
            process.terminate()  # Try graceful termination first

            # Wait a bit for graceful shutdown
            time.sleep(0.5)

            if process.is_running():
                process.kill()  # Force kill if still running

            # Update execution status
            execution.status = "cancelled"
            execution.completed_at = timezone.now()
            execution.error_message = "Execution was manually cancelled"
            if execution.started_at:
                execution.duration_seconds = (
                    execution.completed_at - execution.started_at
                ).total_seconds()
            execution.save()

            # Send WebSocket update
            try:
                channel_layer = get_channel_layer()
                if channel_layer:
                    async_to_sync(channel_layer.group_send)(
                        f"execution_{execution_id}",
                        {
                            "type": "execution_update",
                            "message_type": "cancelled",
                            "execution_id": execution_id,
                            "status": "cancelled",
                        },
                    )
            except Exception:
                pass

            return True

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            # Process doesn't exist or can't be accessed
            execution.status = "failed"
            execution.completed_at = timezone.now()
            execution.error_message = f"Failed to kill process: {str(e)}"
            execution.save()
            return False

    except ScriptExecution.DoesNotExist:
        return False
