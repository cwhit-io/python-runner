# ScriptDash AI Assistant Guide

This document describes how AI assistants can interact with the ScriptDash
script execution platform. Two MCP (Model Context Protocol) endpoints are
available, as well as a REST API.

---

## MCP Endpoints (Native Streamable HTTP)

ScriptDash exposes two native MCP endpoints that AI assistants connect to
directly. Both use OAuth 2.0 Bearer token authentication.

### `/mcp` — Script Execution Tools

**Scope:** `script:execute`

This endpoint dynamically exposes one tool for each script that has
**Expose to MCP Server** enabled in its settings. Each tool is named after
the script (auto-generated snake_case, or a custom name if set).

- Tools appear and disappear automatically when scripts are saved or deleted.
- Each tool accepts:
  - `input_text` (optional string) — sent to the script via stdin
  - `timeout_seconds` (optional integer, default 60, max 3600)
- The tool returns stdout, stderr, exit code, and execution duration.
- Credentials attached to the script are injected as environment variables.
- **Only the script owner can execute their own scripts.**

### `/mcp/admin` — Admin / CRUD Tools

**Scope:** `script:read` + `script:write`

Full management tools for scripts, schedules, tags, secrets, and credentials.

**Script tools:**

- `search` — search scripts by name or description
- `fetch` — get full script details including source code
- `list_scripts` — list all scripts with status
- `list_mcp_tools` — list only MCP-exposed scripts
- `create_script` — create a new script
- `update_script` — update name, code, description, language, etc.
- `delete_script` — delete a script and its venv
- `run_script` — execute a script by ID
- `refresh_mcp_tools` — re-scan for exposed scripts

**Execution tools:**

- `list_executions` — recent executions for a script
- `get_execution` — full execution details including output

**Schedule tools:**

- `list_schedules` — schedules for a script
- `create_schedule` — cron, interval, or one-time schedule
- `delete_schedule` — remove a schedule

**Tag tools:**

- `list_tags`, `create_tag`, `update_tag`, `delete_tag`

**Secret tools:**

- `list_script_secrets`, `get_script_secret`
- `set_script_secret`, `delete_script_secret`

**Credential tools:**

- `list_credentials`, `create_credential`
- `update_credential`, `delete_credential`

---

## REST API (OpenAPI)

A full REST API is documented interactively at:

- Swagger UI: `/api/docs/`
- Redoc: `/api/redoc/`
- OpenAPI JSON: `/api/v1/openapi.json`

**Authentication:** Include `Authorization: Bearer <token>` in headers.
Tokens are managed on the API Tokens page in the web UI.

**Key REST endpoints:**

- `GET /api/v1/scripts` — list scripts
- `POST /api/v1/scripts` — create script
- `GET /api/v1/scripts/{id}` — get script details
- `PUT /api/v1/scripts/{id}` — update script
- `DELETE /api/v1/scripts/{id}` — delete script
- `POST /api/v1/scripts/{id}/execute` — execute script (returns result)
- `GET /api/v1/scripts/{id}/executions` — execution history

**MCP-compatible REST endpoints (tool manifest format):**

- `GET /api/v1/mcp/discovery` — discover public scripts
- `GET /api/v1/mcp/scripts` — list tool manifests for exposed scripts
- `GET /api/v1/mcp/scripts/{id}/manifest` — get tool manifest
- `POST /api/v1/mcp/scripts/{id}/invoke` — invoke a script

---

## Tips for AI Assistants

1. **Use `/mcp` for execution only** — connect to this endpoint when the
   user wants to run a script. The available tools are the user's scripts.

2. **Use `/mcp/admin` for management** — connect to this endpoint when
   the user wants to create, edit, or delete scripts and other resources.

3. **Scripts have an `expose_to_mcp` flag** — a script must have this
   enabled to appear as a tool on `/mcp`. You can enable it via
   `update_script` on the admin endpoint.

4. **Input schemas** — scripts can have custom JSON input schemas.
   Use `fetch` on the admin endpoint to see a script's schema.

5. **Credentials** — credentials attached to a script are injected as
   environment variables during execution. They are never visible in
   tool descriptions or responses.

6. **Schedules** — scripts can run on cron, interval, or one-time
   schedules. Use the schedule tools on the admin endpoint to manage them.

7. **Destructive scripts** — some scripts are marked as destructive.
   Exercise caution when the tool annotation includes `destructiveHint`.
