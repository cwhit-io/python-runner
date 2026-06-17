from ninja import Router
from typing import List
from django.shortcuts import get_object_or_404
from app.auth import APITokenAuth
from app.models import Script
from app.services.script_runner import ScriptRunner
from .mcp_schemas import (
    MCPDiscoverySchema,
    MCPInvokeRequestSchema,
    MCPInvokeResponseSchema,
    MCPToolManifestSchema,
)
from .security import authenticate_bearer_token
from app.mcp_server import _convert_script_name_to_tool_name, _get_default_input_schema


router = Router(tags=["MCP"])


def _build_mcp_manifest(script: Script) -> dict:
    """Build an MCP tool manifest for a script using the new naming and schema logic."""
    tool_name = _convert_script_name_to_tool_name(script.name, script.mcp_tool_name)
    
    # Use custom input schema if available, otherwise use default
    input_schema = script.input_schema if script.input_schema else _get_default_input_schema()
    
    return {
        "script_id": script.id,
        "name": script.name,
        "description": script.description or f"Run the ScriptDash script: {script.name}.",
        "language": script.language,
        "tool_name": tool_name,
        "tool_description": (
            f"Execute script '{script.name}' ({script.language}). "
            + (script.description or f"Run the ScriptDash script: {script.name}.")
        ).strip(),
        "parameters": input_schema,
        "is_destructive": script.is_destructive,
    }


@router.get("/scripts", response=List[MCPToolManifestSchema], auth=APITokenAuth())
def list_mcp_manifests(request):
    """List MCP-compatible tool manifests for a user's scripts that are exposed to MCP."""
    # Only show scripts where expose_to_mcp is True
    scripts = Script.objects.filter(
        owner=request.auth.user, 
        expose_to_mcp=True
    ).order_by("-updated_at")
    return [_build_mcp_manifest(script) for script in scripts]


@router.get("/discovery", response=MCPDiscoverySchema, auth=None)
def discover_mcp_resources(request):
    """Discover available MCP script resources."""
    scripts = Script.objects.filter(is_public=True).order_by("-updated_at")

    resources = []
    for script in scripts:
        resources.append(
            {
                "id": f"scriptdash-script-{script.id}",
                "name": script.name,
                "description": script.description or "Public ScriptDash script",
                "manifest_url": request.build_absolute_uri(
                    f"/api/v1/mcp/scripts/{script.id}/manifest"
                ),
                "tool_type": "script",
            }
        )

    return {"resources": resources}


@router.get("/scripts/{script_id}/manifest", response=MCPToolManifestSchema, auth=None)
def get_mcp_manifest(request, script_id: int):
    """Get the MCP-compatible tool manifest for a script.
    
    Only returns manifest for scripts that are exposed to MCP.
    """
    script = get_object_or_404(Script, id=script_id)
    api_token = authenticate_bearer_token(request)
    
    # Check if script is exposed to MCP
    if not script.expose_to_mcp:
        return {"error": "Script is not exposed to MCP"}, 404

    if script.is_public:
        return _build_mcp_manifest(script)

    if api_token is None:
        return {"error": "Authentication required"}, 401

    if script.owner_id != api_token.user_id:
        return {"error": "Permission denied"}, 403

    return _build_mcp_manifest(script)


@router.post("/scripts/{script_id}/invoke", response=MCPInvokeResponseSchema, auth=None)
def invoke_script_mcp(request, script_id: int, payload: MCPInvokeRequestSchema):
    """Invoke a script through the MCP-compatible execution interface.
    
    Only allows execution of scripts that are exposed to MCP.
    """
    script = get_object_or_404(Script, id=script_id)
    api_token = authenticate_bearer_token(request)
    
    # Check if script is exposed to MCP - this is the key security check
    if not script.expose_to_mcp:
        return {"error": "Script is not exposed to MCP"}, 403
    
    # For non-public scripts, require authentication
    if not script.is_public:
        if api_token is None:
            return {"error": "Authentication required"}, 401
        if script.owner_id != api_token.user_id:
            return {"error": "Permission denied"}, 403

    runner = ScriptRunner(script)
    execution = runner.execute(
        triggered_by=api_token.user if api_token else None,
        trigger_type="mcp",
        timeout_seconds=payload.timeout_seconds,
        input_text=payload.input_text,
    )

    return {
        "id": execution.id,
        "script_id": script.id,
        "status": execution.status,
        "trigger_type": execution.trigger_type,
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
    }
