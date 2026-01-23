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
            
            # Only start scheduler in main process (after reload)
            if os.environ.get('RUN_MAIN') == 'true':
                try:
                    from app.services.scheduler import reload_all_schedules
                    reload_all_schedules()
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Failed to load schedules on startup: {e}")
