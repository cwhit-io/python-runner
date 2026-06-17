"""
API endpoints for script management.
"""

import json
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
    ExecutionResultSchema,
    ScheduleSchema,
    ScheduleCreateSchema,
    TagSchema,
    SecretSchema,
    SecretSetSchema,
    GlobalCredentialSchema,
    GlobalCredentialCreateSchema,
    GlobalCredentialUpdateSchema,
)
from .security import authenticate_bearer_token


def parse_execution_output(stdout: str) -> dict | None:
    """Try to parse stdout as JSON, returning None if parsing fails.
    
    Args:
        stdout: The stdout string from script execution
        
    Returns:
        Parsed JSON dict if stdout is valid JSON, None otherwise
    """
    if not stdout:
        return None
    try:
        result = json.loads(stdout.strip())
        if isinstance(result, dict):
            return result
        return None
    except (json.JSONDecodeError, ValueError):
        return None

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
    from app.models import Tag, GlobalCredential
    
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
        elif attr == "credentials":
            # Handle credentials - only assign existing credentials owned by user
            if value is not None:
                credentials = []
                for cred_id in value:
                    try:
                        cred = GlobalCredential.objects.get(
                            id=cred_id, user=request.auth.user
                        )
                        credentials.append(cred)
                    except GlobalCredential.DoesNotExist:
                        pass
                script.credentials.set(credentials)
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


@router.post("/scripts/{script_id}/execute", auth=None)
def execute_script_api(request, script_id: int):
    """Execute a script and wait for completion.

    Returns only the parsed JSON result if the script output is valid JSON.
    Requires authentication. For public scripts, use the webhook endpoint instead.
    """
    import time
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

    # Wait for execution to complete (poll every 0.5s, up to 60s)
    deadline = time.time() + 60
    while time.time() < deadline:
        execution.refresh_from_db()
        if execution.status in ("success", "failed", "cancelled"):
            break
        time.sleep(0.5)

    # Try to parse stdout as JSON
    result = parse_execution_output(execution.stdout)

    # For failed executions, include error details
    if execution.status == "failed":
        return {
            "output": execution.stdout or "",
            "error": execution.error_message or "",
        }

    # Only return the result when available
    if result is not None:
        return {"result": result}
    
    # For non-JSON output, return the stdout output
    return {"output": execution.stdout or ""}


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
    "/executions/{execution_id}", response=ExecutionResultSchema, auth=APITokenAuth()
)
def get_execution(request, execution_id: int):
    """Get execution details with parsed JSON result if available."""
    execution = get_object_or_404(ScriptExecution, id=execution_id)

    # Check permission
    if execution.script.owner != request.auth.user:
        return {"error": "Permission denied"}, 403

    # Try to parse stdout as JSON
    result = parse_execution_output(execution.stdout)

    return {
        "id": execution.id,
        "script_id": execution.script_id,
        "status": execution.status,
        "trigger_type": execution.trigger_type,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
        "duration_seconds": execution.duration_seconds,
        "exit_code": execution.exit_code,
        "created_at": execution.created_at,
        "stdout": "" if result else (execution.stdout or ""),
        "stderr": execution.stderr or "",
        "error_message": execution.error_message or "",
        "result": result,
    }


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


# Script Secrets API endpoints
@router.get("/scripts/{script_id}/secrets", response=List[SecretSchema], auth=APITokenAuth())
def list_script_secrets_api(request, script_id: int):
    """List secret names for a script."""
    from app.services.secret_store import list_script_secrets

    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)

    names = list_script_secrets(script_id)
    return [{"name": name} for name in names]


@router.get("/scripts/{script_id}/secrets/{secret_name}", auth=APITokenAuth())
def get_script_secret_api(request, script_id: int, secret_name: str):
    """Get a secret value for a script."""
    from app.services.secret_store import get_script_secret

    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)

    value = get_script_secret(script_id, secret_name)
    if value is None:
        return {"error": "Secret not found"}, 404

    return {"name": secret_name, "value": value}


@router.post("/scripts/{script_id}/secrets", auth=APITokenAuth())
def set_script_secret_api(request, script_id: int, payload: SecretSetSchema):
    """Set/update a script secret."""
    from app.services.secret_store import set_script_secret

    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)

    name = payload.name.strip()
    if not name:
        return {"error": "Secret name is required"}, 400

    # Basic validation for secret name
    import re
    if not re.match(r"^[A-Z0-9_\-]+$", name, re.I):
        return {
            "error": "Invalid name (use letters, numbers, - or _)"
        }, 400

    set_script_secret(script_id, name, payload.value)
    return {"success": True, "name": name}


@router.delete("/scripts/{script_id}/secrets/{secret_name}", auth=APITokenAuth())
def delete_script_secret_api(request, script_id: int, secret_name: str):
    """Delete a script secret."""
    from app.services.secret_store import delete_script_secret

    script = get_object_or_404(Script, id=script_id, owner=request.auth.user)

    deleted = delete_script_secret(script_id, secret_name)
    if not deleted:
        return {"error": "Secret not found"}, 404

    return {"success": True}


# Global Credential API endpoints
@router.get("/credentials", response=List[GlobalCredentialSchema], auth=APITokenAuth())
def list_credentials(request):
    """List all global credentials for the current user."""
    from app.models import GlobalCredential
    
    credentials = GlobalCredential.objects.filter(
        user=request.auth.user
    ).order_by("-updated_at")
    return credentials


@router.post("/credentials", response=GlobalCredentialSchema, auth=APITokenAuth())
def create_credential(request, payload: GlobalCredentialCreateSchema):
    """Create a new global credential."""
    from app.models import GlobalCredential, CredentialType
    
    # Build the credential data based on type
    credential_data = {}
    
    if payload.credential_type == CredentialType.API_KEY:
        if not payload.api_key:
            return {"error": "api_key is required for this credential type"}, 400
        credential_data["api_key"] = payload.api_key
    elif payload.credential_type == CredentialType.BEARER_TOKEN:
        if not payload.token:
            return {"error": "token is required for this credential type"}, 400
        credential_data["token"] = payload.token
    elif payload.credential_type == CredentialType.BASIC_AUTH:
        if not payload.username or not payload.password:
            return {"error": "username and password are required for basic auth"}, 400
        credential_data["username"] = payload.username
        credential_data["password"] = payload.password
    elif payload.credential_type == CredentialType.OAUTH_CLIENT_CREDENTIALS:
        if not payload.client_id or not payload.client_secret or not payload.token_url:
            return {"error": "client_id, client_secret, and token_url are required"}, 400
        credential_data["client_id"] = payload.client_id
        credential_data["client_secret"] = payload.client_secret
        credential_data["token_url"] = payload.token_url
    elif payload.credential_type == CredentialType.GENERIC:
        if not payload.key or not payload.value:
            return {"error": "key and value are required for generic credentials"}, 400
        credential_data["key"] = payload.key
        credential_data["value"] = payload.value
    
    credential = GlobalCredential.objects.create(
        user=request.auth.user,
        name=payload.name,
        credential_type=payload.credential_type,
    )
    credential.set_encrypted_data(credential_data)
    credential.save()
    
    return credential


@router.get("/credentials/{credential_id}", response=GlobalCredentialSchema, auth=APITokenAuth())
def get_credential(request, credential_id: int):
    """Get a specific global credential (masked value only)."""
    from app.models import GlobalCredential
    
    credential = get_object_or_404(
        GlobalCredential, 
        id=credential_id, 
        user=request.auth.user
    )
    return credential


@router.put("/credentials/{credential_id}", response=GlobalCredentialSchema, auth=APITokenAuth())
def update_credential(request, credential_id: int, payload: GlobalCredentialUpdateSchema):
    """Update a global credential."""
    from app.models import GlobalCredential, CredentialType
    
    credential = get_object_or_404(
        GlobalCredential, 
        id=credential_id, 
        user=request.auth.user
    )
    
    # Update name if provided
    if payload.name:
        credential.name = payload.name
    
    # Update credential data if any secret fields are provided
    update_data = {}
    existing_data = credential.get_decrypted_data()
    
    if payload.credential_type == CredentialType.API_KEY or credential.credential_type == CredentialType.API_KEY:
        if payload.api_key:
            update_data["api_key"] = payload.api_key
    elif payload.credential_type == CredentialType.BEARER_TOKEN or credential.credential_type == CredentialType.BEARER_TOKEN:
        if payload.token:
            update_data["token"] = payload.token
    elif payload.credential_type == CredentialType.BASIC_AUTH or credential.credential_type == CredentialType.BASIC_AUTH:
        if payload.username:
            update_data["username"] = payload.username
        if payload.password:
            update_data["password"] = payload.password
    elif payload.credential_type == CredentialType.OAUTH_CLIENT_CREDENTIALS or credential.credential_type == CredentialType.OAUTH_CLIENT_CREDENTIALS:
        if payload.client_id:
            update_data["client_id"] = payload.client_id
        if payload.client_secret:
            update_data["client_secret"] = payload.client_secret
        if payload.token_url:
            update_data["token_url"] = payload.token_url
    elif payload.credential_type == CredentialType.GENERIC or credential.credential_type == CredentialType.GENERIC:
        if payload.key:
            update_data["key"] = payload.key
        if payload.value:
            update_data["value"] = payload.value
    
    if update_data:
        # Merge with existing data, keeping unchanged fields
        merged_data = {**existing_data, **update_data}
        credential.set_encrypted_data(merged_data)
    
    credential.save()
    return credential


@router.delete("/credentials/{credential_id}", auth=APITokenAuth())
def delete_credential(request, credential_id: int):
    """Delete a global credential."""
    from app.models import GlobalCredential
    
    credential = get_object_or_404(
        GlobalCredential, 
        id=credential_id, 
        user=request.auth.user
    )
    credential.delete()
    return {"success": True}
