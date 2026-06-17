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

Button locations are specified with `page`, `bank`, `x`, `y` (all default to 0).

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `COMPANION_BASE_URL` | No | Companion base URL (default: `http://localhost:8000`) |
| `COMPANION_API_KEY` | No | API key/token for Companion auth (if enabled) |
| `COMPANION_TOKEN` | No | Alias for COMPANION_API_KEY |

## CLI Usage

```bash
# Press a button at page 0, bank 0, x=1, y=2
python ai_scripts/bitfocus_companion/wrapper.py '{"action":"press_button","page":0,"bank":0,"x":1,"y":2}'

# Set a custom variable
python ai_scripts/bitfocus_companion/wrapper.py '{"action":"set_custom_variable","name":"current_song","value":"Amazing Grace"}'

# Get a custom variable
python ai_scripts/bitfocus_companion/wrapper.py '{"action":"get_custom_variable","name":"current_song"}'

# Get a module variable (e.g. from OBS)
python ai_scripts/bitfocus_companion/wrapper.py '{"action":"get_module_variable","module_name":"obs-studio","variable_name":"scene_name"}'

# Rescan surfaces
python ai_scripts/bitfocus_companion/wrapper.py '{"action":"rescan_surfaces"}'
```

## Notes

- Button coordinates use Companion's 0-based indexing
- Empty page/bank/x/y values default to 0
- Timeout default is 10 seconds (Companion is typically local)
- This wrapper exposes no destructive actions; button presses are safe

## API Docs

https://github.com/bitfocus/companion/wiki/HTTP-Actions
