"""
ScriptDash MCP Server – OpenAI / ChatGPT compatible.

Speaks the Model Context Protocol over Streamable HTTP transport.
Exposes tools for discovering, reading, and executing scripts.
Supports OAuth2 bearer-token authentication (APIToken model).
"""

from __future__ import annotations

import json
import os
import sys

# ── Bootstrap Django before importing models ─────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
import django

django.setup()

# ── Imports ──────────────────────────────────────────────────────────────
from typing import Any, Sequence

from django.contrib.auth import get_user_model
from mcp.server.fastmcp import FastMCP, Context
from mcp.types import TextContent, EmbeddedResource
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.models import APIToken, Script, ScriptExecution
from app.services.script_runner import ScriptRunner

User = get_user_model()

# ── FastMCP Server ───────────────────────────────────────────────────────

mcp = FastMCP(
    name="ScriptDash",
    instructions=(
        "ScriptDash MCP server – manage and execute Python/bash scripts. "
        "Search for scripts, inspect recent executions, or invoke a script by ID. "
        "Before running a script, call list_executions or search to validate the script ID."
    ),
)

# ── Auth Middleware ───────────────────────────────────────────────────────


class BearerTokenAuthMiddleware(BaseHTTPMiddleware):
    """Extract APIToken from Authorization header and store it in request.state."""

    async def dispatch(self, request: Request, call_next):
        auth = request.headers.get("authorization") or request.headers.get("Authorization", "")
        token_str = ""
        if auth.startswith("Bearer "):
            token_str = auth[7:]

        if token_str:
            try:
                token = await _async_get_token(token_str)
                request.state.api_token = token
                request.state.user = token.user if token else None
            except Exception:
                request.state.api_token = None
                request.state.user = None
        else:
            request.state.api_token = None
            request.state.user = None

        return await call_next(request)


async def _async_get_token(token_str: str) -> APIToken | None:
    """Synchronously look up a token – safe in async context via sync_to_async."""
    from asgiref.sync import sync_to_async

    @sync_to_async
    def _lookup():
        try:
            return APIToken.objects.select_related("user").get(
                token=token_str, is_active=True
            )
        except APIToken.DoesNotExist:
            return None

    return await _lookup()


def get_authenticated_user(context: Context) -> User | None:
    """Extract the authenticated user from the Context's request state."""
    rc = context.request_context
    if rc is None or rc.request is None:
        return None
    return getattr(rc.request.state, "user", None)


def _error(msg: str, status: int = 400) -> dict:
    return {
        "content": [TextContent(type="text", text=msg)],
        "isError": True,
    }


# ── Helper: serialize a Script object ────────────────────────────────────


def _script_to_dict(s: Script) -> dict:
    return {
        "id": s.id,
        "name": s.name,
        "description": s.description or "",
        "language": s.language,
        "is_public": s.is_public,
        "last_status": s.last_status,
        "last_run": s.last_run.isoformat() if s.last_run else None,
        "execution_count": s.execution_count,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


# ── Tools ────────────────────────────────────────────────────────────────


@mcp.tool(
    name="search",
    description="Search your ScriptDash scripts by name or description keyword.",
    annotations={"readOnlyHint": True},
)
def search_scripts(query: str, context: Context) -> dict:
    """Search scripts matching the query. Returns matching script summaries."""
    user = get_authenticated_user(context)
    if user is None:
        return _error("Authentication required", 401)

    scripts = list(
        Script.objects.filter(owner=user)
        .filter(name__icontains=query) | Script.objects.filter(owner=user).filter(
            description__icontains=query
        )
        .order_by("-updated_at")[:20]
    )

    results = [_script_to_dict(s) for s in scripts]
    structured = {"results": results}

    return {
        "structuredContent": structured,
        "content": [
            TextContent(type="text", text=json.dumps(structured)),
        ],
        "_meta": {"total": len(results)},
    }


@mcp.tool(
    name="fetch",
    description="Fetch full details and source code for a specific script by ID.",
    annotations={"readOnlyHint": True},
)
def fetch_script(script_id: int, context: Context) -> dict:
    """Retrieve the full details, code, and dependencies of a script."""
    user = get_authenticated_user(context)
    if user is None:
        return _error("Authentication required", 401)

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found", 404)

    structured = {
        "id": script.id,
        "title": script.name,
        "text": script.code,
        "url": "",  # no canonical external URL
        "metadata": {
            "language": script.language,
            "description": script.description or "",
            "dependencies": script.dependencies or "",
            "last_status": script.last_status,
            "execution_count": script.execution_count,
        },
    }

    return {
        "structuredContent": structured,
        "content": [
            TextContent(type="text", text=json.dumps(structured)),
        ],
        "_meta": {"script_id": script.id},
    }


@mcp.tool(
    name="list_scripts",
    description="List all of your ScriptDash scripts with their latest status.",
    annotations={"readOnlyHint": True},
)
def list_scripts(context: Context) -> dict:
    """Return a list of all scripts owned by the authenticated user."""
    user = get_authenticated_user(context)
    if user is None:
        return _error("Authentication required", 401)

    scripts = list(Script.objects.filter(owner=user).order_by("-updated_at"))
    results = [_script_to_dict(s) for s in scripts]
    structured = {"scripts": results}

    return {
        "structuredContent": structured,
        "content": [
            TextContent(type="text", text=json.dumps(structured)),
        ],
        "_meta": {"total": len(results)},
    }


@mcp.tool(
    name="list_executions",
    description="List recent executions for a script by ID.",
    annotations={"readOnlyHint": True},
)
def list_executions(script_id: int, context: Context) -> dict:
    """Return the 20 most recent executions for a given script."""
    user = get_authenticated_user(context)
    if user is None:
        return _error("Authentication required", 401)

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found", 404)

    executions = list(script.executions.order_by("-created_at")[:20])  # type: ignore[attr-defined]
    execs = []
    for e in executions:
        execs.append(
            {
                "id": e.id,
                "status": e.status,
                "trigger_type": e.trigger_type,
                "started_at": e.started_at.isoformat() if e.started_at else None,
                "completed_at": e.completed_at.isoformat() if e.completed_at else None,
                "duration_seconds": e.duration_seconds,
                "exit_code": e.exit_code,
            }
        )

    structured = {"script_id": script_id, "executions": execs}
    return {
        "structuredContent": structured,
        "content": [
            TextContent(type="text", text=json.dumps(structured)),
        ],
        "_meta": {"total": len(execs)},
    }


@mcp.tool(
    name="run_script",
    description="Execute a script and return the result. Provide optional stdin input and timeout.",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
def run_script(
    script_id: int,
    context: Context,
    input_text: str = "",
    timeout_seconds: int = 60,
) -> dict:
    """Execute a script by ID.

    Args:
        script_id: The ID of the script to run.
        input_text: Optional text to feed to the script via stdin.
        timeout_seconds: Max execution time in seconds (default 60).
    """
    user = get_authenticated_user(context)
    if user is None:
        return _error("Authentication required", 401)

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found", 404)

    runner = ScriptRunner(script)
    execution = runner.execute(
        triggered_by=user,
        trigger_type="mcp",
        timeout_seconds=timeout_seconds or None,
        input_text=input_text or None,
    )

    # Wait up to timeout_seconds for completion (poll every 0.5s)
    import time

    deadline = time.time() + (timeout_seconds or 60)
    while time.time() < deadline:
        execution.refresh_from_db()
        if execution.status in ("success", "failed", "cancelled"):
            break
        time.sleep(0.5)

    structured = {
        "id": execution.id,
        "script_id": script.id,
        "status": execution.status,
        "stdout": execution.stdout or "",
        "stderr": execution.stderr or "",
        "error_message": execution.error_message or "",
        "exit_code": execution.exit_code,
        "duration_seconds": execution.duration_seconds,
    }

    text_parts = []
    if execution.stdout:
        text_parts.append(f"--- stdout ---\n{execution.stdout}")
    if execution.stderr:
        text_parts.append(f"--- stderr ---\n{execution.stderr}")
    if execution.error_message:
        text_parts.append(f"--- error ---\n{execution.error_message}")

    return {
        "structuredContent": structured,
        "content": [
            TextContent(
                type="text",
                text="\n\n".join(text_parts) if text_parts else f"Script finished with status: {execution.status}",
            ),
        ],
        "_meta": {
            "execution_id": execution.id,
            "script_id": script.id,
            "status": execution.status,
        },
    }


# ── ASGI app factory ─────────────────────────────────────────────────────


def create_mcp_asgi_app() -> "Starlette":
    """Wrap the FastMCP streamable_http_app with auth middleware."""
    from starlette.applications import Starlette
    from starlette.routing import Mount

    inner = mcp.streamable_http_app()
    routes = [
        Mount(
            path="",
            app=BearerTokenAuthMiddleware(inner),
        ),
    ]
    return Starlette(routes=routes)
