"""
JSON Schema definitions for all MCP tools.

Uses JSON Schema Draft 2020-12 format.
All schemas are designed to be clear and complete for AI client consumption.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


# ── Script Property Schema ─────────────────────────────────────────────────


class ScriptPropertySchema(BaseModel):
    """Property for a single script."""
    id: int = Field(description="Unique identifier for the script.")
    name: str = Field(description="Name of the script.")
    description: str = Field(default="", description="Script description.")
    language: Literal["python", "bash", "http"] = Field(description="Script language/runtime.")
    is_public: bool = Field(description="Whether the script is publicly accessible.")
    last_status: str = Field(description="Last execution status: idle, running, success, or failed.")
    last_run: Optional[str] = Field(default=None, description="ISO datetime of last execution, or null.")
    execution_count: int = Field(description="Number of times the script has been executed.")
    created_at: str = Field(description="ISO datetime when the script was created.")
    updated_at: str = Field(description="ISO datetime when the script was last updated.")
    expose_to_mcp: bool = Field(default=False, description="Whether script is exposed as MCP tool.")
    mcp_tool_name: str = Field(default="", description="Custom MCP tool name.")
    is_destructive: bool = Field(default=False, description="Whether script is marked as destructive.")
    has_input_schema: bool = Field(default=False, description="Whether script has custom input schema.")


# ── Execution Property Schema ──────────────────────────────────────────────


class ExecutionPropertySchema(BaseModel):
    """Property for a single execution."""
    id: int = Field(description="Unique execution ID.")
    status: str = Field(description="Execution status: queued, running, success, failed, or cancelled.")
    trigger_type: str = Field(description="How the execution was triggered: manual, scheduled, api, or mcp.")
    started_at: Optional[str] = Field(default=None, description="ISO datetime when execution started.")
    completed_at: Optional[str] = Field(default=None, description="ISO datetime when execution completed.")
    duration_seconds: Optional[float] = Field(default=None, description="Execution duration in seconds.")
    exit_code: Optional[int] = Field(default=None, description="Process exit code, null for running executions.")


# ── Schedule Property Schema ───────────────────────────────────────────────


class SchedulePropertySchema(BaseModel):
    """Property for a single schedule."""
    id: int = Field(description="Schedule ID.")
    script_id: int = Field(description="ID of the script this schedule belongs to.")
    name: str = Field(description="Schedule name/description.")
    cron_expression: str = Field(default="", description="Cron expression for the schedule.")
    schedule_type: str = Field(description="Schedule type: single, cron, or interval.")
    start_datetime: Optional[str] = Field(default=None, description="ISO datetime for single/interval schedules.")
    interval_unit: Optional[str] = Field(default=None, description="Interval unit: hours, days, weeks, or months.")
    interval_value: int = Field(description="Interval value (how many units).")
    timezone: str = Field(description="Timezone for schedule calculation.")
    is_active: bool = Field(description="Whether the schedule is active.")
    last_run: Optional[str] = Field(default=None, description="ISO datetime of last run.")
    next_run: Optional[str] = Field(default=None, description="ISO datetime of next scheduled run.")
    created_at: str = Field(description="ISO datetime when schedule was created.")


# ── Tag Property Schema ────────────────────────────────────────────────────


class TagPropertySchema(BaseModel):
    """Property for a single tag."""
    id: int = Field(description="Tag ID.")
    name: str = Field(description="Tag name.")
    color: str = Field(description="Hex color code for the tag.")
    description: str = Field(default="", description="Tag description.")


# ── Secret Property Schema ──────────────────────────────────────────────────


class SecretPropertySchema(BaseModel):
    """Property for a secret reference."""
    name: str = Field(description="Secret variable name (value is never returned in list).")


# ── Tool Input/Output Schemas ───────────────────────────────────────────────


class SearchScriptsInput(BaseModel):
    """Input schema for search tool."""
    query: str = Field(description="Search query string to match against script names or descriptions.")


class SearchScriptsOutput(BaseModel):
    """Output schema for search tool."""
    results: list[ScriptPropertySchema] = Field(default_factory=list, description="List of matching scripts.")


class FetchScriptInput(BaseModel):
    """Input schema for fetch tool."""
    script_id: int = Field(description="ID of the script to fetch details for.", ge=1)


class FetchScriptOutput(BaseModel):
    """Output schema for fetch tool."""
    id: int = Field(description="Script ID.")
    title: str = Field(description="Script name.")
    text: str = Field(description="Script source code.")
    url: str = Field(default="", description="URL reference (currently unused).")
    metadata: Optional[dict] = Field(default=None, description="Additional script metadata including language, dependencies, and status.")


class ListScriptsOutput(BaseModel):
    """Output schema for list_scripts tool."""
    scripts: list[ScriptPropertySchema] = Field(default_factory=list, description="List of user's scripts.")


class ListExecutionsInput(BaseModel):
    """Input schema for list_executions tool."""
    script_id: int = Field(description="ID of the script to list executions for.", ge=1)


class ListExecutionsOutput(BaseModel):
    """Output schema for list_executions tool."""
    script_id: int = Field(description="The script ID these executions belong to.")
    executions: list[ExecutionPropertySchema] = Field(default_factory=list, description="List of recent executions.")


class RunScriptInput(BaseModel):
    """Input schema for run_script tool."""
    script_id: int = Field(description="ID of the script to execute.", ge=1)
    input_text: str = Field(default="", description="Optional text to send to the script via stdin.")
    timeout_seconds: int = Field(default=60, description="Maximum execution time in seconds.", ge=1, le=3600)


class RunScriptOutput(BaseModel):
    """Output schema for run_script tool."""
    id: int = Field(description="Execution ID.")
    script_id: int = Field(description="The script that was executed.")
    status: str = Field(description="Final execution status.")
    stdout: str = Field(default="", description="Standard output from the script.")
    stderr: str = Field(default="", description="Standard error from the script.")
    error_message: str = Field(default="", description="Error message if execution failed.")
    exit_code: Optional[int] = Field(default=None, description="Process exit code.")
    duration_seconds: Optional[float] = Field(default=None, description="Execution duration.")


class ScriptToolExecutionOutput(BaseModel):
    """Output schema advertised for dynamic ScriptDash MCP script tools."""

    execution_id: int = Field(description="Unique execution record ID.")
    script_id: int = Field(description="ID of the script that was executed.")
    status: str = Field(
        description="Execution status: queued, running, success, failed, or cancelled."
    )
    stdout: str = Field(
        default="",
        description=(
            "Script standard output. API wrappers usually print JSON here "
            "(success, action, data, error fields)."
        ),
    )
    stderr: str = Field(default="", description="Script standard error output.")
    error_message: str = Field(
        default="",
        description="Runner-level error message when execution fails before or during the run.",
    )
    exit_code: Optional[int] = Field(default=None, description="Process exit code, if available.")
    duration_seconds: Optional[float] = Field(
        default=None,
        description="Wall-clock execution duration in seconds.",
    )


def get_script_tool_output_schema() -> dict:
    """JSON Schema for dynamic ScriptDash MCP tool responses."""
    return ScriptToolExecutionOutput.model_json_schema()


class GetExecutionInput(BaseModel):
    """Input schema for get_execution tool."""
    execution_id: int = Field(description="ID of the execution to retrieve.", ge=1)


class GetExecutionOutput(BaseModel):
    """Output schema for get_execution tool."""
    id: int = Field(description="Execution ID.")
    script_id: int = Field(description="ID of the script that was executed.")
    script_name: str = Field(description="Name of the script that was executed.")
    status: str = Field(description="Execution status.")
    trigger_type: str = Field(description="How the execution was triggered.")
    started_at: Optional[str] = Field(default=None, description="ISO datetime when execution started.")
    completed_at: Optional[str] = Field(default=None, description="ISO datetime when execution completed.")
    duration_seconds: Optional[float] = Field(default=None, description="Execution duration in seconds.")
    stdout: str = Field(default="", description="Standard output from the script.")
    stderr: str = Field(default="", description="Standard error from the script.")
    exit_code: Optional[int] = Field(default=None, description="Process exit code.")
    error_message: str = Field(default="", description="Error message if execution failed.")


class CreateScriptInput(BaseModel):
    """Input schema for create_script tool."""
    name: str = Field(description="Name for the new script.", min_length=1)
    code: str = Field(
        default="# Write your Python script here\nprint('Hello, World!')",
        description="Script source code."
    )
    description: str = Field(default="", description="Optional description for the script.")
    language: Literal["python", "bash", "http"] = Field(
        default="python",
        description="Script language: python, bash, or http."
    )
    dependencies: str = Field(
        default="",
        description="Pip dependencies, one per line (e.g., 'requests==2.28.0')."
    )
    is_public: bool = Field(
        default=False,
        description="Whether the script is publicly accessible."
    )
    expose_to_mcp: bool = Field(
        default=False,
        description="Make script available as an MCP tool."
    )
    mcp_tool_name: str = Field(
        default="",
        description="Custom MCP tool name (lowercase snake_case)."
    )
    input_schema: Optional[dict] = Field(
        default=None,
        description="JSON schema for script input parameters."
    )
    is_destructive: bool = Field(
        default=False,
        description="Mark script as destructive (triggers safety warnings)."
    )


class UpdateScriptInput(BaseModel):
    """Input schema for update_script tool."""
    script_id: int = Field(description="ID of the script to update.", ge=1)
    name: Optional[str] = Field(default=None, description="New name for the script.")
    description: Optional[str] = Field(default=None, description="New description.")
    code: Optional[str] = Field(default=None, description="New source code.")
    language: Optional[Literal["python", "bash", "http"]] = Field(default=None, description="New script language.")
    dependencies: Optional[str] = Field(default=None, description="New pip dependencies, one per line.")
    is_public: Optional[bool] = Field(default=None, description="New public status.")
    expose_to_mcp: Optional[bool] = Field(default=None, description="MCP tool exposure status.")
    mcp_tool_name: Optional[str] = Field(default=None, description="Custom MCP tool name.")
    input_schema: Optional[dict] = Field(default=None, description="JSON schema for input parameters.")
    is_destructive: Optional[bool] = Field(default=None, description="Destructive flag for safety warnings.")


class DeleteScriptInput(BaseModel):
    """Input schema for delete_script tool."""
    script_id: int = Field(description="ID of the script to delete.", ge=1)


class DeleteScriptOutput(BaseModel):
    """Output schema for delete_script tool."""
    success: bool = Field(description="Whether the deletion was successful.")
    deleted_script_id: int = Field(description="ID of the deleted script.")


class ListSchedulesInput(BaseModel):
    """Input schema for list_schedules tool."""
    script_id: int = Field(description="ID of the script to list schedules for.", ge=1)


class ListSchedulesOutput(BaseModel):
    """Output schema for list_schedules tool."""
    script_id: int = Field(description="The script ID these schedules belong to.")
    schedules: list[SchedulePropertySchema] = Field(default_factory=list, description="List of schedules.")


class CreateScheduleInput(BaseModel):
    """Input schema for create_schedule tool."""
    script_id: int = Field(description="ID of the script to schedule.", ge=1)
    name: str = Field(description="Name/description for the schedule.")
    cron_expression: str = Field(
        default="",
        description="Cron expression (e.g., '0 */6 * * *' for every 6 hours)."
    )
    schedule_type: Literal["single", "cron", "interval"] = Field(
        default="single",
        description="Schedule type: single (one-time), cron, or interval."
    )
    start_datetime: Optional[str] = Field(
        default=None,
        description="ISO datetime string for single/interval schedules (e.g., '2024-01-15T10:30:00')."
    )
    interval_unit: Optional[Literal["hours", "days", "weeks", "months"]] = Field(
        default=None,
        description="For interval schedules: 'hours', 'days', 'weeks', or 'months'."
    )
    interval_value: int = Field(
        default=1,
        description="For interval schedules: how many units between runs.",
        ge=1
    )


class DeleteScheduleInput(BaseModel):
    """Input schema for delete_schedule tool."""
    schedule_id: int = Field(description="ID of the schedule to delete.", ge=1)


class DeleteScheduleOutput(BaseModel):
    """Output schema for delete_schedule tool."""
    success: bool = Field(description="Whether the deletion was successful.")
    deleted_schedule_id: int = Field(description="ID of the deleted schedule.")


class ListTagsOutput(BaseModel):
    """Output schema for list_tags tool."""
    tags: list[TagPropertySchema] = Field(default_factory=list, description="List of user's tags.")


class CreateTagInput(BaseModel):
    """Input schema for create_tag tool."""
    name: str = Field(description="Name for the new tag.", min_length=1)
    color: str = Field(
        default="#3B82F6",
        description="Hex color code for the tag (e.g., '#3B82F6')."
    )
    description: str = Field(default="", description="Optional description for the tag.")


class UpdateTagInput(BaseModel):
    """Input schema for update_tag tool."""
    tag_id: int = Field(description="ID of the tag to update.", ge=1)
    name: Optional[str] = Field(default=None, description="New name for the tag.")
    color: Optional[str] = Field(default=None, description="New hex color code.")
    description: Optional[str] = Field(default=None, description="New description.")


class DeleteTagInput(BaseModel):
    """Input schema for delete_tag tool."""
    tag_id: int = Field(description="ID of the tag to delete.", ge=1)


class DeleteTagOutput(BaseModel):
    """Output schema for delete_tag tool."""
    success: bool = Field(description="Whether the deletion was successful.")
    deleted_tag_id: int = Field(description="ID of the deleted tag.")


class ListScriptSecretsInput(BaseModel):
    """Input schema for list_script_secrets tool."""
    script_id: int = Field(description="ID of the script to list secrets for.", ge=1)


class ListScriptSecretsOutput(BaseModel):
    """Output schema for list_script_secrets tool."""
    script_id: int = Field(description="The script ID these secrets belong to.")
    secrets: list[SecretPropertySchema] = Field(default_factory=list, description="List of secret names.")


class GetScriptSecretInput(BaseModel):
    """Input schema for get_script_secret tool."""
    script_id: int = Field(description="ID of the script.", ge=1)
    secret_name: str = Field(description="Name of the secret to retrieve.", min_length=1)


class GetScriptSecretOutput(BaseModel):
    """Output schema for get_script_secret tool."""
    script_id: int = Field(description="The script ID this secret belongs to.")
    name: str = Field(description="Secret variable name.")
    value: str = Field(description="Secret value.")


class SetScriptSecretInput(BaseModel):
    """Input schema for set_script_secret tool."""
    script_id: int = Field(description="ID of the script to set the secret for.", ge=1)
    secret_name: str = Field(
        description="Name for the secret (letters, numbers, underscore, hyphen only).",
        min_length=1,
        pattern=r"^[A-Z0-9_\-]+$",
    )
    secret_value: str = Field(description="Value to store for the secret.")


class SetScriptSecretOutput(BaseModel):
    """Output schema for set_script_secret tool."""
    success: bool = Field(description="Whether the secret was set successfully.")
    script_id: int = Field(description="The script ID this secret belongs to.")
    name: str = Field(description="Secret variable name that was set.")


class DeleteScriptSecretInput(BaseModel):
    """Input schema for delete_script_secret tool."""
    script_id: int = Field(description="ID of the script.", ge=1)
    secret_name: str = Field(description="Name of the secret to delete.", min_length=1)


class DeleteScriptSecretOutput(BaseModel):
    """Output schema for delete_script_secret tool."""
    success: bool = Field(description="Whether the deletion was successful.")
    script_id: int = Field(description="The script ID this secret belongs to.")
    name: str = Field(description="Secret variable name that was deleted.")


# ── Schema Registry ───────────────────────────────────────────────────────


TOOL_SCHEMAS = {
    "search": {
        "input": SearchScriptsInput,
        "output": SearchScriptsOutput,
    },
    "fetch": {
        "input": FetchScriptInput,
        "output": FetchScriptOutput,
    },
    "list_scripts": {
        "input": None,  # No input parameters
        "output": ListScriptsOutput,
    },
    "list_executions": {
        "input": ListExecutionsInput,
        "output": ListExecutionsOutput,
    },
    "run_script": {
        "input": RunScriptInput,
        "output": RunScriptOutput,
    },
    "get_execution": {
        "input": GetExecutionInput,
        "output": GetExecutionOutput,
    },
    "create_script": {
        "input": CreateScriptInput,
        "output": ScriptPropertySchema,
    },
    "update_script": {
        "input": UpdateScriptInput,
        "output": ScriptPropertySchema,
    },
    "delete_script": {
        "input": DeleteScriptInput,
        "output": DeleteScriptOutput,
    },
    "list_schedules": {
        "input": ListSchedulesInput,
        "output": ListSchedulesOutput,
    },
    "create_schedule": {
        "input": CreateScheduleInput,
        "output": SchedulePropertySchema,
    },
    "delete_schedule": {
        "input": DeleteScheduleInput,
        "output": DeleteScheduleOutput,
    },
    "list_tags": {
        "input": None,  # No input parameters
        "output": ListTagsOutput,
    },
    "create_tag": {
        "input": CreateTagInput,
        "output": TagPropertySchema,
    },
    "update_tag": {
        "input": UpdateTagInput,
        "output": TagPropertySchema,
    },
    "delete_tag": {
        "input": DeleteTagInput,
        "output": DeleteTagOutput,
    },
    "list_script_secrets": {
        "input": ListScriptSecretsInput,
        "output": ListScriptSecretsOutput,
    },
    "get_script_secret": {
        "input": GetScriptSecretInput,
        "output": GetScriptSecretOutput,
    },
    "set_script_secret": {
        "input": SetScriptSecretInput,
        "output": SetScriptSecretOutput,
    },
    "delete_script_secret": {
        "input": DeleteScriptSecretInput,
        "output": DeleteScriptSecretOutput,
    },
}


# ── Dynamic MCP Tool Schemas ─────────────────────────────────────────────


class DynamicToolInfo(BaseModel):
    """Information about a dynamically registered MCP tool."""
    script_id: int = Field(description="ID of the script this tool is based on.")
    tool_name: str = Field(description="MCP tool name for this script.")
    description: str = Field(description="Tool description.")
    is_destructive: bool = Field(default=False, description="Whether the tool is marked as destructive.")


class MCPToolInfoOutput(BaseModel):
    """Output schema for listing dynamic MCP tools."""
    tools: list[DynamicToolInfo] = Field(default_factory=list, description="List of dynamic MCP tools.")


class RefreshMCPToolsOutput(BaseModel):
    """Output schema for refresh_mcp_tools tool."""
    success: bool = Field(description="Whether the refresh was successful.")
    registered_tools: int = Field(description="Number of tools registered.")
    message: str = Field(description="Status message.")


# Update the TOOL_SCHEMAS with refresh_mcp_tools
TOOL_SCHEMAS["refresh_mcp_tools"] = {
    "input": None,  # No input parameters
    "output": RefreshMCPToolsOutput,
}


# ── Dynamic MCP Tool Schemas ─────────────────────────────────────────────


class DynamicToolInfo(BaseModel):
    """Information about a dynamically registered MCP tool."""
    script_id: int = Field(description="ID of the script this tool is based on.")
    tool_name: str = Field(description="MCP tool name for this script.")
    description: str = Field(description="Tool description.")
    is_destructive: bool = Field(default=False, description="Whether the tool is marked as destructive.")


class MCPToolInfoOutput(BaseModel):
    """Output schema for listing dynamic MCP tools."""
    tools: list[DynamicToolInfo] = Field(default_factory=list, description="List of dynamic MCP tools.")


class RefreshMCPToolsOutput(BaseModel):
    """Output schema for refresh_mcp_tools tool."""
    success: bool = Field(description="Whether the refresh was successful.")
    registered_tools: int = Field(description="Number of tools registered.")
    message: str = Field(description="Status message.")
