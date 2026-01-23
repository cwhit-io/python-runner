"""
Script execution service with virtual environment management.
"""
import os
import subprocess
import sys
import threading
import time
from datetime import datetime
from django.conf import settings
from django.utils import timezone
from app.models import Script, ScriptExecution


class ScriptRunner:
    """Manages script execution in isolated virtual environments."""
    
    def __init__(self, script: Script):
        self.script = script
        self.execution = None
    
    def ensure_venv(self):
        """Create or update virtual environment for the script."""
        venv_path = self.script.get_venv_path()
        
        # Create venv if it doesn't exist
        if not os.path.exists(venv_path):
            os.makedirs(os.path.dirname(venv_path), exist_ok=True)
            subprocess.run(
                [sys.executable, '-m', 'venv', venv_path],
                check=True,
                capture_output=True
            )
            self.script.venv_created = True
            self.script.venv_updated_at = timezone.now()
            self.script.save(update_fields=['venv_created', 'venv_updated_at'])
        
        # Install/update dependencies if specified
        if self.script.dependencies:
            self._install_dependencies(venv_path)
    
    def _install_dependencies(self, venv_path):
        """Install dependencies in the virtual environment."""
        pip_path = os.path.join(venv_path, 'bin', 'pip')
        
        # Create a temporary requirements file
        requirements_file = os.path.join(venv_path, 'requirements.txt')
        with open(requirements_file, 'w') as f:
            f.write(self.script.dependencies)
        
        # Install dependencies
        subprocess.run(
            [pip_path, 'install', '-r', requirements_file],
            check=True,
            capture_output=True,
            text=True
        )
        
        self.script.venv_updated_at = timezone.now()
        self.script.save(update_fields=['venv_updated_at'])
    
    def execute(self, triggered_by=None, trigger_type='manual'):
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
                status='failed',
                error_message=f"Failed to create/update virtual environment: {str(e)}"
            )
            return execution
        
        # Create execution record
        self.execution = ScriptExecution.objects.create(
            script=self.script,
            triggered_by=triggered_by,
            trigger_type=trigger_type,
            status='running',
            started_at=timezone.now()
        )
        
        # Update script status
        self.script.last_status = 'running'
        self.script.save(update_fields=['last_status'])
        
        # Run script in a separate thread to not block
        thread = threading.Thread(target=self._run_script)
        thread.daemon = True
        thread.start()
        
        return self.execution
    
    def _run_script(self):
        """Internal method to run the script (called in thread)."""
        python_path = self.script.get_python_executable()
        
        # Create a temporary script file
        script_file = os.path.join(self.script.get_venv_path(), 'script.py')
        with open(script_file, 'w') as f:
            f.write(self.script.code)
        
        try:
            # Run the script
            start_time = time.time()
            process = subprocess.Popen(
                [python_path, script_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Store process ID
            self.execution.process_id = process.pid
            self.execution.save(update_fields=['process_id'])
            
            # Wait for completion and capture output
            stdout, stderr = process.communicate()
            end_time = time.time()
            
            # Update execution record
            self.execution.stdout = stdout
            self.execution.stderr = stderr
            self.execution.exit_code = process.returncode
            self.execution.completed_at = timezone.now()
            self.execution.duration_seconds = end_time - start_time
            self.execution.status = 'success' if process.returncode == 0 else 'failed'
            self.execution.save()
            
            # Update script status
            self.script.last_status = self.execution.status
            self.script.last_run = timezone.now()
            self.script.execution_count += 1
            if process.returncode == 0:
                self.script.last_success = timezone.now()
            self.script.save(update_fields=['last_status', 'last_run', 'execution_count', 'last_success'])
            
        except Exception as e:
            # Handle execution errors
            self.execution.status = 'failed'
            self.execution.error_message = str(e)
            self.execution.completed_at = timezone.now()
            self.execution.save()
            
            self.script.last_status = 'failed'
            self.script.last_run = timezone.now()
            self.script.save(update_fields=['last_status', 'last_run'])
        
        finally:
            # Clean up script file
            if os.path.exists(script_file):
                os.remove(script_file)


def execute_script(script_id, triggered_by=None, trigger_type='manual'):
    """
    Convenience function to execute a script by ID.
    """
    try:
        script = Script.objects.get(id=script_id)
        runner = ScriptRunner(script)
        return runner.execute(triggered_by=triggered_by, trigger_type=trigger_type)
    except Script.DoesNotExist:
        return None
