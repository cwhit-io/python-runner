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
from typing import Annotated

from django.contrib.auth import get_user_model
from mcp.server.fastmcp import FastMCP, Context
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.fastmcp.server import TransportSecuritySettings
from mcp.types import TextContent, CallToolResult

from app.models import APIToken, Script, ScriptExecution, ScriptSchedule, Tag
from app.services.script_runner import ScriptRunner
from app.mcp_schemas import (
    ScriptPropertySchema,
    ExecutionPropertySchema,
    SchedulePropertySchema,
    TagPropertySchema,
    SearchScriptsOutput,
    FetchScriptOutput,
    ListScriptsOutput,
    ListExecutionsOutput,
    RunScriptOutput,
    GetExecutionOutput,
    DeleteScriptOutput,
    ListSchedulesOutput,
    DeleteScheduleOutput,
    ListTagsOutput,
    DeleteTagOutput,
    ListScriptSecretsOutput,
    GetScriptSecretOutput,
    SetScriptSecretOutput,
    DeleteScriptSecretOutput,
)

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
        "expose_to_mcp": s.expose_to_mcp,
        "mcp_tool_name": s.mcp_tool_name or "",
        "is_destructive": s.is_destructive,
        "has_input_schema": bool(s.input_schema),
        "last_status": s.last_status,
        "last_run": s.last_run.isoformat() if s.last_run else None,
        "execution_count": s.execution_count,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


# ── MCP Tool Name Conversion Helper ───────────────────────────────────────


def _convert_script_name_to_tool_name(script_name: str, custom_tool_name: str = None) -> str:
    """Convert a script name to a valid MCP tool name.
    
    Uses lowercase snake_case and prefixes with 'scriptdash_' unless a custom
    tool name is provided.
    
    Examples:
        "Newsletter Builder" -> "scriptdash_newsletter_builder"
        "MyScript" -> "scriptdash_my_script"
        "API Script!" -> "scriptdash_api_script"
        With custom "newsletter_tool" -> "newsletter_tool" (no prefix)
    """
    import re
    
    if custom_tool_name:
        # Validate the custom tool name - no prefix added
        name = custom_tool_name.lower().strip()
        # Replace spaces and special characters with underscores
        name = re.sub(r'[^a-z0-9_]', '_', name)
        # Remove multiple consecutive underscores
        name = re.sub(r'_+', '_', name)
        # Remove leading/trailing underscores
        name = name.strip('_')
        # Ensure it doesn't start with a number (add script prefix for validity)
        if name and name[0].isdigit():
            name = f"script_{name}"
        return name or "tool"
    
    # Auto-generate from script name with scriptdash_ prefix
    # Split camelCase: "MyScript" -> "My_Script" then lowercase -> "my_script"
    split_camel = re.sub(r'([a-z])([A-Z])', r'\1_\2', script_name)
    name = split_camel.lower().strip()
    
    # Replace non-alphanumeric characters with underscores
    name = re.sub(r'[^a-z0-9_]+', '_', name)
    # Remove multiple consecutive underscores
    name = re.sub(r'_+', '_', name)
    # Remove leading/trailing underscores
    name = name.strip('_')
    
    # The scriptdash_ prefix makes names starting with numbers valid
    return f"scriptdash_{name}" if name else "scriptdash_script"


# ── Default Input Schema Generator ───────────────────────────────────────


def _get_default_input_schema() -> dict:
    """Generate the default input schema for scripts without a custom schema.
    
    Returns a JSON Schema with:
        - optional input_text string
        - optional timeout_seconds integer (default 60)
    """
    return {
        "type": "object",
        "properties": {
            "input_text": {
                "type": "string",
                "description": "Optional text input to provide to the script via stdin.",
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "Maximum execution time in seconds.",
                "default": 60,
                "minimum": 1,
                "maximum": 3600,
            },
        },
        "required": [],
    }


# ── MCP Tool Cache ─────────────────────────────────────────────────────────


_mcp_tool_cache: dict[int, list[dict]] = {}
_mcp_tool_cache_timestamp: float = 0
_MCP_TOOL_CACHE_TTL_SECONDS = 30  # Short cache TTL for refresh behavior


def _get_mcp_tools_for_user(user_id: int) -> list[dict]:
    """Get MCP tool definitions for a user's exposed scripts.
    
    Uses caching to avoid hitting the database on every request.
    Only returns scripts where expose_to_mcp=True.
    """
    global _mcp_tool_cache, _mcp_tool_cache_timestamp
    import time
    
    now = time.time()
    if (user_id in _mcp_tool_cache and 
        now - _mcp_tool_cache_timestamp < _MCP_TOOL_CACHE_TTL_SECONDS):
        return _mcp_tool_cache[user_id]
    
    scripts = list(Script.objects.filter(
        owner_id=user_id,
        expose_to_mcp=True
    ).order_by("name"))
    
    tools = []
    for script in scripts:
        tool_name = _convert_script_name_to_tool_name(script.name, script.mcp_tool_name)
        tools.append({
            "script_id": script.id,
            "tool_name": tool_name,
            "mcp_tool_name": script.mcp_tool_name,
            "description": script.description or f"Run the ScriptDash script: {script.name}.",
            "is_destructive": script.is_destructive,
            "input_schema": script.input_schema if script.input_schema else _get_default_input_schema(),
        })
    
    _mcp_tool_cache[user_id] = tools
    _mcp_tool_cache_timestamp = now
    return tools


def _invalidate_mcp_tool_cache(user_id: int = None):
    """Invalidate the MCP tool cache for a specific user or all users."""
    global _mcp_tool_cache, _mcp_tool_cache_timestamp
    if user_id is not None:
        _mcp_tool_cache.pop(user_id, None)
    else:
        _mcp_tool_cache.clear()
    _mcp_tool_cache_timestamp = 0


# ── Dynamic MCP Tool Registration ────────────────────────────────────────


# Track registered dynamic tools for cleanup
_registered_dynamic_tool_names: set[str] = set()


def _create_dynamic_tool_function(script_id: int, is_destructive: bool):
    """Create a tool function that executes a specific script.
    
    This creates a closure that captures the script_id and can be registered
    as an MCP tool.
    """
    def dynamic_tool_func(
        context: Context = None,
        input_text: str = "",
        timeout_seconds: int = 60,
    ):
        """Execute the MCP-exposed script.
        
        Args:
            input_text: Optional text input for the script via stdin.
            timeout_seconds: Maximum execution time (default 60).
        """
        user = _get_user_from_context(context)
        if user is None:
            return _error("Authentication required")
        
        try:
            script = Script.objects.get(id=script_id, owner=user)
        except Script.DoesNotExist:
            return _error(f"Script {script_id} not found or not accessible")
        
        runner = ScriptRunner(script)
        execution = runner.execute(
            triggered_by=user,
            trigger_type="mcp",
            timeout_seconds=timeout_seconds or None,
            input_text=input_text or None,
        )
        
        # Wait for completion (poll every 0.5s)
        import time
        deadline = time.time() + (timeout_seconds or 60)
        while time.time() < deadline:
            execution.refresh_from_db()
            if execution.status in ("success", "failed", "cancelled"):
                break
            time.sleep(0.5)
        
        text_parts = []
        if execution.stdout:
            text_parts.append(f"--- stdout ---\n{execution.stdout}")
        if execution.stderr:
            text_parts.append(f"--- stderr ---\n{execution.stderr}")
        if execution.error_message:
            text_parts.append(f"--- error ---\n{execution.error_message}")
        
        return {
            "content": [TextContent(type="text", text="\n".join(text_parts) or "Execution completed.")],
            "isError": execution.status == "failed",
            # Include structured output for clients that can parse it
            "structuredContent": {
                "execution_id": execution.id,
                "script_id": script_id,
                "status": execution.status,
                "stdout": execution.stdout or "",
                "stderr": execution.stderr or "",
                "error_message": execution.error_message or "",
                "exit_code": execution.exit_code,
                "duration_seconds": execution.duration_seconds,
            },
        }
    
    return dynamic_tool_func


def _register_dynamic_mcp_tools():
    """Register all MCP-exposed scripts as individual tools.
    
    This should be called on server startup to dynamically create tools
    for scripts marked with expose_to_mcp=True.
    
    Tools are registered globally for all users. The actual execution is gated by
    authentication in the tool function - only the script owner can execute it.
    """
    global _registered_dynamic_tool_names
    
    # Get all scripts that should have dynamic tools
    scripts = list(Script.objects.filter(expose_to_mcp=True).order_by("name"))
    
    for script in scripts:
        tool_name = _convert_script_name_to_tool_name(script.name, script.mcp_tool_name)
        
        # Skip if already registered (avoid duplicates on refresh)
        if tool_name in _registered_dynamic_tool_names:
            continue
        
        # Create description
        description = script.description or f"Run the ScriptDash script: {script.name}."
        
        # Create the tool function
        tool_func = _create_dynamic_tool_function(script.id, script.is_destructive)
        
        # Set function attributes for introspection
        tool_func.__name__ = tool_name
        tool_func.__doc__ = description
        
        # Register with scripts_mcp - parameters are derived from function signature
        tool = scripts_mcp._tool_manager.add_tool(
            tool_func,
            name=tool_name,
            description=description,
            annotations={
                "readOnlyHint": not script.is_destructive,
                "openWorldHint": False,
                "destructiveHint": script.is_destructive,
            },
        )
        
        # Override parameters with custom input schema if provided
        if script.input_schema:
            tool.parameters = script.input_schema
        
        _registered_dynamic_tool_names.add(tool_name)
        logger.info(f"Registered MCP tool: {tool_name} (script_id={script.id}, destructive={script.is_destructive})")


def _unregister_dynamic_mcp_tools():
    """Remove all dynamically registered MCP tools.
    
    Called when refreshing tools to ensure clean state.
    """
    global _registered_dynamic_tool_names
    
    for tool_name in list(_registered_dynamic_tool_names):
        if tool_name in scripts_mcp._tool_manager._tools:
            scripts_mcp._tool_manager._tools.pop(tool_name)
            logger.info(f"Unregistered dynamic MCP tool: {tool_name}")
    
    _registered_dynamic_tool_names.clear()


def _rebuild_dynamic_tools():
    """Refresh the registered MCP tools.
    
    Clears existing dynamic tools and re-registers them based on current
    database state. Also invalidates the user cache.
    """
    _invalidate_mcp_tool_cache()
    _unregister_dynamic_mcp_tools()
    _register_dynamic_mcp_tools()


# ── Base server URL (injected via env or settings) ───────────────────────
_SERVER_BASE = os.environ.get(
    "MCP_SERVER_URL",
    os.environ.get("SCRIPTDASH_URL", "http://localhost:8003"),
)

# ── FastMCP Factory ──────────────────────────────────────────────────────


def _create_mcp_instance(
    name: str,
    instructions: str,
    streamable_http_path: str,
    required_scopes: list[str],
) -> FastMCP:
    """Create a FastMCP instance with standard ScriptDash configuration."""
    return FastMCP(
        name=name,
        instructions=instructions,
        streamable_http_path=streamable_http_path,
        # ── OAuth configuration ──────────────────────────────────────────
        auth=AuthSettings(
            issuer_url=f"{_SERVER_BASE}",
            resource_server_url=f"{_SERVER_BASE}",
            required_scopes=required_scopes,
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                default_scopes=required_scopes,
            ),
        ),
        token_verifier=ScriptDashTokenVerifier(),
        # Use stateless HTTP to avoid TaskGroup lifecycle requirement
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=["scriptdash.bhm.li", "*.bhm.li"],
            allowed_origins=["*"],
        ),
    )


# ── Admin MCP Server (CRUD tools) ────────────────────────────────────────
# Mounted at /mcp/admin. Exposes management tools for scripts, schedules,
# tags, secrets, and credentials.

admin_mcp = _create_mcp_instance(
    name="ScriptDash Admin",
    streamable_http_path="/mcp/admin",
    required_scopes=["script:read", "script:write"],
    instructions=(
        "ScriptDash Admin MCP server – manage scripts, schedules, tags, "
        "secrets, and credentials through the Model Context Protocol."
        "\n\n"
        "## SCRIPT MANAGEMENT TOOLS:\n"
        "- list_scripts: List all your scripts with their latest status.\n"
        "- list_mcp_tools: List only scripts exposed to MCP (expose_to_mcp=True).\n"
        "- search: Search scripts by name or description keyword.\n"
        "- fetch: Get full script details including source code and dependencies.\n"
        "- create_script: Create a new script.\n"
        "- update_script: Update an existing script.\n"
        "- delete_script: Delete a script by ID.\n"
        "\n"
        "## EXECUTION TOOLS:\n"
        "- list_executions: List recent executions for a script by ID.\n"
        "- get_execution: Get full execution details by execution ID.\n"
        "- run_script: Execute a script (only works for scripts exposed to MCP).\n"
        "\n"
        "## SCHEDULE MANAGEMENT TOOLS:\n"
        "- list_schedules: List all schedules for a script.\n"
        "- create_schedule: Create a schedule for a script.\n"
        "- delete_schedule: Delete a schedule by ID.\n"
        "\n"
        "## TAG MANAGEMENT TOOLS:\n"
        "- list_tags: List all tags.\n"
        "- create_tag: Create a new tag.\n"
        "- update_tag: Update an existing tag.\n"
        "- delete_tag: Delete a tag by ID.\n"
        "\n"
        "## SECRET MANAGEMENT TOOLS:\n"
        "- list_script_secrets: List all secret names for a script.\n"
        "- get_script_secret: Get a secret value.\n"
        "- set_script_secret: Set/update a secret.\n"
        "- delete_script_secret: Delete a secret.\n"
        "\n"
        "## GLOBAL CREDENTIAL MANAGEMENT TOOLS:\n"
        "- list_credentials: List all your global credentials.\n"
        "- create_credential: Create a new global credential.\n"
        "- update_credential: Update a credential.\n"
        "- delete_credential: Delete a credential by ID.\n"
        "\n"
        "IMPORTANT: To make a script callable via the scripts MCP endpoint "
        "(/mcp), enable 'Expose to MCP Server' in the script settings."
    ),
)


# ── Scripts MCP Server (dynamic per-script tools) ────────────────────────
# Mounted at /mcp. Only exposes dynamically registered tools for scripts
# that have expose_to_mcp=True.

scripts_mcp = _create_mcp_instance(
    name="ScriptDash",
    streamable_http_path="/mcp",
    required_scopes=["script:execute"],
    instructions=(
        "ScriptDash MCP server – execute Python/bash/HTTP scripts through "
        "the Model Context Protocol."
        "\n\n"
        "Each script with 'Expose to MCP Server' enabled appears as its own "
        "tool, named after the script. Call any of the available tools to "
        "execute that script."
        "\n\n"
        "To manage scripts (create, update, delete), schedules, tags, "
        "secrets, and credentials, use the admin MCP endpoint at /mcp/admin."
    ),
)


# ── Dynamic Tool Registration on Startup ──────────────────────────────────

# Register all MCP-exposed scripts as individual tools on scripts_mcp
_rebuild_dynamic_tools()


# ═══════════════════════════════════════════════════════════════════════════
# ADMIN MCP TOOLS (registered on admin_mcp, mounted at /mcp/admin)
# ═══════════════════════════════════════════════════════════════════════════


@admin_mcp.tool(
    name="search",
    description="Search your ScriptDash scripts by name or description keyword.",
    annotations={"readOnlyHint": True},
)
def search_scripts(query: str, context: Context) -> Annotated[CallToolResult, SearchScriptsOutput]:
    """Search scripts matching the query. Returns matching script summaries.

    Args:
        query: Search query string to match against script names or descriptions.
    """
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    scripts = list(
        Script.objects.filter(owner=user)
        .filter(name__icontains=query)
        | Script.objects.filter(owner=user).filter(description__icontains=query)
        .order_by("-updated_at")[:20]
    )

    results = [_script_to_dict(s) for s in scripts]
    return SearchScriptsOutput(results=results).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="fetch",
    description="Fetch full details and source code for a specific script by ID.",
    annotations={"readOnlyHint": True},
)
def fetch_script(script_id: int, context: Context) -> Annotated[CallToolResult, FetchScriptOutput]:
    """Retrieve the full details, code, and dependencies of a script.

    Args:
        script_id: The ID of the script to fetch details for.
    """
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found")  # type: ignore[return-value]

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

    return FetchScriptOutput(**structured).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="list_scripts",
    description="List all of your ScriptDash scripts with their latest status.",
    annotations={"readOnlyHint": True},
)
def list_scripts(context: Context) -> Annotated[CallToolResult, ListScriptsOutput]:
    """Return a list of all scripts owned by the authenticated user."""
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    scripts = list(Script.objects.filter(owner=user).order_by("-updated_at"))
    # Include expose_to_mcp in the output
    results = [_script_to_dict(s) for s in scripts]

    return ListScriptsOutput(scripts=results).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="list_mcp_tools",
    description="List all scripts that are currently exposed to the MCP server.",
    annotations={"readOnlyHint": True},
)
def list_mcp_tools(context: Context) -> Annotated[CallToolResult, ListScriptsOutput]:
    """Return a list of scripts exposed to MCP (expose_to_mcp=True)."""
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    scripts = list(Script.objects.filter(
        owner=user, 
        expose_to_mcp=True
    ).order_by("-updated_at"))
    results = [_script_to_dict(s) for s in scripts]

    return ListScriptsOutput(scripts=results).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="refresh_mcp_tools",
    description="Refresh the dynamic MCP tool list (call when scripts are added/removed/renamed).",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
def refresh_mcp_tools(context: Context) -> dict:
    """Refresh dynamic MCP tools after script changes.
    
    This clears the tool cache and re-registers tools for all MCP-exposed scripts.
    """
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    _rebuild_dynamic_tools()
    
    return {
        "content": [TextContent(type="text", text="MCP tools refreshed successfully.")],
        "structuredContent": {
            "success": True,
            "registered_tools": len(_registered_dynamic_tool_names),
            "message": f"Refreshed {len(_registered_dynamic_tool_names)} dynamic MCP tools."
        }
    }


@admin_mcp.tool(
    name="list_executions",
    description="List recent executions for a script by ID.",
    annotations={"readOnlyHint": True},
)
def list_executions(script_id: int, context: Context) -> Annotated[CallToolResult, ListExecutionsOutput]:
    """Return the 20 most recent executions for a given script.

    Args:
        script_id: The ID of the script to list executions for.
    """
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found")  # type: ignore[return-value]

    executions = list(script.executions.order_by("-created_at")[:20])  # type: ignore[attr-defined]
    execs = [
        {
            "id": e.id,
            "status": e.status,
            "trigger_type": e.trigger_type,
            "started_at": e.started_at.isoformat() if e.started_at else None,
            "completed_at": e.completed_at.isoformat() if e.completed_at else None,
            "duration_seconds": e.duration_seconds,
            "exit_code": e.exit_code,
        }
        for e in executions
    ]

    return ListExecutionsOutput(script_id=script_id, executions=execs).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
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
) -> Annotated[CallToolResult, RunScriptOutput]:
    """Execute a script by ID. Only works for scripts exposed to MCP.
    
    Args:
        script_id: The ID of the script to run.
        input_text: Optional text to feed to the script via stdin.
        timeout_seconds: Max execution time in seconds (default 60).
    """
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found")  # type: ignore[return-value]
    
    # Check if script is exposed to MCP
    if not script.expose_to_mcp:
        return _error(f"Script {script_id} is not exposed to MCP. Enable 'Expose to MCP Server' in the script settings.")  # type: ignore[return-value]

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

    text_parts = []
    if execution.stdout:
        text_parts.append(f"--- stdout ---\n{execution.stdout}")
    if execution.stderr:
        text_parts.append(f"--- stderr ---\n{execution.stderr}")
    if execution.error_message:
        text_parts.append(f"--- error ---\n{execution.error_message}")

    return RunScriptOutput(
        id=execution.id,
        script_id=script.id,
        status=execution.status,
        stdout=execution.stdout or "",
        stderr=execution.stderr or "",
        error_message=execution.error_message or "",
        exit_code=execution.exit_code,
        duration_seconds=execution.duration_seconds,
    ).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="get_execution",
    description="Fetch full details for a specific execution by ID, including stdout, stderr, and outputs.",
    annotations={"readOnlyHint": True},
)
def get_execution(execution_id: int, context: Context) -> Annotated[CallToolResult, GetExecutionOutput]:
    """Retrieve the full details of a script execution by its ID.

    Args:
        execution_id: The ID of the execution to retrieve.
    """
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        execution = ScriptExecution.objects.select_related("script").get(
            id=execution_id, script__owner=user
        )
    except ScriptExecution.DoesNotExist:
        return _error(f"Execution {execution_id} not found")  # type: ignore[return-value]

    return GetExecutionOutput(
        id=execution.id,
        script_id=execution.script_id,
        script_name=execution.script.name,
        status=execution.status,
        trigger_type=execution.trigger_type,
        started_at=execution.started_at.isoformat() if execution.started_at else None,
        completed_at=execution.completed_at.isoformat() if execution.completed_at else None,
        duration_seconds=execution.duration_seconds,
        stdout=execution.stdout or "",
        stderr=execution.stderr or "",
        exit_code=execution.exit_code,
        error_message=execution.error_message or "",
    ).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="create_script",
    description="Create a new script with optional code, description, and tags.",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
def create_script(
    context: Context,
    name: str,
    code: str = "# Write your Python script here\nprint('Hello, World!')",
    description: str = "",
    language: str = "python",
    dependencies: str = "",
    is_public: bool = False,
    expose_to_mcp: bool = False,
    mcp_tool_name: str = "",
    input_schema: dict = None,
    is_destructive: bool = False,
) -> Annotated[CallToolResult, ScriptPropertySchema]:
    """Create a new script owned by the authenticated user.

    Args:
        name: The name for the new script.
        code: The script source code (defaults to a simple hello world).
        description: Optional description for the script.
        language: Script language - 'python', 'bash', or 'http'.
        dependencies: Optional pip dependencies, one per line.
        is_public: Whether the script is publicly accessible.
        expose_to_mcp: Make script available as an MCP tool.
        mcp_tool_name: Custom MCP tool name (lowercase snake_case).
        input_schema: JSON schema for script input parameters.
        is_destructive: Mark script as destructive (safety warning).
    """
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    script = Script.objects.create(
        name=name,
        description=description,
        code=code,
        language=language,
        dependencies=dependencies,
        owner=user,
        is_public=is_public,
        expose_to_mcp=expose_to_mcp,
        mcp_tool_name=mcp_tool_name,
        input_schema=input_schema,
        is_destructive=is_destructive,
    )

    return ScriptPropertySchema(
        id=script.id,
        name=script.name,
        description=script.description or "",
        language=script.language,
        is_public=script.is_public,
        last_status=script.last_status,
        last_run=script.last_run.isoformat() if script.last_run else None,
        execution_count=script.execution_count,
        created_at=script.created_at.isoformat(),
        updated_at=script.updated_at.isoformat(),
    ).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="update_script",
    description="Update an existing script's code, description, or other properties.",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
def update_script(
    context: Context,
    script_id: int,
    name: str = None,
    description: str = None,
    code: str = None,
    language: str = None,
    dependencies: str = None,
    is_public: bool = None,
    expose_to_mcp: bool = None,
    mcp_tool_name: str = None,
    input_schema: dict = None,
    is_destructive: bool = None,
) -> Annotated[CallToolResult, ScriptPropertySchema]:
    """Update an existing script owned by the authenticated user.

    Args:
        script_id: The ID of the script to update.
        name: New name for the script (optional).
        description: New description (optional).
        code: New source code (optional).
        language: Script language - 'python', 'bash', or 'http' (optional).
        dependencies: New pip dependencies, one per line (optional).
        is_public: Whether the script is publicly accessible (optional).
        expose_to_mcp: Make script available as MCP tool (optional).
        mcp_tool_name: Custom MCP tool name (optional, lowercase snake_case).
        input_schema: JSON schema for script input parameters (optional).
        is_destructive: Mark script as destructive (optional).
    """
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found")  # type: ignore[return-value]

    if name is not None:
        script.name = name
    if description is not None:
        script.description = description
    if code is not None:
        script.code = code
    if language is not None:
        script.language = language
    if dependencies is not None:
        script.dependencies = dependencies
    if is_public is not None:
        script.is_public = is_public
    if expose_to_mcp is not None:
        script.expose_to_mcp = expose_to_mcp
    if mcp_tool_name is not None:
        script.mcp_tool_name = mcp_tool_name
    if input_schema is not None:
        script.input_schema = input_schema
    if is_destructive is not None:
        script.is_destructive = is_destructive

    script.save()
    
    # Invalidate cache when script MCP properties change
    _invalidate_mcp_tool_cache(user.id)

    return ScriptPropertySchema(
        id=script.id,
        name=script.name,
        description=script.description or "",
        language=script.language,
        is_public=script.is_public,
        last_status=script.last_status,
        last_run=script.last_run.isoformat() if script.last_run else None,
        execution_count=script.execution_count,
        created_at=script.created_at.isoformat(),
        updated_at=script.updated_at.isoformat(),
    ).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="delete_script",
    description="Delete a script by ID. This removes the script and its virtual environment.",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": True,
    },
)
def delete_script(context: Context, script_id: int) -> Annotated[CallToolResult, DeleteScriptOutput]:
    """Delete a script owned by the authenticated user.

    Args:
        script_id: The ID of the script to delete.
    """
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        script = Script.objects.get(id=script_id, owner=user)
        script.delete()
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found")  # type: ignore[return-value]

    return DeleteScriptOutput(success=True, deleted_script_id=script_id).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="list_schedules",
    description="List all schedules for a specific script by ID.",
    annotations={"readOnlyHint": True},
)
def list_schedules(context: Context, script_id: int) -> Annotated[CallToolResult, ListSchedulesOutput]:
    """List all schedules for a script owned by the authenticated user.

    Args:
        script_id: The ID of the script to list schedules for.
    """
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found")  # type: ignore[return-value]

    schedules = list(script.schedules.all())  # type: ignore[attr-defined]
    result = [
        {
            "id": s.id,
            "script_id": s.script_id,
            "name": s.name,
            "cron_expression": s.cron_expression,
            "schedule_type": s.schedule_type,
            "start_datetime": s.start_datetime.isoformat() if s.start_datetime else None,
            "interval_unit": s.interval_unit,
            "interval_value": s.interval_value,
            "timezone": s.timezone,
            "is_active": s.is_active,
            "last_run": s.last_run.isoformat() if s.last_run else None,
            "next_run": s.next_run.isoformat() if s.next_run else None,
            "created_at": s.created_at.isoformat(),
        }
        for s in schedules
    ]

    return ListSchedulesOutput(script_id=script_id, schedules=result).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="create_schedule",
    description="Create a schedule (cron, interval, or one-time) for a script.",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
def create_schedule(
    context: Context,
    script_id: int,
    name: str,
    cron_expression: str = "",
    schedule_type: str = "single",
    start_datetime: str = None,
    interval_unit: str = None,
    interval_value: int = 1,
) -> Annotated[CallToolResult, SchedulePropertySchema]:
    """Create a schedule for a script owned by the authenticated user.

    Args:
        script_id: The ID of the script to schedule.
        name: Name/description for the schedule.
        cron_expression: Cron expression (e.g., '0 */6 * * *' for every 6 hours).
        schedule_type: 'cron', 'single', or 'interval'.
        start_datetime: ISO datetime string for single/interval schedules.
        interval_unit: For interval: 'hours', 'days', 'weeks', or 'months'.
        interval_value: For interval: how many units between runs.
    """
    from app.services.scheduler import schedule_job
    from datetime import datetime

    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found")  # type: ignore[return-value]

    parsed_start_datetime = None
    if start_datetime:
        try:
            parsed_start_datetime = datetime.fromisoformat(start_datetime)
        except ValueError:
            return _error(f"Invalid start_datetime format: {start_datetime}")  # type: ignore[return-value]

    schedule = ScriptSchedule.objects.create(
        script=script,
        name=name,
        cron_expression=cron_expression,
        schedule_type=schedule_type,
        start_datetime=parsed_start_datetime,
        interval_unit=interval_unit or "",
        interval_value=interval_value,
        created_by=user,
    )

    schedule_job(schedule)

    return SchedulePropertySchema(
        id=schedule.id,
        script_id=schedule.script_id,
        name=schedule.name,
        cron_expression=schedule.cron_expression,
        schedule_type=schedule.schedule_type,
        start_datetime=schedule.start_datetime.isoformat() if schedule.start_datetime else None,
        interval_unit=schedule.interval_unit,
        interval_value=schedule.interval_value,
        timezone=schedule.timezone,
        is_active=schedule.is_active,
        last_run=schedule.last_run.isoformat() if schedule.last_run else None,
        next_run=schedule.next_run.isoformat() if schedule.next_run else None,
        created_at=schedule.created_at.isoformat(),
    ).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="delete_schedule",
    description="Delete a schedule by ID.",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": True,
    },
)
def delete_schedule(context: Context, schedule_id: int) -> Annotated[CallToolResult, DeleteScheduleOutput]:
    """Delete a schedule owned by the authenticated user.

    Args:
        schedule_id: The ID of the schedule to delete.
    """
    from app.services.scheduler import remove_schedule

    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        schedule = ScriptSchedule.objects.get(id=schedule_id)
    except ScriptSchedule.DoesNotExist:
        return _error(f"Schedule {schedule_id} not found")  # type: ignore[return-value]

    if schedule.script.owner != user:
        return _error("Permission denied")  # type: ignore[return-value]

    remove_schedule(schedule)
    schedule.delete()

    return DeleteScheduleOutput(success=True, deleted_schedule_id=schedule_id).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="list_tags",
    description="List all tags created by the authenticated user.",
    annotations={"readOnlyHint": True},
)
def list_tags(context: Context) -> Annotated[CallToolResult, ListTagsOutput]:
    """List all tags created by the authenticated user."""
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    tags = list(Tag.objects.filter(created_by=user).order_by("name"))
    result = [
        {
            "id": t.id,
            "name": t.name,
            "color": t.color,
            "description": t.description or "",
        }
        for t in tags
    ]

    return ListTagsOutput(tags=result).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="create_tag",
    description="Create a new tag with a name and optional color.",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
def create_tag(
    context: Context,
    name: str,
    color: str = "#3B82F6",
    description: str = "",
) -> Annotated[CallToolResult, TagPropertySchema]:
    """Create a new tag for the authenticated user.

    Args:
        name: The name for the new tag.
        color: Hex color code for the tag (default: #3B82F6).
        description: Optional description for the tag.
    """
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    tag, created = Tag.objects.get_or_create(
        name=name,
        created_by=user,
        defaults={"color": color, "description": description},
    )

    if not created:
        return TagPropertySchema(id=tag.id, name=tag.name, color=tag.color, description=tag.description).model_dump()  # type: ignore[return-value]

    return TagPropertySchema(id=tag.id, name=tag.name, color=tag.color, description=tag.description).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="update_tag",
    description="Update an existing tag's name, color, or description.",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
def update_tag(
    context: Context,
    tag_id: int,
    name: str = None,
    color: str = None,
    description: str = None,
) -> Annotated[CallToolResult, TagPropertySchema]:
    """Update an existing tag owned by the authenticated user.

    Args:
        tag_id: The ID of the tag to update.
        name: New name for the tag (optional).
        color: New hex color code (optional).
        description: New description (optional).
    """
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        tag = Tag.objects.get(id=tag_id, created_by=user)
    except Tag.DoesNotExist:
        return _error(f"Tag {tag_id} not found")  # type: ignore[return-value]

    if name is not None:
        tag.name = name
    if color is not None:
        tag.color = color
    if description is not None:
        tag.description = description

    tag.save()

    return TagPropertySchema(id=tag.id, name=tag.name, color=tag.color, description=tag.description).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="delete_tag",
    description="Delete a tag by ID.",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": True,
    },
)
def delete_tag(context: Context, tag_id: int) -> Annotated[CallToolResult, DeleteTagOutput]:
    """Delete a tag owned by the authenticated user.

    Args:
        tag_id: The ID of the tag to delete.
    """
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        tag = Tag.objects.get(id=tag_id, created_by=user)
        tag.delete()
    except Tag.DoesNotExist:
        return _error(f"Tag {tag_id} not found")  # type: ignore[return-value]

    return DeleteTagOutput(success=True, deleted_tag_id=tag_id).model_dump()  # type: ignore[return-value]


# ── Secret Management Tools ────────────────────────────────────────────────


@admin_mcp.tool(
    name="list_script_secrets",
    description="List all secret names for a script (values not returned).",
    annotations={"readOnlyHint": True},
)
def list_script_secrets(context: Context, script_id: int) -> Annotated[CallToolResult, ListScriptSecretsOutput]:
    """List all secret variable names for a script owned by the authenticated user.

    Args:
        script_id: The ID of the script to list secrets for.
    """
    from app.services.secret_store import list_script_secrets as _list_secrets

    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found")  # type: ignore[return-value]

    names = _list_secrets(script_id)
    result = [{"name": name} for name in names]

    return ListScriptSecretsOutput(script_id=script_id, secrets=result).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="get_script_secret",
    description="Get a secret value by name for a script.",
    annotations={"readOnlyHint": True},
)
def get_script_secret(context: Context, script_id: int, secret_name: str) -> Annotated[CallToolResult, GetScriptSecretOutput]:
    """Get a secret value for a script owned by the authenticated user.

    Args:
        script_id: The ID of the script.
        secret_name: The name of the secret to retrieve.
    """
    from app.services.secret_store import get_script_secret as _get_secret

    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found")  # type: ignore[return-value]

    value = _get_secret(script_id, secret_name)
    if value is None:
        return _error(f"Secret '{secret_name}' not found for script {script_id}")  # type: ignore[return-value]

    return GetScriptSecretOutput(script_id=script_id, name=secret_name, value=value).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="set_script_secret",
    description="Set or update a secret name and value for a script.",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
def set_script_secret(
    context: Context,
    script_id: int,
    secret_name: str,
    secret_value: str,
) -> Annotated[CallToolResult, SetScriptSecretOutput]:
    """Set or update a secret for a script owned by the authenticated user.

    Args:
        script_id: The ID of the script.
        secret_name: The name for the secret (letters, numbers, underscore, hyphen).
        secret_value: The value to store for the secret.
    """
    from app.services.secret_store import set_script_secret as _set_secret
    import re

    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found")  # type: ignore[return-value]

    # Validate secret name
    if not secret_name or not re.match(r"^[A-Z0-9_\-]+$", secret_name, re.I):
        return _error("Invalid secret name (use letters, numbers, - or _)")  # type: ignore[return-value]

    _set_secret(script_id, secret_name, secret_value)

    return SetScriptSecretOutput(success=True, script_id=script_id, name=secret_name).model_dump()  # type: ignore[return-value]


@admin_mcp.tool(
    name="delete_script_secret",
    description="Delete a secret by name for a script.",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": True,
    },
)
def delete_script_secret(context: Context, script_id: int, secret_name: str) -> Annotated[CallToolResult, DeleteScriptSecretOutput]:
    """Delete a secret for a script owned by the authenticated user.

    Args:
        script_id: The ID of the script.
        secret_name: The name of the secret to delete.
    """
    from app.services.secret_store import delete_script_secret as _delete_secret

    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")  # type: ignore[return-value]

    try:
        script = Script.objects.get(id=script_id, owner=user)
    except Script.DoesNotExist:
        return _error(f"Script {script_id} not found")  # type: ignore[return-value]

    deleted = _delete_secret(script_id, secret_name)
    if not deleted:
        return _error(f"Secret '{secret_name}' not found for script {script_id}")  # type: ignore[return-value]

    return DeleteScriptSecretOutput(success=True, script_id=script_id, name=secret_name).model_dump()  # type: ignore[return-value]


# ── Global Credential Management Tools ─────────────────────────────────────


@admin_mcp.tool(
    name="list_credentials",
    description="List all your global credentials (values are masked).",
    annotations={"readOnlyHint": True},
)
def list_credentials(context: Context) -> dict:
    """List all global credentials for the authenticated user."""
    from app.models import GlobalCredential
    
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")
    
    credentials = list(GlobalCredential.objects.filter(user=user).order_by("-updated_at"))
    results = [
        {
            "id": c.id,
            "name": c.name,
            "type": c.credential_type,
            "masked_value": c.get_masked_value(),
            "created_at": c.created_at.isoformat(),
            "updated_at": c.updated_at.isoformat(),
        }
        for c in credentials
    ]
    
    return {"credentials": results}


@admin_mcp.tool(
    name="create_credential",
    description="Create a new global credential.",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
def create_credential(
    context: Context,
    name: str,
    credential_type: str,
    api_key: str = None,
    token: str = None,
    username: str = None,
    password: str = None,
    client_id: str = None,
    client_secret: str = None,
    token_url: str = None,
    key: str = None,
    value: str = None,
) -> dict:
    """Create a new global credential for the authenticated user."""
    from app.models import GlobalCredential, CredentialType
    
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")
    
    # Build credential data based on type
    credential_data = {}
    valid = True
    
    if credential_type == CredentialType.API_KEY:
        if api_key:
            credential_data["api_key"] = api_key
        else:
            valid = False
    elif credential_type == CredentialType.BEARER_TOKEN:
        if token:
            credential_data["token"] = token
        else:
            valid = False
    elif credential_type == CredentialType.BASIC_AUTH:
        if username and password:
            credential_data["username"] = username
            credential_data["password"] = password
        else:
            valid = False
    elif credential_type == CredentialType.OAUTH_CLIENT_CREDENTIALS:
        if client_id and client_secret and token_url:
            credential_data["client_id"] = client_id
            credential_data["client_secret"] = client_secret
            credential_data["token_url"] = token_url
        else:
            valid = False
    elif credential_type == CredentialType.GENERIC:
        if key and value:
            credential_data["key"] = key
            credential_data["value"] = value
        else:
            valid = False
    
    if not valid:
        return _error(f"Missing required fields for {credential_type} credential type")
    
    try:
        credential = GlobalCredential.objects.create(
            user=user,
            name=name,
            credential_type=credential_type,
        )
        credential.set_encrypted_data(credential_data)
        credential.save()
        
        return {
            "id": credential.id,
            "name": credential.name,
            "type": credential.credential_type,
            "masked_value": credential.get_masked_value(),
            "created_at": credential.created_at.isoformat(),
        }
    except Exception as e:
        return _error(f"Failed to create credential: {str(e)}")


@admin_mcp.tool(
    name="update_credential",
    description="Update a credential's name or values.",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": False,
    },
)
def update_credential(
    context: Context,
    credential_id: int,
    name: str = None,
    api_key: str = None,
    token: str = None,
    username: str = None,
    password: str = None,
    client_id: str = None,
    client_secret: str = None,
    token_url: str = None,
    key: str = None,
    value: str = None,
) -> dict:
    """Update a global credential for the authenticated user."""
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")
    
    try:
        credential = GlobalCredential.objects.get(id=credential_id, user=user)
    except GlobalCredential.DoesNotExist:
        return _error(f"Credential {credential_id} not found")
    
    # Update name if provided
    if name:
        credential.name = name
    
    # Update credential data
    update_data = {}
    existing_data = credential.get_decrypted_data()
    
    if api_key:
        update_data["api_key"] = api_key
    if token:
        update_data["token"] = token
    if username:
        update_data["username"] = username
    if password:
        update_data["password"] = password
    if client_id:
        update_data["client_id"] = client_id
    if client_secret:
        update_data["client_secret"] = client_secret
    if token_url:
        update_data["token_url"] = token_url
    if key:
        update_data["key"] = key
    if value:
        update_data["value"] = value
    
    if update_data:
        merged_data = {**existing_data, **update_data}
        credential.set_encrypted_data(merged_data)
    
    credential.save()
    
    return {
        "id": credential.id,
        "name": credential.name,
        "type": credential.credential_type,
        "masked_value": credential.get_masked_value(),
    }


@admin_mcp.tool(
    name="delete_credential",
    description="Delete a global credential by ID.",
    annotations={
        "readOnlyHint": False,
        "openWorldHint": False,
        "destructiveHint": True,
    },
)
def delete_credential(context: Context, credential_id: int) -> dict:
    """Delete a global credential for the authenticated user."""
    from app.models import GlobalCredential
    
    user = _get_user_from_context(context)
    if user is None:
        return _error("Authentication required")
    
    try:
        credential = GlobalCredential.objects.get(id=credential_id, user=user)
        credential.delete()
        return {"success": True, "deleted_credential_id": credential_id}
    except GlobalCredential.DoesNotExist:
        return _error(f"Credential {credential_id} not found")


# ── ASGI app factory ─────────────────────────────────────────────────────


def create_mcp_asgi_app(mcp_instance: FastMCP = None) -> "Starlette":
    """Return the FastMCP streamable_http_app as a Starlette ASGI app.

    ``stateless_http=True`` avoids persistent sessions, but the SDK still
    needs ``_task_group`` initialised — the stateless handler calls
    ``_task_group.start()``.  We run ``session_manager.run()`` in a
    persistent background task via ``anyio``.
    """
    import anyio
    import asyncio

    if mcp_instance is None:
        mcp_instance = scripts_mcp

    app = mcp_instance.streamable_http_app()
    sm = mcp_instance.session_manager

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


# ── Auto-refresh MCP tools when scripts change ──────────────────────────
# These signals ensure the dynamic tool list stays in sync whenever a
# script is created, updated, or deleted through any path (UI, API, MCP).

from django.db.models.signals import post_save, post_delete


def _on_script_saved(sender, instance, **kwargs):
    """Rebuild dynamic MCP tools when a script is saved.
    
    This handles:
    - Scripts being created with expose_to_mcp=True
    - Scripts having expose_to_mcp toggled on/off
    - Script names changing (affects auto-generated tool names)
    - Script mcp_tool_name changing
    """
    _rebuild_dynamic_tools()


def _on_script_deleted(sender, instance, **kwargs):
    """Rebuild dynamic MCP tools when a script is deleted.
    
    Ensures tools for deleted scripts are removed from the registry.
    """
    _rebuild_dynamic_tools()


post_save.connect(_on_script_saved, sender=Script, weak=False)
post_delete.connect(_on_script_deleted, sender=Script, weak=False)
