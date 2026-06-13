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

router = Router(tags=["MCP"])


def authenticate_bearer_token(request):
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    if not auth_header:
        return None

    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return APITokenAuth().authenticate(request, parts[1])


def _build_mcp_manifest(script: Script) -> dict:
    tool_name = f"run_script_{script.id}"
    return {
        "script_id": script.id,
        "name": script.name,
        "description": script.description or "Run this script through the MCP tool interface.",
        "language": script.language,
        "tool_name": tool_name,
        "tool_description": (
            f"Execute script '{script.name}' ({script.language}). "
            + (script.description or "No description available.")
        ).strip(),
        "parameters": {
            "type": "object",
            "properties": {
                "input_text": {
                    "type": "string",
                    "description": "Optional text input provided to the script via stdin.",
                },
                "timeout_seconds": {
                    "type": "number",
                    "description": "Maximum execution time in seconds.",
                },
            },
            "required": [],
        },
    }


@router.get("/scripts", response=List[MCPToolManifestSchema], auth=APITokenAuth())
def list_mcp_manifests(request):
    """List MCP-compatible tool manifests for a user's scripts."""
    scripts = Script.objects.filter(owner=request.auth.user).order_by("-updated_at")
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
    """Get the MCP-compatible tool manifest for a script."""
    script = get_object_or_404(Script, id=script_id)
    api_token = authenticate_bearer_token(request)

    if script.is_public:
        return _build_mcp_manifest(script)

    if api_token is None:
        return {"error": "Authentication required"}, 401

    if script.owner_id != api_token.user_id:
        return {"error": "Permission denied"}, 403

    return _build_mcp_manifest(script)


@router.post("/scripts/{script_id}/invoke", response=MCPInvokeResponseSchema, auth=None)
def invoke_script_mcp(request, script_id: int, payload: MCPInvokeRequestSchema):
    """Invoke a script through the MCP-compatible execution interface."""
    script = get_object_or_404(Script, id=script_id)
    api_token = authenticate_bearer_token(request)

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

    return execution
