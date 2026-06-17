from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
import secrets
import os
import shutil
import json
from cryptography.fernet import Fernet, InvalidToken


# Global Credential Types
class CredentialType(models.TextChoices):
    API_KEY = "api_key", "API Key"
    BEARER_TOKEN = "bearer_token", "Bearer Token"
    BASIC_AUTH = "basic_auth", "Basic Auth"
    OAUTH_CLIENT_CREDENTIALS = "oauth_client_credentials", "OAuth Client Credentials"
    GENERIC = "generic", "Generic Key/Value"


class GlobalCredential(models.Model):
    """Global credentials that can be attached to scripts for secure reuse.
    
    Secret values are encrypted and never returned to the frontend after save.
    Credentials can be referenced by scripts during execution.
    """
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="credentials"
    )
    name = models.CharField(max_length=100, help_text="Descriptive name for this credential")
    credential_type = models.CharField(
        max_length=30,
        choices=CredentialType.choices,
        default=CredentialType.GENERIC,
    )
    
    # Encrypted JSON storage for credential data
    encrypted_data = models.TextField(
        help_text="Encrypted credential data (JSON)"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Global Credential"
        verbose_name_plural = "Global Credentials"
        indexes = [
            models.Index(fields=["user", "-updated_at"]),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.name}"
    
    def get_masked_value(self) -> str:
        """Return a masked representation of the credential value for UI display."""
        return "••••••••••••••••••••••••••••••••••••••••••••••••••"
    
    def get_decrypted_data(self) -> dict:
        """Decrypt and return the credential data. Returns empty dict if decryption fails."""
        from app.services.secret_store import get_master_key
        key = get_master_key()
        if not key:
            return {}
        
        try:
            fernet = Fernet(key)
            decrypted = fernet.decrypt(self.encrypted_data.encode())
            return json.loads(decrypted.decode())
        except (InvalidToken, json.JSONDecodeError):
            return {}
    
    def set_encrypted_data(self, data: dict) -> None:
        """Encrypt and store the credential data."""
        from app.services.secret_store import get_master_key
        key = get_master_key()
        if not key:
            raise RuntimeError("Master encryption key not available")
        
        fernet = Fernet(key)
        encrypted = fernet.encrypt(json.dumps(data).encode())
        self.encrypted_data = encrypted.decode()


class UserProfile(models.Model):
    """Extended user profile with avatar and verification."""

    THEME_CHOICES = [
        ("light", "Light"),
        ("dark", "Dark"),
        ("cupcake", "Cupcake"),
        ("bumblebee", "Bumblebee"),
        ("emerald", "Emerald"),
        ("corporate", "Corporate"),
        ("synthwave", "Synthwave"),
        ("retro", "Retro"),
        ("cyberpunk", "Cyberpunk"),
        ("valentine", "Valentine"),
        ("halloween", "Halloween"),
        ("garden", "Garden"),
        ("forest", "Forest"),
        ("aqua", "Aqua"),
        ("lofi", "Lofi"),
        ("pastel", "Pastel"),
        ("fantasy", "Fantasy"),
        ("wireframe", "Wireframe"),
        ("black", "Black"),
        ("luxury", "Luxury"),
        ("dracula", "Dracula"),
        ("cmyk", "CMYK"),
        ("autumn", "Autumn"),
        ("business", "Business"),
        ("acid", "Acid"),
        ("lemonade", "Lemonade"),
        ("night", "Night"),
        ("coffee", "Coffee"),
        ("winter", "Winter"),
    ]

    TIMEZONE_CHOICES = [
        ("UTC", "UTC"),
        ("America/New_York", "Eastern Time (ET)"),
        ("America/Chicago", "Central Time (CT)"),
        ("America/Denver", "Mountain Time (MT)"),
        ("America/Los_Angeles", "Pacific Time (PT)"),
        ("America/Anchorage", "Alaska Time (AKT)"),
        ("Pacific/Honolulu", "Hawaii Time (HT)"),
        ("Europe/London", "London (GMT/BST)"),
        ("Europe/Paris", "Paris (CET/CEST)"),
        ("Europe/Berlin", "Berlin (CET/CEST)"),
        ("Europe/Rome", "Rome (CET/CEST)"),
        ("Europe/Madrid", "Madrid (CET/CEST)"),
        ("Asia/Tokyo", "Tokyo (JST)"),
        ("Asia/Shanghai", "Shanghai (CST)"),
        ("Asia/Kolkata", "India (IST)"),
        ("Asia/Dubai", "Dubai (GST)"),
        ("Australia/Sydney", "Sydney (AEST/AEDT)"),
        ("Australia/Melbourne", "Melbourne (AEST/AEDT)"),
        ("Pacific/Auckland", "Auckland (NZST/NZDT)"),
    ]

    TIME_FORMAT_CHOICES = [
        ("12", "12-hour (AM/PM)"),
        ("24", "24-hour"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True)
    theme_preference = models.CharField(
        max_length=20, choices=THEME_CHOICES, default="light"
    )
    timezone = models.CharField(max_length=50, choices=TIMEZONE_CHOICES, default="UTC")
    time_format = models.CharField(
        max_length=2, choices=TIME_FORMAT_CHOICES, default="24"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def send_verification_email(self, request):
        """Send email verification link."""
        if not self.email_verification_token:
            self.email_verification_token = secrets.token_urlsafe(32)
            self.save()

        verification_url = request.build_absolute_uri(
            f"/verify-email/{self.email_verification_token}/"
        )

        send_mail(
            "Verify your email address",
            f"Click the link to verify your email: {verification_url}",
            "noreply@mysite.com",
            [self.user.email],
            fail_silently=False,
        )


class APIToken(models.Model):
    """API authentication tokens for users."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="api_tokens")
    token = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=100, help_text="Token description/name")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "API Token"
        verbose_name_plural = "API Tokens"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.name}"

    @classmethod
    def generate_token(cls):
        """Generate a secure random token."""
        return secrets.token_urlsafe(48)

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self.generate_token()
        super().save(*args, **kwargs)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create profile when user is created."""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save profile when user is saved."""
    if hasattr(instance, "profile"):
        instance.profile.save()


class APILog(models.Model):
    """Model to store API request logs."""

    # Request information
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    full_path = models.CharField(max_length=1000, blank=True)

    # User information
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="api_logs"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)

    # Request details
    query_params = models.TextField(blank=True)
    request_body = models.TextField(blank=True)

    # Response information
    status_code = models.IntegerField(null=True, blank=True)
    response_body = models.TextField(blank=True)

    # Performance metrics
    duration_ms = models.FloatField(
        null=True, blank=True, help_text="Request duration in milliseconds"
    )

    # Error tracking
    error = models.TextField(blank=True)

    # Timestamps
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "API Log"
        verbose_name_plural = "API Logs"
        indexes = [
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["method", "-timestamp"]),
            models.Index(fields=["status_code", "-timestamp"]),
            models.Index(fields=["user", "-timestamp"]),
        ]

    def __str__(self):
        return f"{self.method} {self.path} - {self.status_code} ({self.timestamp})"

    @property
    def is_error(self):
        """Check if the request resulted in an error."""
        return self.status_code >= 400 if self.status_code else False

    @property
    def duration_seconds(self):
        """Get duration in seconds."""
        return self.duration_ms / 1000 if self.duration_ms else None


class Script(models.Model):
    """Script model supporting multiple languages."""

    LANGUAGE_CHOICES = [
        ("python", "Python"),
        ("bash", "Bash"),
        ("http", "HTTP Request"),
    ]

    STATUS_CHOICES = [
        ("idle", "Idle"),
        ("running", "Running"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    language = models.CharField(
        max_length=20,
        choices=LANGUAGE_CHOICES,
        default="python",
        help_text="Script language/runtime",
    )
    code = models.TextField(
        default='# Write your Python script here\nprint("Hello, World!")'
    )
    dependencies = models.TextField(
        blank=True, help_text="One package per line (e.g., 'requests==2.28.0')"
    )

    # Virtual environment
    venv_path = models.CharField(max_length=500, blank=True)
    venv_created = models.BooleanField(default=False)
    venv_updated_at = models.DateTimeField(null=True, blank=True)

    # Dependency management
    dependencies_hash = models.CharField(
        max_length=64,
        blank=True,
        help_text="SHA-256 hash of dependencies for change detection",
    )
    dependency_conflicts = models.TextField(
        blank=True, help_text="JSON list of detected dependency conflicts"
    )

    # Ownership and permissions
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scripts")
    is_public = models.BooleanField(
        default=False, help_text="Allow other users to view/run"
    )
    expose_to_mcp = models.BooleanField(
        default=False,
        help_text="Make this script available as a tool through the MCP server",
    )
    mcp_tool_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Custom name for the MCP tool (lowercase snake_case, auto-generated from script name if empty)",
    )
    input_schema = models.JSONField(
        blank=True,
        null=True,
        help_text="JSON schema for script input parameters (auto-generated if empty)",
    )
    is_destructive = models.BooleanField(
        default=False,
        help_text="Mark this script as destructive/making changes (for safety warnings)",
    )
    credentials = models.ManyToManyField(
        GlobalCredential,
        blank=True,
        related_name="scripts",
        help_text="Global credentials to attach to this script",
    )
    tags = models.ManyToManyField(
        "Tag",
        blank=True,
        related_name="scripts",
        help_text="Tags for categorizing this script",
    )

    # Status
    last_status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="idle"
    )
    last_run = models.DateTimeField(null=True, blank=True)
    last_success = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    execution_count = models.IntegerField(default=0)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Script"
        verbose_name_plural = "Scripts"
        indexes = [
            models.Index(fields=["owner", "-updated_at"]),
            models.Index(fields=["last_status"]),
        ]

    def __str__(self):
        return self.name

    def get_venv_path(self):
        """Get the virtual environment path for this script."""
        if not self.venv_path:
            # Store venvs in media/venvs/{script_id}
            from django.conf import settings

            venv_dir = os.path.join(settings.MEDIA_ROOT, "venvs", str(self.id))
            self.venv_path = venv_dir
            self.save(update_fields=["venv_path"])
        return self.venv_path

    def get_python_executable(self):
        """Get the Python executable path in the venv."""
        venv_path = self.get_venv_path()
        return os.path.join(venv_path, "bin", "python")

    @property
    def has_dependency_conflicts(self):
        """Check if the script has dependency conflicts."""
        return bool(self.dependency_conflicts)

    @property
    def dependency_conflicts_list(self):
        """Get dependency conflicts as a list."""
        if not self.dependency_conflicts:
            return []
        try:
            return json.loads(self.dependency_conflicts)
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def next_run(self):
        """Get the next scheduled run time for this script."""
        active_schedules = self.schedules.filter(is_active=True)
        if not active_schedules.exists():
            return None

        # Get the earliest next_run from active schedules
        next_runs = []
        for schedule in active_schedules:
            if schedule.next_run:
                next_runs.append(schedule.next_run)

        return min(next_runs) if next_runs else None

    @property
    def has_overdue_schedules(self):
        """Check if this script has any schedules that should have run but haven't."""
        from django.utils import timezone

        now = timezone.now()

        active_schedules = self.schedules.filter(is_active=True)
        for schedule in active_schedules:
            if schedule.next_run and schedule.next_run < now:
                return True
        return False

    def save(self, *args, **kwargs):
        # Automatically add requests dependency for HTTP scripts
        if self.language == "http":
            deps = self.dependencies.strip() if self.dependencies else ""
            deps_list = [d.strip() for d in deps.split("\n") if d.strip()]

            # Check if requests is already in dependencies
            has_requests = any(d.lower().startswith("requests") for d in deps_list)

            if not has_requests:
                deps_list.append("requests")
                self.dependencies = "\n".join(deps_list)

        super().save(*args, **kwargs)

        # Create venv in background thread to avoid blocking save operation
        if self.language in ("python", "http"):
            import threading
            from app.services.script_runner import ScriptRunner

            def create_venv():
                try:
                    runner = ScriptRunner(self)
                    runner.ensure_venv()
                except Exception as e:
                    import logging

                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to create venv for script {self.id}: {e}")

            thread = threading.Thread(target=create_venv, daemon=True)
            thread.start()


@receiver(models.signals.post_delete, sender=Script)
def cleanup_script_venv(sender, instance: Script, **kwargs):
    """Remove the script's virtual environment directory when the script is deleted."""
    try:
        from django.conf import settings

        venv_base = os.path.realpath(os.path.join(settings.MEDIA_ROOT, "venvs"))

        candidate_paths = []
        if instance.venv_path:
            candidate_paths.append(instance.venv_path)
        candidate_paths.append(
            os.path.join(settings.MEDIA_ROOT, "venvs", str(instance.id))
        )

        for candidate in candidate_paths:
            if not candidate:
                continue

            real_candidate = os.path.realpath(candidate)
            if not (
                real_candidate == venv_base
                or real_candidate.startswith(venv_base + os.sep)
            ):
                continue

            if os.path.isdir(real_candidate):
                shutil.rmtree(real_candidate, ignore_errors=True)
    except Exception:
        # Never block deletion if cleanup fails.
        return


class ScriptExecution(models.Model):
    """Execution history for scripts."""

    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    script = models.ForeignKey(
        Script, on_delete=models.CASCADE, related_name="executions"
    )
    triggered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_executions",
    )

    # Execution details
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="queued")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.FloatField(null=True, blank=True)

    # Output
    stdout = models.TextField(blank=True)
    stderr = models.TextField(blank=True)
    exit_code = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    # Process info
    process_id = models.IntegerField(null=True, blank=True)

    # Snapshot of the code that was executed (for historical accuracy)
    code_snapshot = models.TextField(
        blank=True,
        help_text="Snapshot of script code at time of execution",
    )
    dependencies_snapshot = models.TextField(
        blank=True,
        help_text="Snapshot of script dependencies at time of execution",
    )

    # Resource monitoring
    peak_cpu_percent = models.FloatField(
        null=True, blank=True, help_text="Peak CPU usage percentage"
    )
    peak_memory_mb = models.FloatField(
        null=True, blank=True, help_text="Peak memory usage in MB"
    )
    timeout_seconds = models.IntegerField(
        null=True, blank=True, help_text="Execution timeout in seconds"
    )
    timed_out = models.BooleanField(
        default=False, help_text="Whether execution was terminated due to timeout"
    )

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    trigger_type = models.CharField(
        max_length=20,
        choices=[
            ("manual", "Manual"),
            ("scheduled", "Scheduled"),
            ("api", "API"),
            ("mcp", "MCP"),
            ("test", "Test"),
        ],
        default="manual",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Script Execution"
        verbose_name_plural = "Script Executions"
        indexes = [
            models.Index(fields=["script", "-created_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.script.name} - {self.status} ({self.created_at})"

    @property
    def is_running(self):
        """Check if execution is currently running."""
        return self.status == "running"

    @property
    def is_complete(self):
        """Check if execution is complete."""
        return self.status in ["success", "failed", "cancelled"]


class ScriptSchedule(models.Model):
    """Scheduled execution for scripts."""

    script = models.ForeignKey(
        Script, on_delete=models.CASCADE, related_name="schedules"
    )

    # Schedule configuration
    name = models.CharField(max_length=200)
    cron_expression = models.CharField(
        max_length=100,
        help_text="Cron expression (e.g., '0 */6 * * *' for every 6 hours)",
        blank=True,
        default="",
    )
    # Support scheduling: 'cron', 'single' (one-time), 'interval' (repeating)
    SCHEDULE_TYPE_CHOICES = [
        ("cron", "Cron"),
        ("single", "Single datetime"),
        ("interval", "Interval (repeating)"),
    ]
    schedule_type = models.CharField(
        max_length=20, choices=SCHEDULE_TYPE_CHOICES, default="single"
    )
    # For single/interval schedules, store the start datetime
    start_datetime = models.DateTimeField(null=True, blank=True)
    # For interval schedules
    INTERVAL_UNIT_CHOICES = [
        ("hours", "Hourly"),
        ("days", "Daily"),
        ("weeks", "Weekly"),
        ("months", "Monthly"),
    ]
    interval_unit = models.CharField(
        max_length=10, choices=INTERVAL_UNIT_CHOICES, blank=True, default=""
    )
    interval_value = models.IntegerField(
        default=1, help_text="How many units between runs"
    )
    timezone = models.CharField(max_length=50, default="UTC")

    # Status
    is_active = models.BooleanField(default=True)
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="created_schedules"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Script Schedule"
        verbose_name_plural = "Script Schedules"

    def __str__(self):
        return f"{self.script.name} - {self.name}"


class Tag(models.Model):
    """Tag model for categorizing scripts."""

    name = models.CharField(max_length=50, unique=True)
    color = models.CharField(
        max_length=7,
        default="#3B82F6",
        help_text="Hex color code for the tag (e.g., #3B82F6)",
    )
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="created_tags"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Tag"
        verbose_name_plural = "Tags"

    def __str__(self):
        return self.name

    def clean(self):
        """Validate color format."""
        import re

        if not re.match(r"^#[0-9A-Fa-f]{6}$", self.color):
            from django.core.exceptions import ValidationError

            raise ValidationError(
                "Color must be a valid hex color code (e.g., #3B82F6)"
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
