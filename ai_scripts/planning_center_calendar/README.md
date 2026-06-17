# Planning Center Calendar Wrapper

AI-callable wrapper for the Planning Center Calendar API.

## Supported Actions

### Read-only
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `list_events` | List all events | — |
| `search_events` | Search events | — (use `query`) |
| `get_event` | Get event details | `event_id` |
| `list_event_instances` | List instances of an event | `event_id` |
| `list_resources` | List all resources | — |
| `list_rooms` | List all rooms | — |
| `list_tags` | List all tags | — |

### Write (guarded)
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `create_event` | Create a new event | `data` |
| `update_event` | Update an existing event | `event_id`, `data` |

## Environment Variables

Same as other Planning Center wrappers — see shared config.

## CLI Usage

```bash
python ai_scripts/planning_center_calendar/wrapper.py '{"action":"list_events","per_page":5}'
python ai_scripts/planning_center_calendar/wrapper.py '{"action":"get_event","event_id":"123456"}'
python ai_scripts/planning_center_calendar/wrapper.py '{"action":"create_event","data":{"data":{"type":"Event","attributes":{"name":"Test"}}},"dry_run":true}'
```

## API Docs

https://developer.planningcenter.com/calendar/docs
