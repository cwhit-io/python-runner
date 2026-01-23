from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
import secrets


class UserProfile(models.Model):
    """Extended user profile with avatar and verification."""
    THEME_CHOICES = [
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('cupcake', 'Cupcake'),
        ('bumblebee', 'Bumblebee'),
        ('emerald', 'Emerald'),
        ('corporate', 'Corporate'),
        ('synthwave', 'Synthwave'),
        ('retro', 'Retro'),
        ('cyberpunk', 'Cyberpunk'),
        ('valentine', 'Valentine'),
        ('halloween', 'Halloween'),
        ('garden', 'Garden'),
        ('forest', 'Forest'),
        ('aqua', 'Aqua'),
        ('lofi', 'Lofi'),
        ('pastel', 'Pastel'),
        ('fantasy', 'Fantasy'),
        ('wireframe', 'Wireframe'),
        ('black', 'Black'),
        ('luxury', 'Luxury'),
        ('dracula', 'Dracula'),
        ('cmyk', 'CMYK'),
        ('autumn', 'Autumn'),
        ('business', 'Business'),
        ('acid', 'Acid'),
        ('lemonade', 'Lemonade'),
        ('night', 'Night'),
        ('coffee', 'Coffee'),
        ('winter', 'Winter'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    bio = models.TextField(max_length=500, blank=True)
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True)
    theme_preference = models.CharField(max_length=20, choices=THEME_CHOICES, default='light')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    def send_verification_email(self, request):
        """Send email verification link."""
        if not self.email_verification_token:
            self.email_verification_token = secrets.token_urlsafe(32)
            self.save()
        
        verification_url = request.build_absolute_uri(
            f'/verify-email/{self.email_verification_token}/'
        )
        
        send_mail(
            'Verify your email address',
            f'Click the link to verify your email: {verification_url}',
            'noreply@mysite.com',
            [self.user.email],
            fail_silently=False,
        )


class APIToken(models.Model):
    """API authentication tokens for users."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='api_tokens')
    token = models.CharField(max_length=64, unique=True, db_index=True)
    name = models.CharField(max_length=100, help_text="Token description/name")
    created_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = 'API Token'
        verbose_name_plural = 'API Tokens'
        ordering = ['-created_at']
    
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
    if hasattr(instance, 'profile'):
        instance.profile.save()


class APILog(models.Model):
    """Model to store API request logs."""
    
    # Request information
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=500)
    full_path = models.CharField(max_length=1000, blank=True)
    
    # User information
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='api_logs'
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
        null=True, 
        blank=True,
        help_text="Request duration in milliseconds"
    )
    
    # Error tracking
    error = models.TextField(blank=True)
    
    # Timestamps
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'API Log'
        verbose_name_plural = 'API Logs'
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['method', '-timestamp']),
            models.Index(fields=['status_code', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
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
