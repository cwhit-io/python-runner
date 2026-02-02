"""
Django app configuration for initializing the scheduler.
"""
from django.apps import AppConfig
import sys


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    
    def ready(self):
        """Initialize scheduler when Django starts."""
        # Only run scheduler initialization in runserver/production, not during migrations
        # Avoid database access during app initialization
        if 'migrate' not in sys.argv and 'makemigrations' not in sys.argv:
            # Import here to avoid AppRegistryNotReady error
            import os

            # If using runserver's autoreloader, only start in the reloaded process.
            if 'runserver' in sys.argv and os.environ.get('RUN_MAIN') != 'true':
                return

            try:
                from app.services.scheduler import reload_all_schedules
                reload_all_schedules()
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to load schedules on startup: {e}")
