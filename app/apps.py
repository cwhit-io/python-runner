"""
Django app configuration for initializing the scheduler.
"""
from django.apps import AppConfig


class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    
    def ready(self):
        """Initialize scheduler when Django starts."""
        # Import here to avoid AppRegistryNotReady error
        from app.services.scheduler import reload_all_schedules
        import os
        
        # Only start scheduler in main process (not in migration, etc.)
        # Check if we're running the server
        if os.environ.get('RUN_MAIN') == 'true' or 'runserver' not in os.sys.argv:
            try:
                reload_all_schedules()
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to load schedules on startup: {e}")
