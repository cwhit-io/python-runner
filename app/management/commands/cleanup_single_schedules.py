from django.core.management.base import BaseCommand
from django.utils import timezone
from app.models import ScriptSchedule


class Command(BaseCommand):
    help = "Clean up completed single schedules that are still active"

    def handle(self, *args, **options):
        now = timezone.now()

        # Find single schedules that are active but have next_run in the past
        # and have been executed (have last_run set)
        completed_schedules = ScriptSchedule.objects.filter(
            schedule_type="single",
            is_active=True,
            next_run__lt=now,
            last_run__isnull=False,
        )

        count = 0
        for schedule in completed_schedules:
            schedule.is_active = False
            schedule.save(update_fields=["is_active"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Deactivated completed single schedule: {schedule.name} (ID: {schedule.id})"
                )
            )
            count += 1

        if count == 0:
            self.stdout.write("No completed single schedules found to clean up.")
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Successfully cleaned up {count} completed single schedules."
                )
            )
