# Planning Center People Wrapper

AI-callable wrapper for the Planning Center People API.

## Supported Actions

### Read-only
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `list_people` | List all people | — |
| `search_people` | Search people by query | — (use `query`) |
| `get_person` | Get person details | `person_id` |
| `list_households` | List all households | — |
| `get_household` | Get household details | `household_id` |
| `list_campuses` | List all campuses | — |
| `list_workflows` | List all workflows | — |
| `list_lists` | List all lists | — |
| `get_list` | Get list details | `list_id` |
| `list_birthdays` | List birthdays by month/day | — (use `month`, `day`) |

### Write (guarded)
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `create_person` | Create a new person | `data` |
| `update_person` | Update an existing person | `person_id`, `data` |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `PLANNING_CENTER_ACCESS_TOKEN` | Yes* | Personal access token for Bearer auth |
| `PLANNING_CENTER_CLIENT_ID` | Yes* | OAuth client ID (used with secret for Basic auth) |
| `PLANNING_CENTER_CLIENT_SECRET` | Yes* | OAuth client secret (used with ID for Basic auth) |

\* Either `PLANNING_CENTER_ACCESS_TOKEN` OR both `PLANNING_CENTER_CLIENT_ID` + `PLANNING_CENTER_CLIENT_SECRET` must be set.

## CLI Usage

```bash
# List people
python ai_scripts/planning_center_people/wrapper.py '{"action":"list_people","per_page":5}'

# Search people
python ai_scripts/planning_center_people/wrapper.py '{"action":"search_people","query":"John"}'

# Get person with related resources
python ai_scripts/planning_center_people/wrapper.py '{"action":"get_person","person_id":"123456","include":"addresses,emails"}'

# Dry-run create
python ai_scripts/planning_center_people/wrapper.py '{"action":"create_person","data":{"data":{"type":"Person","attributes":{"first_name":"Jane"}}},"dry_run":true}'
```

## Example Output

```json
{
  "success": true,
  "action": "list_people",
  "data": {
    "data": [ ... ],
    "meta": { "total_count": 42, "count": 5 }
  },
  "warnings": [],
  "meta": {
    "service": "planning_center_people",
    "duration_ms": 342.1
  }
}
```

## Write Behavior

- All write actions support `dry_run: true` to preview the request
- Write actions send proper JSON:API formatted request bodies
- `update_person` uses PATCH for partial updates
- Writes go directly to the API — no local caching

## API Documentation

https://developer.planningcenter.com/people/docs
