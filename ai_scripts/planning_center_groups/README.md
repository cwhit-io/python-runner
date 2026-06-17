# Planning Center Groups Wrapper

AI-callable wrapper for the Planning Center Groups API.

## Supported Actions

### Read-only
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `list_groups` | List all groups | — |
| `search_groups` | Search groups by query | — |
| `get_group` | Get group details | `group_id` |
| `list_group_memberships` | List members of a group | `group_id` |
| `list_group_events` | List events for a group | `group_id` |
| `list_group_types` | List all group types | — |
| `list_people` | List people who are group members | — |

### Write (guarded)
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `create_group_event` | Create an event for a group | `group_id`, `data` |

## CLI Usage

```bash
python ai_scripts/planning_center_groups/wrapper.py '{"action":"list_groups","per_page":5}'
python ai_scripts/planning_center_groups/wrapper.py '{"action":"get_group","group_id":"123"}'
python ai_scripts/planning_center_groups/wrapper.py '{"action":"create_group_event","group_id":"123","data":{"data":{"type":"Event","attributes":{"name":"Game Night"}}},"dry_run":true}'
```

## API Docs

https://developer.planningcenter.com/groups/docs
