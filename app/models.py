from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
import secrets
import os
import shutil


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

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True)
    theme_preference = models.CharField(
        max_length=20, choices=THEME_CHOICES, default="light"
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
    """Python script model."""

    STATUS_CHOICES = [
        ("idle", "Idle"),
        ("running", "Running"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
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

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    trigger_type = models.CharField(
        max_length=20,
        choices=[
            ("manual", "Manual"),
            ("scheduled", "Scheduled"),
            ("api", "API"),
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
