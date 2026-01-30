"""
Management command to check for and fix stuck script executions.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from app.models import ScriptExecution, Script


class Command(BaseCommand):
    help = "Check for stuck script executions and mark them as failed"

    def add_arguments(self, parser):
        parser.add_argument(
            "--timeout-minutes",
            type=int,
            default=30,
            help="Mark executions as stuck if running longer than this many minutes (default: 30)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be fixed without actually making changes",
        )

    def handle(self, *args, **options):
        timeout_minutes = options["timeout_minutes"]
        dry_run = options["dry_run"]
        cutoff_time = timezone.now() - timedelta(minutes=timeout_minutes)

        self.stdout.write(self.style.SUCCESS(f"=== Checking for stuck executions ==="))
        self.stdout.write(f"Timeout threshold: {timeout_minutes} minutes")
        self.stdout.write(f"Cutoff time: {cutoff_time}")
        self.stdout.write(f"Dry run: {dry_run}\n")

        # Find stuck executions
        stuck_executions = ScriptExecution.objects.filter(
            status="running", started_at__lt=cutoff_time
        ).select_related("script")

        if not stuck_executions.exists():
            self.stdout.write(self.style.SUCCESS("No stuck executions found."))
            return

        self.stdout.write(
            self.style.WARNING(f"Found {stuck_executions.count()} stuck executions:")
        )

        for execution in stuck_executions:
            self.stdout.write(f"\nExecution #{execution.id}:")
            self.stdout.write(f"  Script: {execution.script.name}")
            self.stdout.write(f"  Started: {execution.started_at}")
            self.stdout.write(
                f"  Running for: {(timezone.now() - execution.started_at).total_seconds() / 60:.1f} minutes"
            )
            self.stdout.write(f"  Process ID: {execution.process_id or 'None'}")

            if not dry_run:
                # Mark execution as failed
                execution.status = "failed"
                execution.error_message = f"Execution marked as failed due to timeout (running > {timeout_minutes} minutes)"
                execution.completed_at = timezone.now()
                execution.save()

                # Update script status
                execution.script.last_status = "failed"
                execution.script.save(update_fields=["last_status"])

                self.stdout.write(
                    self.style.SUCCESS("  ✓ Marked as failed and updated script status")
                )
            else:
                self.stdout.write(
                    self.style.WARNING("  ⚠ Would mark as failed (dry run)")
                )

        # Also check for scripts that are marked as running but have no active executions
        self.stdout.write(
            self.style.SUCCESS("\n=== Checking for scripts with incorrect status ===")
        )

        running_scripts = Script.objects.filter(last_status="running")
        fixed_count = 0

        for script in running_scripts:
            # Check if script has any running executions
            has_running_execution = script.executions.filter(status="running").exists()

            if not has_running_execution:
                self.stdout.write(
                    f"Script '{script.name}' is marked as running but has no active executions"
                )

                if not dry_run:
                    script.last_status = "idle"
                    script.save(update_fields=["last_status"])
                    self.stdout.write(self.style.SUCCESS("  ✓ Reset to idle status"))
                    fixed_count += 1
                else:
                    self.stdout.write(
                        self.style.WARNING("  ⚠ Would reset to idle (dry run)")
                    )

        if fixed_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nFixed {fixed_count} scripts with incorrect status."
                )
            )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\nThis was a dry run. Use --dry-run=False to apply fixes."
                )
            )
