# Planning Center Registrations Wrapper

AI-callable wrapper for the Planning Center Registrations API.

## Supported Actions

### Read-only (no write actions)
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `list_events` | List all registration events | — |
| `get_event` | Get event details | `event_id` |
| `list_attendees` | List attendees for an event | `event_id` |
| `get_attendee` | Get attendee details | `event_id`, `attendee_id` |
| `list_categories` | List all categories | — |
| `list_selections` | List selections for an event | `event_id` |
| `list_signup_locations` | List signup locations | — |

This wrapper is read-only. No create, update, or delete actions are implemented.

## CLI Usage

```bash
python ai_scripts/planning_center_registrations/wrapper.py '{"action":"list_events","per_page":5}'
python ai_scripts/planning_center_registrations/wrapper.py '{"action":"get_event","event_id":"123"}'
python ai_scripts/planning_center_registrations/wrapper.py '{"action":"list_attendees","event_id":"123"}'
```

## API Docs

https://developer.planningcenter.com/registrations/docs
