# Planning Center Publishing Wrapper

AI-callable wrapper for the Planning Center Publishing API.

## Supported Actions

### Read-only
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `list_episodes` | List all episodes | — |
| `get_episode` | Get episode details | `episode_id` |
| `list_series` | List all series | — |
| `get_series` | Get series details | `series_id` |
| `list_speakers` | List all speakers | — |
| `list_episode_resources` | List resources for an episode | `episode_id` |

### Write (guarded)
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `create_episode` | Create a new episode | `data` |
| `update_episode` | Update an existing episode | `episode_id`, `data` |

## CLI Usage

```bash
python ai_scripts/planning_center_publishing/wrapper.py '{"action":"list_episodes","per_page":5}'
python ai_scripts/planning_center_publishing/wrapper.py '{"action":"get_series","series_id":"123"}'
```

## API Docs

https://developer.planningcenter.com/publishing/docs
