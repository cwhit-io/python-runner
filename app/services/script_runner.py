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
from datetime import datetime
from typing import List, Dict, Tuple
from django.conf import settings
from django.utils import timezone
from app.models import Script, ScriptExecution


class ScriptRunner:
    """Manages script execution in isolated virtual environments."""

    def __init__(self, script: Script):
        self.script = script
        self.execution = None

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

    def execute(self, triggered_by=None, trigger_type="manual"):
        """
        Execute the script in its virtual environment.
        Returns the ScriptExecution object.
        """
        # Ensure venv is ready
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
        """Internal method to run the script (called in thread)."""
        python_path = self.script.get_python_executable()

        # Create a per-execution script file to avoid collisions during concurrent runs
        venv_path = self.script.get_venv_path()
        tmp_dir = os.path.join(venv_path, "tmp")
        os.makedirs(tmp_dir, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%fZ")
        exec_id = getattr(self.execution, "id", None) or "unknown"
        script_file = os.path.join(tmp_dir, f"script_{exec_id}_{ts}.py")
        with open(script_file, "w") as f:
            f.write(self.script.code)

        try:
            # Run the script
            start_time = time.time()
            process = subprocess.Popen(
                [python_path, script_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            # Store process ID
            self.execution.process_id = process.pid
            self.execution.save(update_fields=["process_id"])

            # Wait for completion and capture output
            stdout, stderr = process.communicate()
            end_time = time.time()

            # Update execution record
            self.execution.stdout = stdout
            self.execution.stderr = stderr
            self.execution.exit_code = process.returncode
            self.execution.completed_at = timezone.now()
            self.execution.duration_seconds = end_time - start_time
            self.execution.status = "success" if process.returncode == 0 else "failed"
            self.execution.save()

            # Update script status
            self.script.last_status = self.execution.status
            self.script.last_run = timezone.now()
            self.script.execution_count += 1
            if process.returncode == 0:
                self.script.last_success = timezone.now()
            self.script.save(
                update_fields=[
                    "last_status",
                    "last_run",
                    "execution_count",
                    "last_success",
                ]
            )

        except Exception as e:
            # Handle execution errors
            self.execution.status = "failed"
            self.execution.error_message = str(e)
            self.execution.completed_at = timezone.now()
            self.execution.save()

            self.script.last_status = "failed"
            self.script.last_run = timezone.now()
            self.script.save(update_fields=["last_status", "last_run"])

        finally:
            # Clean up script file
            if os.path.exists(script_file):
                os.remove(script_file)


def execute_script(script_id, triggered_by=None, trigger_type="manual"):
    """
    Convenience function to execute a script by ID.
    """
    try:
        script = Script.objects.get(id=script_id)
        runner = ScriptRunner(script)
        return runner.execute(triggered_by=triggered_by, trigger_type=trigger_type)
    except Script.DoesNotExist:
        return None
