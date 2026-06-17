# Planning Center Services Wrapper

AI-callable wrapper for the Planning Center Services (Service Planner) API.

## Supported Actions

### Read-only
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `list_service_types` | List all service types | — |
| `list_plans` | List plans (optionally by service type) | — |
| `get_plan` | Get plan details | `plan_id` |
| `list_plan_items` | List items in a plan | `plan_id` |
| `list_plan_people` | List team members assigned to a plan | `plan_id` |
| `list_songs` | List all songs | — |
| `search_songs` | Search songs by query | — |
| `list_teams` | List all teams | — |
| `list_people` | List all service-type people | — |

### Write (guarded)
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `update_plan_title` | Update a plan's title | `plan_id`, `title` |
| `create_plan_note` | Add a note to a plan | `plan_id`, `content` |

## CLI Usage

```bash
# List service types
python ai_scripts/planning_center_services/wrapper.py '{"action":"list_service_types"}'

# List plans for a service type
python ai_scripts/planning_center_services/wrapper.py '{"action":"list_plans","service_type_id":"123","per_page":10}'

# Update plan title (dry-run)
python ai_scripts/planning_center_services/wrapper.py '{"action":"update_plan_title","plan_id":"456","title":"New Title","dry_run":true}'
```

## API Docs

https://developer.planningcenter.com/services/docs
