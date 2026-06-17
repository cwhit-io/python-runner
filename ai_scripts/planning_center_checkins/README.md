# Planning Center Check-Ins Wrapper

AI-callable wrapper for the Planning Center Check-Ins API.

## Supported Actions

### Read-only (no write actions)
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `list_events` | List all check-in events | — |
| `get_event` | Get event details | `event_id` |
| `list_check_ins` | List check-ins (optionally by event) | — |
| `get_check_in` | Get check-in details | `check_in_id` |
| `list_locations` | List all locations | — |
| `list_event_periods` | List periods for an event | `event_id` |
| `list_attendees` | List attendees (optionally by event) | — |

This wrapper is read-only. No create, update, or delete actions are implemented.

## CLI Usage

```bash
python ai_scripts/planning_center_checkins/wrapper.py '{"action":"list_events","per_page":5}'
python ai_scripts/planning_center_checkins/wrapper.py '{"action":"get_event","event_id":"123"}'
python ai_scripts/planning_center_checkins/wrapper.py '{"action":"list_check_ins","event_id":"123"}'
```

## API Docs

https://developer.planningcenter.com/check-ins/docs
