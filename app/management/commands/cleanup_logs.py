"""
Management command to clean up old execution logs and API logs.

Recommended retention:
- API logs: 7-30 days (for debugging/auditing)
- Execution stdout/stderr: 30-90 days (keep code snapshots for debugging)
- Executions: Keep indefinitely for historical tracking

Run via cron: python manage.py cleanup_logs --days=30
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from app.models import APILog, ScriptExecution


class Command(BaseCommand):
    help = "Clean up old API logs and execution output to prevent database bloat"

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-days',
            type=int,
            default=30,
            help='Days to keep API logs (default: 30)',
        )
        parser.add_argument(
            '--execution-output-days',
            type=int,
            default=90,
            help='Days to keep execution stdout/stderr (default: 90)',
        )

    def handle(self, *args, **options):
        api_days = options['api_days']
        exec_days = options['execution_output_days']

        # Clean up old API logs
        api_cutoff = timezone.now() - timedelta(days=api_days)
        api_deleted, _ = APILog.objects.filter(timestamp__lt=api_cutoff).delete()
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {api_deleted} API log entries older than {api_days} days")
        )

        # Clean up old execution output (keep status, timestamps, etc.)
        exec_cutoff = timezone.now() - timedelta(days=exec_days)
        execs_updated = ScriptExecution.objects.filter(
            created_at__lt=exec_cutoff
        ).exclude(stdout='').update(stdout='', stderr='')
        
        self.stdout.write(
            self.style.SUCCESS(f"Cleared output for {execs_updated} executions older than {exec_days} days")
        )

        # Clear old error messages for successful executions
        execs_error_cleared = ScriptExecution.objects.filter(
            created_at__lt=exec_cutoff,
            status='success'
        ).exclude(error_message='').update(error_message='')

        self.stdout.write(
            self.style.SUCCESS(f"Cleared error messages for {execs_error_cleared} old successful executions")
        )