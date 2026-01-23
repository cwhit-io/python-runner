"""
Scheduler service using APScheduler for running scripts on schedule.
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from django.conf import settings
from app.models import ScriptSchedule
from app.services.script_runner import execute_script
import logging

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
        return
    
    try:
        # Parse cron expression and create trigger
        trigger = CronTrigger.from_crontab(
            schedule.cron_expression,
            timezone=schedule.timezone
        )
        
        # Add job to scheduler
        scheduler.add_job(
            func=_execute_scheduled_script,
            trigger=trigger,
            id=job_id,
            args=[schedule.script.id, schedule.id],
            replace_existing=True,
            max_instances=1  # Prevent overlapping executions
        )
        
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


def _execute_scheduled_script(script_id, schedule_id):
    """Internal function to execute a script via schedule."""
    from django.utils import timezone
    
    try:
        # Execute the script
        execution = execute_script(
            script_id=script_id,
            triggered_by=None,
            trigger_type='scheduled'
        )
        
        # Update schedule's last_run time
        schedule = ScriptSchedule.objects.get(id=schedule_id)
        schedule.last_run = timezone.now()
        schedule.save(update_fields=['last_run'])
        
        logger.info(f"Scheduled execution completed: script={script_id}, execution={execution.id}")
        
    except Exception as e:
        logger.error(f"Scheduled execution failed: script={script_id}, error={e}")


def reload_all_schedules():
    """Reload all active schedules into the scheduler."""
    from app.models import ScriptSchedule
    
    scheduler = get_scheduler()
    
    # Remove all existing script schedule jobs
    for job in scheduler.get_jobs():
        if job.id.startswith('script_schedule_'):
            scheduler.remove_job(job.id)
    
    # Add all active schedules
    active_schedules = ScriptSchedule.objects.filter(is_active=True).select_related('script')
    for schedule in active_schedules:
        schedule_job(schedule)
    
    logger.info(f"Reloaded {active_schedules.count()} active schedules")


def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown()
        _scheduler = None
