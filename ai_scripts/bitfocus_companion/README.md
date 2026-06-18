# Bitfocus Companion HTTP Wrapper

AI-callable wrapper for the Bitfocus Companion HTTP remote control API (v4.x).

## Supported Actions

| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `press_button` | Press a button | — |
| `button_down` | Trigger button press (down) | — |
| `button_up` | Trigger button release (up) | — |
| `rotate_left` | Rotate encoder left | — |
| `rotate_right` | Rotate encoder right | — |
| `set_step` | Set button/encoder step | `step` |
| `set_button_style` | Update button style | `style` |
| `set_custom_variable` | Set a custom variable | `name`, `value` |
| `get_custom_variable` | Get a custom variable value | `name` |
| `get_module_variable` | Get a module variable value | `module_name`, `variable_name` |
| `rescan_surfaces` | Trigger surface rescan | — |

Button locations use Companion's v4 format: `page`, `row`, `column` (all 0-based unless your pages are numbered differently). `x`/`y` are accepted as aliases for `column`/`row`.

Example from the official docs: press page 1, row 0, column 2:

```json
{"action":"press_button","page":1,"row":0,"column":2}
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `COMPANION_BASE_URL` | No | Companion base URL (default: `http://localhost:8000`) |
| `COMPANION_API_KEY` | No | Optional Bearer token if configured in Companion |
| `COMPANION_TOKEN` | No | Alias for `COMPANION_API_KEY` |

If ScriptDash runs in Docker and Companion runs on the host, use something like `http://host.docker.internal:8000` instead of `localhost`.

## CLI Usage

```bash
# Press page 1, row 0, column 2
python ai_scripts/bitfocus_companion/wrapper.py '{"action":"press_button","page":1,"row":0,"column":2}'

# Set a custom variable
python ai_scripts/bitfocus_companion/wrapper.py '{"action":"set_custom_variable","name":"current_song","value":"Amazing Grace"}'

# Get a module variable (connection label from Companion UI)
python ai_scripts/bitfocus_companion/wrapper.py '{"action":"get_module_variable","module_name":"My OBS","variable_name":"scene_name"}'
```

## Notes

- Enable **HTTP Remote Control** in Companion settings (`http_api_enabled`)
- Companion returns plain text for variable reads; the wrapper wraps that as `{"value": "..."}`
- `module_name` must match the connection **label** in Companion, not the module ID
- No destructive actions are exposed

## API Docs

https://companion.free/user-guide/v4.3/remote-control/http-remote-control/