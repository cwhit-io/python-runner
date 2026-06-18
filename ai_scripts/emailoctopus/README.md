# EmailOctopus API Wrapper

AI-callable wrapper for the EmailOctopus API v1.6.

## Supported Actions

### Read-only
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `list_lists` | List all mailing lists | — |
| `get_list` | Get list details | `list_id` |
| `list_contacts` | List contacts in a list | `list_id` |
| `get_contact` | Get contact details | `list_id`, `contact_id` |
| `list_campaigns` | List all campaigns | — |
| `get_campaign` | Get campaign details | `campaign_id` |

### Write (guarded)
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `create_contact` | Add a contact to a list | `list_id`, `email` |
| `update_contact` | Update contact fields/tags | `list_id`, `contact_id` |

All write actions support `dry_run`.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `EMAILOCTOPUS_API_KEY` | Yes | EmailOctopus API key |

## CLI Usage

```bash
# List lists
python ai_scripts/emailoctopus/wrapper.py '{"action":"list_lists","per_page":5}'

# List contacts
python ai_scripts/emailoctopus/wrapper.py '{"action":"list_contacts","list_id":"abc123"}'

# Create contact (dry-run)
python ai_scripts/emailoctopus/wrapper.py '{"action":"create_contact","list_id":"abc123","email":"user@example.com","dry_run":true}'

# List campaigns
python ai_scripts/emailoctopus/wrapper.py '{"action":"list_campaigns"}'
```

## Notes

- API key is sent as a query parameter per EmailOctopus API spec
- Only officially documented v1.6 endpoints are implemented
- No destructive delete actions are implemented

## API Docs

https://emailoctopus.com/api-documentation