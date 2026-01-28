"""
Scheduler service using APScheduler for running scripts on schedule.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from app.models import ScriptSchedule
from app.services.script_runner import execute_script
import logging
from django.utils import timezone
from dateutil.rrule import rrulestr
from dateutil.parser import parse as parse_dt

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler = None


def get_scheduler():
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
        _scheduler.start()
    return _scheduler


def schedule_job(schedule: ScriptSchedule):
    """Add a scheduled job to the scheduler."""
    scheduler = get_scheduler()

    # Create job ID from schedule ID
    job_id = f"script_schedule_{schedule.id}"

    # Remove existing job if it exists
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)

    # Only add if schedule is active
    if not schedule.is_active:
        # ensure DB reflects that there's no next run when inactive
        try:
            schedule.next_run = None
            schedule.save(update_fields=["next_run"])
        except Exception:
            pass
        return

    try:
        if schedule.schedule_type == "cron":
            # Parse cron expression and create trigger
            trigger = CronTrigger.from_crontab(
                schedule.cron_expression, timezone=schedule.timezone
            )
            scheduler.add_job(
                func=_execute_scheduled_script,
                trigger=trigger,
                id=job_id,
                args=[schedule.script.id, schedule.id],
                replace_existing=True,
                max_instances=1,  # Prevent overlapping executions
            )
            # persist the next_run time to the schedule record
            try:
                job = scheduler.get_job(job_id)
                if job and getattr(job, "next_run_time", None):
                    schedule.next_run = job.next_run_time
                    schedule.save(update_fields=["next_run"])
            except Exception:
                logger.exception("Failed to persist next_run for cron job %s", job_id)

        elif schedule.schedule_type == "single":
            # calendar_expression expected to be an ISO datetime string
            if not schedule.calendar_expression:
                logger.error(f"Single schedule {job_id} missing calendar_expression")
                return
            dt = parse_dt(schedule.calendar_expression)
            # ensure timezone-aware
            if dt.tzinfo is None:
                dt = timezone.make_aware(dt, timezone=timezone.get_default_timezone())
            scheduler.add_job(
                func=_execute_scheduled_script,
                trigger="date",
                run_date=dt,
                id=job_id,
                args=[schedule.script.id, schedule.id],
                replace_existing=True,
            )
            try:
                job = scheduler.get_job(job_id)
                if job and getattr(job, "next_run_time", None):
                    schedule.next_run = job.next_run_time
                    schedule.save(update_fields=["next_run"])
            except Exception:
                logger.exception("Failed to persist next_run for single job %s", job_id)

        elif schedule.schedule_type == "rrule":
            # calendar_expression expected to be an RFC5545 RRULE string
            if not schedule.calendar_expression:
                logger.error(f"RRULE schedule {job_id} missing calendar_expression")
                return
            now = timezone.now()
            try:
                rule = rrulestr(schedule.calendar_expression, dtstart=now)
                next_dt = rule.after(now, inc=True)
            except Exception as e:
                logger.error(f"Failed parsing RRULE for {job_id}: {e}")
                return
            if not next_dt:
                logger.info(f"RRULE {job_id} has no future occurrences")
                return
            # Ensure timezone-aware
            if next_dt.tzinfo is None:
                next_dt = timezone.make_aware(
                    next_dt, timezone=timezone.get_default_timezone()
                )
            scheduler.add_job(
                func=_execute_scheduled_script,
                trigger="date",
                run_date=next_dt,
                id=job_id,
                args=[schedule.script.id, schedule.id],
                replace_existing=True,
            )
            try:
                job = scheduler.get_job(job_id)
                if job and getattr(job, "next_run_time", None):
                    schedule.next_run = job.next_run_time
                    schedule.save(update_fields=["next_run"])
            except Exception:
                logger.exception("Failed to persist next_run for rrule job %s", job_id)

        logger.info(f"Scheduled job added: {job_id}")

    except Exception as e:
        logger.error(f"Failed to schedule job {job_id}: {e}")


def remove_schedule(schedule: ScriptSchedule):
    """Remove a scheduled job from the scheduler."""
    scheduler = get_scheduler()
    job_id = f"script_schedule_{schedule.id}"

    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"Scheduled job removed: {job_id}")
    try:
        schedule.next_run = None
        schedule.save(update_fields=["next_run"])
    except Exception:
        pass


def _execute_scheduled_script(script_id, schedule_id):
    """Internal function to execute a script via schedule."""
    from django.utils import timezone

    try:
        # Execute the script
        execution = execute_script(
            script_id=script_id, triggered_by=None, trigger_type="scheduled"
        )

        # Update schedule's last_run time
        schedule = ScriptSchedule.objects.get(id=schedule_id)
        schedule.last_run = timezone.now()
        schedule.save(update_fields=["last_run"])

        # For RRULE schedules, schedule the next occurrence
        try:
            if schedule.schedule_type == "rrule":
                # schedule_job will compute and add the next occurrence
                schedule_job(schedule)
        except Exception:
            logger.exception("Failed to reschedule RRULE")

        logger.info(
            f"Scheduled execution completed: script={script_id}, execution={execution.id}"
        )

    except Exception as e:
        logger.error(f"Scheduled execution failed: script={script_id}, error={e}")


def reload_all_schedules():
    """Reload all active schedules into the scheduler."""
    from app.models import ScriptSchedule

    scheduler = get_scheduler()

    # Remove all existing script schedule jobs
    for job in scheduler.get_jobs():
        if job.id.startswith("script_schedule_"):
            scheduler.remove_job(job.id)

    # Add all active schedules
    active_schedules = ScriptSchedule.objects.filter(is_active=True).select_related(
        "script"
    )
    for schedule in active_schedules:
        schedule_job(schedule)

    logger.info(f"Reloaded {active_schedules.count()} active schedules")


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown()
        _scheduler = None


def compute_next_run(schedule: ScriptSchedule):
    """Compute the next run datetime for a schedule without mutating scheduler state.

    Returns a timezone-aware datetime or None if no future run.
    """
    from django.utils import timezone

    try:
        now = timezone.now()
        if not schedule.is_active:
            return None

        if schedule.schedule_type == "cron":
            # Build a CronTrigger and compute next fire time
            try:
                trigger = CronTrigger.from_crontab(
                    schedule.cron_expression, timezone=schedule.timezone
                )
                next_dt = trigger.get_next_fire_time(None, now)
                return next_dt
            except Exception:
                logger.exception(
                    "Failed computing next_run for cron schedule %s", schedule.id
                )
                return None

        if schedule.schedule_type == "single":
            if not schedule.calendar_expression:
                return None
            try:
                dt = parse_dt(schedule.calendar_expression)
                if dt.tzinfo is None:
                    dt = timezone.make_aware(
                        dt, timezone=timezone.get_default_timezone()
                    )
                return dt if dt >= now else None
            except Exception:
                logger.exception(
                    "Failed parsing single calendar_expression for %s", schedule.id
                )
                return None

        if schedule.schedule_type == "rrule":
            if not schedule.calendar_expression:
                return None
            try:
                # rrulestr can parse DTSTART if present in the string
                rule = rrulestr(schedule.calendar_expression)
                # prefer using schedule.next_run if set and in future
                next_dt = rule.after(now, inc=True)
                if next_dt and next_dt.tzinfo is None:
                    next_dt = timezone.make_aware(
                        next_dt, timezone=timezone.get_default_timezone()
                    )
                return next_dt
            except Exception:
                logger.exception("Failed computing RRULE next_run for %s", schedule.id)
                return None

    except Exception:
        logger.exception(
            "Unexpected error computing next_run for schedule %s",
            getattr(schedule, "id", "?"),
        )
        return None
