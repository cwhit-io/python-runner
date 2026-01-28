"""
Management command to check scheduler status and compute next_run for all schedules.
"""

from django.core.management.base import BaseCommand
from app.models import ScriptSchedule
from app.services.scheduler import get_scheduler, compute_next_run, schedule_job


class Command(BaseCommand):
    help = "Check APScheduler status and compute next_run for all schedules"

    def handle(self, *args, **options):
        scheduler = get_scheduler()

        self.stdout.write(self.style.SUCCESS("\n=== APScheduler Status ==="))
        self.stdout.write(f"Running: {scheduler.running}")

        jobs = scheduler.get_jobs()
        self.stdout.write(f"Total jobs in scheduler: {len(jobs)}\n")

        for job in jobs:
            self.stdout.write(f"  Job ID: {job.id}")
            self.stdout.write(f"    Next run: {job.next_run_time}")
            self.stdout.write(f"    Trigger: {job.trigger}\n")

        self.stdout.write(self.style.SUCCESS("\n=== Database Schedules ==="))
        schedules = ScriptSchedule.objects.all().select_related("script")

        for schedule in schedules:
            self.stdout.write(f"\nSchedule #{schedule.id}: {schedule.name}")
            self.stdout.write(f"  Script: {schedule.script.name}")
            self.stdout.write(f"  Type: {schedule.schedule_type}")
            self.stdout.write(f"  Active: {schedule.is_active}")
            self.stdout.write(f"  DB next_run: {schedule.next_run}")

            # Compute next run
            computed_next = compute_next_run(schedule)
            self.stdout.write(f"  Computed next_run: {computed_next}")

            if schedule.schedule_type == "cron":
                self.stdout.write(f"  Cron: {schedule.cron_expression}")
            else:
                self.stdout.write(f"  Calendar: {schedule.calendar_expression[:100]}")

            # Check if job exists in scheduler
            job_id = f"script_schedule_{schedule.id}"
            job = scheduler.get_job(job_id)
            if job:
                self.stdout.write(
                    self.style.SUCCESS(f"  ✓ Job in scheduler: {job.next_run_time}")
                )
            else:
                self.stdout.write(self.style.WARNING(f"  ✗ Job NOT in scheduler"))
                if schedule.is_active:
                    self.stdout.write(self.style.WARNING(f"    Re-adding job..."))
                    try:
                        schedule_job(schedule)
                        job = scheduler.get_job(job_id)
                        if job:
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"    ✓ Job added: {job.next_run_time}"
                                )
                            )
                            # Update DB
                            schedule.next_run = job.next_run_time
                            schedule.save(update_fields=["next_run"])
                        else:
                            self.stdout.write(
                                self.style.ERROR(f"    ✗ Failed to add job")
                            )
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"    Error: {e}"))

        self.stdout.write(self.style.SUCCESS("\n=== Done ===\n"))
