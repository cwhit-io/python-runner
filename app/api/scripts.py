"""
API endpoints for script management.
"""
from ninja import Router, Schema
from typing import List, Optional
from datetime import datetime
from django.shortcuts import get_object_or_404
from app.auth import APITokenAuth
from app.models import Script, ScriptExecution, ScriptSchedule
from app.services.script_runner import ScriptRunner

router = Router(tags=["Scripts"])


# Schemas
class ScriptSchema(Schema):
    id: int
    name: str
    description: str
    code: str
    dependencies: str
    last_status: str
    last_run: Optional[datetime]
    execution_count: int
    is_public: bool
    created_at: datetime
    updated_at: datetime


class ScriptCreateSchema(Schema):
    name: str
    description: Optional[str] = ""
    code: Optional[str] = "# Write your Python script here\nprint('Hello, World!')"
    dependencies: Optional[str] = ""


class ScriptUpdateSchema(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    code: Optional[str] = None
    dependencies: Optional[str] = None
    is_public: Optional[bool] = None


class ExecutionSchema(Schema):
    id: int
    script_id: int
    status: str
    trigger_type: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    exit_code: Optional[int]
    created_at: datetime


class ExecutionDetailSchema(ExecutionSchema):
    stdout: str
    stderr: str
    error_message: str


class ScheduleSchema(Schema):
    id: int
    script_id: int
    name: str
    cron_expression: str
    timezone: str
    is_active: bool
    last_run: Optional[datetime]
    next_run: Optional[datetime]


class ScheduleCreateSchema(Schema):
    name: str
    cron_expression: str
    timezone: Optional[str] = "UTC"


# Endpoints
@router.get("/scripts", response=List[ScriptSchema], auth=APITokenAuth())
def list_scripts(request):
    """List all scripts owned by the authenticated user."""
    scripts = Script.objects.filter(owner=request.auth.user).order_by('-updated_at')
    return scripts


@router.post("/scripts", response=ScriptSchema, auth=APITokenAuth())
def create_script(request, payload: ScriptCreateSchema):
    """Create a new script."""
    script = Script.objects.create(
        name=payload.name,
        description=payload.description,
        code=payload.code,
        dependencies=payload.dependencies,
        owner=request.auth.user
    )
    return script


@router.get("/scripts/{script_id}", response=ScriptSchema, auth=APITokenAuth())
def get_script(request, script_id: int):
    """Get a specific script."""
    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)
    return script


@router.put("/scripts/{script_id}", response=ScriptSchema, auth=APITokenAuth())
def update_script(request, script_id: int, payload: ScriptUpdateSchema):
    """Update a script."""
    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)
    
    for attr, value in payload.dict(exclude_unset=True).items():
        setattr(script, attr, value)
    
    script.save()
    return script


@router.delete("/scripts/{script_id}", auth=APITokenAuth())
def delete_script(request, script_id: int):
    """Delete a script."""
    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)
    script.delete()
    return {"success": True}


@router.post("/scripts/{script_id}/execute", response=ExecutionSchema, auth=APITokenAuth())
def execute_script_api(request, script_id: int):
    """Execute a script."""
    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)
    
    runner = ScriptRunner(script)
    execution = runner.execute(triggered_by=request.auth.user, trigger_type='api')
    
    return execution


@router.get("/scripts/{script_id}/executions", response=List[ExecutionSchema], auth=APITokenAuth())
def list_executions(request, script_id: int):
    """List executions for a script."""
    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)
    executions = script.executions.all()[:50]
    return executions


@router.get("/executions/{execution_id}", response=ExecutionDetailSchema, auth=APITokenAuth())
def get_execution(request, execution_id: int):
    """Get execution details."""
    execution = get_object_or_404(ScriptExecution, id=execution_id)
    
    # Check permission
    if execution.script.owner != request.auth.user:
        return {"error": "Permission denied"}, 403
    
    return execution


@router.get("/scripts/{script_id}/schedules", response=List[ScheduleSchema], auth=APITokenAuth())
def list_schedules(request, script_id: int):
    """List schedules for a script."""
    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)
    schedules = script.schedules.all()
    return schedules


@router.post("/scripts/{script_id}/schedules", response=ScheduleSchema, auth=APITokenAuth())
def create_schedule(request, script_id: int, payload: ScheduleCreateSchema):
    """Create a schedule for a script."""
    from app.services.scheduler import schedule_job
    
    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)
    
    schedule = ScriptSchedule.objects.create(
        script=script,
        name=payload.name,
        cron_expression=payload.cron_expression,
        timezone=payload.timezone,
        created_by=request.auth.user
    )
    
    schedule_job(schedule)
    
    return schedule


@router.delete("/schedules/{schedule_id}", auth=APITokenAuth())
def delete_schedule(request, schedule_id: int):
    """Delete a schedule."""
    from app.services.scheduler import remove_schedule
    
    schedule = get_object_or_404(ScriptSchedule, id=schedule_id)
    
    # Check permission
    if schedule.script.owner != request.auth.user:
        return {"error": "Permission denied"}, 403
    
    remove_schedule(schedule)
    schedule.delete()
    
    return {"success": True}
