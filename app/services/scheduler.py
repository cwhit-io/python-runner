"""
Scheduler service using APScheduler for running scripts on schedule.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.events import (
    EVENT_JOB_EXECUTED,
    EVENT_JOB_ERROR,
    EVENT_JOB_MISSED,
)
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from django.conf import settings
from app.models import ScriptSchedule
from app.services.script_runner import execute_script
import logging
from django.utils import timezone
from dateutil.parser import parse as parse_dt
import pytz

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler = None
_listener_added = False


def get_scheduler():
    """Get or create the global scheduler instance."""
    global _scheduler
    global _listener_added
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
        _scheduler.start()

    if _scheduler and not _listener_added:
        # Log job lifecycle events to aid debugging.
        _scheduler.add_listener(
            _job_event_listener,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED,
        )
        _listener_added = True
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
            if not schedule.cron_expression:
                logger.error(f"Cron schedule {job_id} missing cron_expression")
                return
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
                misfire_grace_time=600,  # Allow 5 minutes grace period for missed jobs
            )
            # persist the next_run time to the schedule record
            try:
                job = scheduler.get_job(job_id)
                if job and getattr(job, "next_run_time", None):
                    # Convert to UTC for database storage
                    schedule.next_run = (
                        job.next_run_time.astimezone(pytz.UTC)
                        if job.next_run_time.tzinfo
                        else job.next_run_time
                    )
                    schedule.save(update_fields=["next_run"])
            except Exception:
                logger.exception("Failed to persist next_run for cron job %s", job_id)

        elif schedule.schedule_type == "single":
            if not schedule.start_datetime:
                logger.error(f"Single schedule {job_id} missing start_datetime")
                return
            dt = schedule.start_datetime
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
                misfire_grace_time=300,  # Allow 5 minutes grace period for missed jobs
            )
            try:
                job = scheduler.get_job(job_id)
                if job and getattr(job, "next_run_time", None):
                    # Convert to UTC for database storage
                    schedule.next_run = (
                        job.next_run_time.astimezone(pytz.UTC)
                        if job.next_run_time.tzinfo
                        else job.next_run_time
                    )
                    schedule.save(update_fields=["next_run"])
            except Exception:
                logger.exception("Failed to persist next_run for single job %s", job_id)

        elif schedule.schedule_type == "interval":
            if not schedule.start_datetime or not schedule.interval_unit:
                logger.error(
                    f"Interval schedule {job_id} missing start_datetime or interval_unit"
                )
                return

            start_dt = schedule.start_datetime
            # ensure timezone-aware
            if start_dt.tzinfo is None:
                start_dt = timezone.make_aware(
                    start_dt, timezone=timezone.get_default_timezone()
                )

            # Build interval trigger kwargs
            interval_kwargs = {schedule.interval_unit: schedule.interval_value}
            if schedule.interval_unit == "months":
                # APScheduler doesn't have months, approximate with 30 days
                interval_kwargs = {"days": schedule.interval_value * 30}

            trigger = IntervalTrigger(
                start_date=start_dt, timezone=schedule.timezone, **interval_kwargs
            )

            scheduler.add_job(
                func=_execute_scheduled_script,
                trigger=trigger,
                id=job_id,
                args=[schedule.script.id, schedule.id],
                replace_existing=True,
                max_instances=1,
                misfire_grace_time=300,  # Allow 5 minutes grace period for missed jobs
            )
            try:
                job = scheduler.get_job(job_id)
                if job and getattr(job, "next_run_time", None):
                    # Convert to UTC for database storage
                    schedule.next_run = (
                        job.next_run_time.astimezone(pytz.UTC)
                        if job.next_run_time.tzinfo
                        else job.next_run_time
                    )
                    schedule.save(update_fields=["next_run"])
            except Exception:
                logger.exception(
                    "Failed to persist next_run for interval job %s", job_id
                )

        logger.info(f"Scheduled job added: {job_id}")

    except Exception as e:
        logger.error(f"Failed to schedule job {job_id}: {e}")


def _persist_next_run(schedule_id: int):
    """Persist the scheduler's next_run_time back to the DB for visibility."""
    try:
        scheduler = get_scheduler()
        job_id = f"script_schedule_{schedule_id}"
        job = scheduler.get_job(job_id)
        if not job or not getattr(job, "next_run_time", None):
            return

        schedule = ScriptSchedule.objects.filter(id=schedule_id).first()
        if not schedule:
            return

        next_dt = job.next_run_time
        schedule.next_run = next_dt.astimezone(pytz.UTC) if next_dt.tzinfo else next_dt
        schedule.save(update_fields=["next_run"])
    except Exception:
        logger.exception("Failed to persist next_run for schedule %s", schedule_id)


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

    logger.info(
        f"Starting scheduled execution: script={script_id}, schedule={schedule_id}"
    )

    try:
        # Execute the script
        execution = execute_script(
            script_id=script_id, triggered_by=None, trigger_type="scheduled"
        )

        # Update schedule's last_run time
        schedule = ScriptSchedule.objects.get(id=schedule_id)
        schedule.last_run = timezone.now()

        # For single schedules, deactivate after successful execution
        if schedule.schedule_type == "single":
            schedule.is_active = False
            schedule.save(update_fields=["last_run", "is_active"])
            logger.info(
                f"Deactivating single schedule {schedule_id} after successful execution"
            )
            # Remove from scheduler since it's completed (this also clears next_run)
            remove_schedule(schedule)
            return execution  # Return early since we don't need to save again

        # For RRULE schedules, schedule the next occurrence
        try:
            if schedule.schedule_type == "rrule":
                # schedule_job will compute and add the next occurrence
                schedule_job(schedule)
        except Exception:
            logger.exception("Failed to reschedule RRULE")

        logger.info(
            f"Scheduled execution completed successfully: script={script_id}, execution={execution.id}, status={execution.status}"
        )
        _persist_next_run(schedule_id)
        return execution

    except Exception as e:
        logger.error(
            f"Scheduled execution failed: script={script_id}, schedule={schedule_id}, error={e}"
        )

        # For single schedules, deactivate even on failure since they only run once
        try:
            schedule = ScriptSchedule.objects.get(id=schedule_id)
            if schedule.schedule_type == "single":
                schedule.is_active = False
                schedule.last_run = timezone.now()
                schedule.save(update_fields=["is_active", "last_run"])
                logger.info(
                    f"Deactivated single schedule {schedule_id} after failed execution"
                )
                # Remove from scheduler since it's completed
                remove_schedule(schedule)
        except Exception as deactivate_error:
            logger.error(
                f"Failed to deactivate single schedule {schedule_id}: {deactivate_error}"
            )

        # Try to create a failed execution record if the script execution failed
        try:
            from app.models import Script

            script = Script.objects.get(id=script_id)
            from app.models import ScriptExecution

            failed_execution = ScriptExecution.objects.create(
                script=script,
                triggered_by=None,
                trigger_type="scheduled",
                status="failed",
                error_message=f"Scheduled execution failed: {str(e)}",
                started_at=timezone.now(),
            )
            logger.info(f"Created failed execution record: {failed_execution.id}")
        except Exception as record_error:
            logger.error(f"Failed to create execution record: {record_error}")
        raise


def reload_all_schedules():
    """Reload all active schedules into the scheduler."""
    from app.models import ScriptSchedule

    scheduler = get_scheduler()
    logger.info("Reloading all schedules...")

    # Remove all existing script schedule jobs
    removed_count = 0
    for job in scheduler.get_jobs():
        if job.id.startswith("script_schedule_"):
            scheduler.remove_job(job.id)
            removed_count += 1

    logger.info(f"Removed {removed_count} existing schedule jobs")

    # Add all active schedules
    active_schedules = ScriptSchedule.objects.filter(is_active=True).select_related(
        "script"
    )
    added_count = 0

    for schedule in active_schedules:
        try:
            schedule_job(schedule)
            added_count += 1
            logger.info(
                f"Added schedule job: {schedule.id} ({schedule.script.name} - {schedule.name})"
            )
        except Exception as e:
            logger.error(f"Failed to add schedule job {schedule.id}: {e}")

    logger.info(f"Successfully loaded {added_count} active schedules")


def execute_missed_schedule(schedule_id):
    """Manually execute a schedule that was missed. Useful for debugging."""
    from app.models import ScriptSchedule

    try:
        schedule = ScriptSchedule.objects.get(id=schedule_id, is_active=True)
        logger.info(
            f"Manually executing missed schedule: {schedule.id} ({schedule.script.name} - {schedule.name})"
        )

        execution = _execute_scheduled_script(schedule.script.id, schedule.id)

        logger.info(
            f"Manual execution completed: execution={execution.id}, status={execution.status}"
        )
        return execution

    except ScriptSchedule.DoesNotExist:
        logger.error(f"Schedule {schedule_id} not found or not active")
        return None
    except Exception as e:
        logger.error(f"Manual execution failed for schedule {schedule_id}: {e}")
        return None

    logger.info(f"Reloaded {active_schedules.count()} active schedules")


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown()
        _scheduler = None
    global _listener_added
    _listener_added = False


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
                # Convert to UTC for consistency
                return (
                    next_dt.astimezone(pytz.UTC)
                    if next_dt and next_dt.tzinfo
                    else next_dt
                )
            except Exception:
                logger.exception(
                    "Failed computing next_run for cron schedule %s", schedule.id
                )
                return None

        if schedule.schedule_type == "single":
            if not schedule.start_datetime:
                return None
            try:
                dt = schedule.start_datetime
                if dt.tzinfo is None:
                    dt = timezone.make_aware(
                        dt, timezone=timezone.get_default_timezone()
                    )
                return dt if dt >= now else None
            except Exception:
                logger.exception(
                    "Failed computing next_run for single schedule %s", schedule.id
                )
                return None

        if schedule.schedule_type == "interval":
            if not schedule.start_datetime or not schedule.interval_unit:
                return None
            try:
                start_dt = schedule.start_datetime
                if start_dt.tzinfo is None:
                    start_dt = timezone.make_aware(
                        start_dt, timezone=timezone.get_default_timezone()
                    )

                # If start time is in the future, that's the next run
                if start_dt >= now:
                    return start_dt

                # Calculate next occurrence based on interval
                from datetime import timedelta

                if schedule.interval_unit == "hours":
                    delta = timedelta(hours=schedule.interval_value)
                elif schedule.interval_unit == "days":
                    delta = timedelta(days=schedule.interval_value)
                elif schedule.interval_unit == "weeks":
                    delta = timedelta(weeks=schedule.interval_value)
                elif schedule.interval_unit == "months":
                    # Approximate months as 30 days
                    delta = timedelta(days=schedule.interval_value * 30)
                else:
                    return None

                # Find the next occurrence after now
                next_dt = start_dt
                while next_dt < now:
                    next_dt += delta

                return next_dt
            except Exception:
                logger.exception(
                    "Failed computing interval next_run for %s", schedule.id
                )
                return None

    except Exception:
        logger.exception(
            "Unexpected error computing next_run for schedule %s",
            getattr(schedule, "id", "?"),
        )
        return None


def _job_event_listener(event):
    """Log scheduler events to help diagnose missed runs."""
    try:
        job_id = getattr(event, "job_id", "?")
        if event.code == EVENT_JOB_EXECUTED:
            logger.info("Job %s executed", job_id)
        elif event.code == EVENT_JOB_ERROR:
            logger.error("Job %s errored: %s", job_id, getattr(event, "exception", ""))
        elif event.code == EVENT_JOB_MISSED:
            logger.warning("Job %s missed its run time", job_id)
    except Exception:
        logger.exception("Scheduler event listener failed")
