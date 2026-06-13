"""
ScriptDash MCP Server – OpenAI / ChatGPT compatible.

Speaks the Model Context Protocol (MCP) over Streamable HTTP transport.
Exposes tools for discovering, reading, and executing scripts.
Supports OAuth2 bearer-token authentication via the APIToken model.
"""

from __future__ import annotations

import json
import os
import logging

logger = logging.getLogger(__name__)

# ── Bootstrap Django before importing models ─────────────────────────────
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")
# Allow sync ORM calls from thread-pool context (FastMCP runs sync tools in
# threads, but Django's async-safe detection trips on the async outer scope).
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
import django

django.setup()

# ── Imports ──────────────────────────────────────────────────────────────
from typing import Any

from django.contrib.auth import get_user_model
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp.server import TransportSecuritySettings
from mcp.types import TextContent

from app.models import APIToken, Script
from app.services.script_runner import ScriptRunner

User = get_user_model()

# ── OAuth Token Verifier ─────────────────────────────────────────────────


class ScriptDashTokenVerifier(TokenVerifier):
    """Validates APIToken model entries as OAuth Bearer tokens."""

    async def verify_token(self, token: str) -> AccessToken | None:
        """Return an AccessToken if the APIToken is valid."""
        from asgiref.sync import sync_to_async

        logger.info("ScriptDashTokenVerifier: verifying token prefix=%s...", token[:12])

        @sync_to_async
        def _lookup():
            try:
                return APIToken.objects.select_related("user").get(
                    token=token, is_active=True
                )
            except APIToken.DoesNotExist:
                return None

        api_token = await _lookup()
        if api_token is None:
            logger.warning("ScriptDashTokenVerifier: token not found or inactive")
            return None

        logger.info("ScriptDashTokenVerifier: token valid for user %s", api_token.user.username)

        # Touch last_used
        @sync_to_async
        def _touch():
            APIToken.objects.filter(pk=api_token.pk).update(
                last_used=django.utils.timezone.now()
            )

        await _touch()

        return AccessToken(
            token=api_token.token,
            client_id=f"user_{api_token.user_id}",
            scopes=["script:read", "script:write", "script:execute"],
            subject=str(api_token.user_id),
        )


# ── Helper: resolve user from a verified token ──────────────────────────


def _get_user_from_context(context: Context) -> User | None:
    """Extract the authenticated Django user from the MCP Context.

    FastMCP stores auth info on the ASGI scope after OAuth verification.
    The scope is accessible through the request object on the context.
    ``scope["user"]`` is an ``AuthenticatedUser`` with an ``access_token``
    property whose ``subject`` field holds the user PK.
    """
    rc = context.request_context
    if rc is None or rc.request is None:
        return None

    scope = getattr(rc.request, "scope", None)
    if scope is None:
        return None

    auth_user = scope.get("user")
    if auth_user is None:
        return None

    token = getattr(auth_user, "access_token", None)
    if token is None:
        return None

    subject = getattr(token, "subject", None)
    if subject is None:
        return None

    try:
        uid = int(subject)
        return User.objects.get(pk=uid)
    except (ValueError, User.DoesNotExist):
        return None


def _error(msg: str) -> dict:
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


# ── Base server URL (injected via env or settings) ───────────────────────
_SERVER_BASE = os.environ.get(
    "MCP_SERVER_URL",
    os.environ.get("SCRIPTDASH_URL", "http://localhost:8003"),
)

# ── FastMCP Server with OAuth ────────────────────────────────────────────

mcp = FastMCP(
    name="ScriptDash",
    instructions=(
        "ScriptDash MCP server – manage and execute Python/bash scripts. "
        "Search for scripts, inspect recent executions, or invoke a script by ID. "
        "Before running a script, call list_executions or search to validate the script ID."
    ),
    # ── OAuth configuration ──────────────────────────────────────────────
    # Tells ChatGPT which OAuth authorization server to use.
    auth=AuthSettings(
        issuer_url=f"{_SERVER_BASE}",
        resource_server_url=f"{_SERVER_BASE}",  # NOT /mcp – metadata is at root
        required_scopes=["script:read", "script:write", "script:execute"],
        # Allow ChatGPT to register itself as an OAuth client automatically
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            default_scopes=["script:read", "script:write", "script:execute"],
        ),
    ),
    token_verifier=ScriptDashTokenVerifier(),
    # Use stateless HTTP to avoid TaskGroup lifecycle requirement when
    # mounted inside Daphne (which doesn't support Starlette lifespan).
    stateless_http=True,
    # Allow the public domain for Host-header validation
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["scriptdash.bhm.li", "*.bhm.li"],
        allowed_origins=["*"],
    ),
)


# ── Tools ────────────────────────────────────────────────────────────────


@mcp.tool(
    name="search",
    description="Search your ScriptDash scripts by name or description keyword.",
    annotations={"readOnlyHint": True},
)
def search_scripts(query: str, context: Context) -> dict:
    """Search scripts matching the query. Returns matching script summaries."""
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")

    scripts = list(
        Script.objects.filter(owner=user)
        .filter(name__icontains=query)
        | Script.objects.filter(owner=user).filter(description__icontains=query)
        .order_by("-updated_at")[:20]
    )

    results = [_script_to_dict(s) for s in scripts]
    structured = {"results": results}

    return {
        "structuredContent": structured,
        "content": [TextContent(type="text", text=json.dumps(structured))],
        "_meta": {"total": len(results)},
    }


@mcp.tool(
    name="fetch",
    description="Fetch full details and source code for a specific script by ID.",
    annotations={"readOnlyHint": True},
)
def fetch_script(script_id: int, context: Context) -> dict:
    """Retrieve the full details, code, and dependencies of a script."""
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found")

    structured = {
        "id": script.id,
        "title": script.name,
        "text": script.code,
        "url": "",
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
        "content": [TextContent(type="text", text=json.dumps(structured))],
        "_meta": {"script_id": script.id},
    }


@mcp.tool(
    name="list_scripts",
    description="List all of your ScriptDash scripts with their latest status.",
    annotations={"readOnlyHint": True},
)
def list_scripts(context: Context) -> dict:
    """Return a list of all scripts owned by the authenticated user."""
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")

    scripts = list(Script.objects.filter(owner=user).order_by("-updated_at"))
    results = [_script_to_dict(s) for s in scripts]
    structured = {"scripts": results}

    return {
        "structuredContent": structured,
        "content": [TextContent(type="text", text=json.dumps(structured))],
        "_meta": {"total": len(results)},
    }


@mcp.tool(
    name="list_executions",
    description="List recent executions for a script by ID.",
    annotations={"readOnlyHint": True},
)
def list_executions(script_id: int, context: Context) -> dict:
    """Return the 20 most recent executions for a given script."""
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found")

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
        "content": [TextContent(type="text", text=json.dumps(structured))],
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
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found")

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
                text="\n\n".join(text_parts)
                if text_parts
                else f"Script finished with status: {execution.status}",
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
    """Return the FastMCP streamable_http_app as a Starlette ASGI app.

    ``stateless_http=True`` avoids persistent sessions, but the SDK still
    needs ``_task_group`` initialised — the stateless handler calls
    ``_task_group.start()``.  We run ``session_manager.run()`` in a
    persistent background task via ``anyio``.
    """
    import anyio
    import asyncio

    app = mcp.streamable_http_app()
    sm = mcp.session_manager

    if sm._task_group is None:
        async def _enter_run():
            # Enter the session manager's run() context and keep it alive
            async with sm.run():
                # Sleep forever so the task group stays active
                await anyio.sleep_forever()

        # Kick off the background task in the default event loop (Daphne's loop)
        # This must run in the same event loop Daphne uses.
        _original_app = app

        async def _lazy_init(scope, receive, send):
            if sm._task_group is None or not hasattr(sm._task_group, 'start'):
                # First request – initialise the task group
                tg = anyio.create_task_group()
                await tg.__aenter__()
                sm._task_group = tg
            await _original_app(scope, receive, send)

        return _lazy_init  # type: ignore[return-value]

    return app
