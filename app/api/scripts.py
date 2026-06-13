"""
API endpoints for script management.
"""

from ninja import Router
from typing import List
from django.shortcuts import get_object_or_404
from app.auth import APITokenAuth
from app.models import Script, ScriptExecution, ScriptSchedule
from app.services.script_runner import ScriptRunner
from .schemas import (
    ScriptSchema,
    ScriptCreateSchema,
    ScriptUpdateSchema,
    ExecutionSchema,
    ExecutionDetailSchema,
    ScheduleSchema,
    ScheduleCreateSchema,
    TagSchema,
)
from .security import authenticate_bearer_token

router = Router(tags=["Scripts"])


# Endpoints
@router.get("/scripts", response=List[ScriptSchema], auth=APITokenAuth())
def list_scripts(request):
    """List all scripts owned by the authenticated user."""
    scripts = Script.objects.filter(owner=request.auth.user).order_by("-updated_at")
    return scripts


@router.post("/scripts", response=ScriptSchema, auth=APITokenAuth())
def create_script(request, payload: ScriptCreateSchema):
    """Create a new script."""
    from app.models import Tag

    script = Script.objects.create(
        name=payload.name,
        description=payload.description,
        code=payload.code,
        dependencies=payload.dependencies,
        owner=request.auth.user,
    )

    # Handle tags - only assign existing tags
    if payload.tags:
        tags = []
        for tag_name in payload.tags:
            try:
                tag = Tag.objects.get(name=tag_name, created_by=request.auth.user)
                tags.append(tag)
            except Tag.DoesNotExist:
                # Skip tags that don't exist or don't belong to the user
                pass
        script.tags.set(tags)  # type: ignore[attr-defined]

    return script


@router.get("/scripts/{script_id}", response=ScriptSchema, auth=APITokenAuth())
def get_script(request, script_id: int):
    """Get a specific script."""
    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)
    return script


@router.put("/scripts/{script_id}", response=ScriptSchema, auth=APITokenAuth())
def update_script(request, script_id: int, payload: ScriptUpdateSchema):
    """Update a script."""
    from app.models import Tag

    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)

    for attr, value in payload.dict(exclude_unset=True).items():
        if attr == "tags":
            # Handle tags separately - only assign existing tags
            if value is not None:
                tags = []
                for tag_name in value:
                    try:
                        tag = Tag.objects.get(
                            name=tag_name, created_by=request.auth.user
                        )
                        tags.append(tag)
                    except Tag.DoesNotExist:
                        # Skip tags that don't exist or don't belong to the user
                        pass
                script.tags.set(tags)  # type: ignore[attr-defined]
        else:
            setattr(script, attr, value)

    script.save()
    return script


@router.delete("/scripts/{script_id}", auth=APITokenAuth())
def delete_script(request, script_id: int):
    """Delete a script."""
    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)
    script.delete()
    return {"success": True}


@router.post("/scripts/{script_id}/execute", response=ExecutionSchema, auth=None)
def execute_script_api(request, script_id: int):
    """Execute a script.

    Requires authentication. For public scripts, use the webhook endpoint instead.
    """
    api_token_obj = authenticate_bearer_token(request)
    if api_token_obj is None:
        return {"error": "Authentication required"}, 401

    # Load the script
    script = get_object_or_404(Script, id=script_id)

    # Ensure the token owner matches script owner
    if script.owner_id != api_token_obj.user_id:
        return {"error": "Permission denied"}, 403

    # Execute the script
    runner = ScriptRunner(script)
    execution = runner.execute(triggered_by=api_token_obj.user, trigger_type="api")

    return execution


@router.get(
    "/scripts/{script_id}/executions",
    response=List[ExecutionSchema],
    auth=APITokenAuth(),
)
def list_executions(request, script_id: int):
    """List executions for a script."""
    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)
    executions = script.executions.all()[:50]  # type: ignore[attr-defined]
    return executions


@router.get(
    "/executions/{execution_id}", response=ExecutionDetailSchema, auth=APITokenAuth()
)
def get_execution(request, execution_id: int):
    """Get execution details."""
    execution = get_object_or_404(ScriptExecution, id=execution_id)

    # Check permission
    if execution.script.owner != request.auth.user:
        return {"error": "Permission denied"}, 403

    return execution


@router.get(
    "/scripts/{script_id}/schedules", response=List[ScheduleSchema], auth=APITokenAuth()
)
def list_schedules(request, script_id: int):
    """List schedules for a script."""
    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)
    schedules = script.schedules.all()  # type: ignore[attr-defined]
    return schedules


@router.post(
    "/scripts/{script_id}/schedules", response=ScheduleSchema, auth=APITokenAuth()
)
def create_schedule(request, script_id: int, payload: ScheduleCreateSchema):
    """Create a schedule for a script."""
    from app.services.scheduler import schedule_job

    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)

    schedule = ScriptSchedule.objects.create(
        script=script,
        name=payload.name,
        cron_expression=payload.cron_expression,
        timezone=getattr(request.auth.user.profile, "timezone", "UTC")
        if hasattr(request.auth.user, "profile")
        else "UTC",
        created_by=request.auth.user,
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


# Tag API endpoints
@router.get("/tags", response=List[TagSchema], auth=APITokenAuth())
def list_tags(request):
    """List all tags for the current user."""
    from app.models import Tag

    tags = Tag.objects.filter(created_by=request.auth.user).order_by("name")
    return tags


@router.post("/tags", response=TagSchema, auth=APITokenAuth())
def create_tag(request, payload: dict):
    """Create a new tag."""
    from app.models import Tag
    from django.core.exceptions import ValidationError

    try:
        tag = Tag.objects.create(
            name=payload["name"],
            color=payload.get("color", "#3B82F6"),
            description=payload.get("description", ""),
            created_by=request.auth.user,
        )
        return tag
    except Exception as e:
        return {"error": str(e)}, 400


@router.put("/tags/{tag_id}", response=TagSchema, auth=APITokenAuth())
def update_tag(request, tag_id: int, payload: dict):
    """Update a tag."""
    from app.models import Tag

    tag = get_object_or_404(Tag, id=tag_id, created_by=request.auth.user)

    if "name" in payload:
        tag.name = payload["name"]
    if "color" in payload:
        tag.color = payload["color"]
    if "description" in payload:
        tag.description = payload["description"]

    try:
        tag.save()
        return tag
    except Exception as e:
        return {"error": str(e)}, 400


@router.delete("/tags/{tag_id}", auth=APITokenAuth())
def delete_tag(request, tag_id: int):
    """Delete a tag."""
    from app.models import Tag

    tag = get_object_or_404(Tag, id=tag_id, created_by=request.auth.user)
    tag.delete()
    return {"message": "Tag deleted successfully"}


@router.post("/scripts/{script_id}/webhook", include_in_schema=False)
def execute_script_webhook(request, script_id: int):
    """Execute a public script via webhook (no authentication required)."""
    script = get_object_or_404(Script, id=script_id)

    # Only allow webhook execution for public scripts
    if not script.is_public:
        return {"error": "Script is not public"}, 403

    # Execute the script
    runner = ScriptRunner(script)
    execution = runner.execute(triggered_by=None, trigger_type="webhook")

    return {"ok": True, "execution_id": execution.id}
