# Planning Center Giving Wrapper

AI-callable wrapper for the Planning Center Giving API.

## Supported Actions

### Read-only (no write actions)
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `list_donations` | List all donations | — |
| `get_donation` | Get donation details | `donation_id` |
| `list_funds` | List all funds | — |
| `list_batches` | List all batches | — |
| `list_designations` | List designations (optionally for a donation) | — |
| `list_recurring_donations` | List recurring donations | — |
| `list_refunds` | List all refunds | — |

This wrapper is intentionally read-only. No create, update, or delete actions are implemented.

## CLI Usage

```bash
python ai_scripts/planning_center_giving/wrapper.py '{"action":"list_donations","per_page":5}'
python ai_scripts/planning_center_giving/wrapper.py '{"action":"get_donation","donation_id":"123456"}'
python ai_scripts/planning_center_giving/wrapper.py '{"action":"list_funds"}'
```

## API Docs

https://developer.planningcenter.com/giving/docs
