# Vimeo API Wrapper

AI-callable wrapper for the Vimeo API.

## Supported Actions

### Read-only
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `list_recent_videos` | List recent videos for the authenticated user | — |
| `search_videos` | Search all videos | — (use `query`) |
| `get_video` | Get video details | `video_id` |
| `find_recent_livestreams` | Find recent live streams | — |

### Write (guarded)
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `update_video_metadata` | Update video name/description/privacy | `video_id`, `data` |
| `prepare_upload` | Create a tus upload ticket (not upload binary) | `name` |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VIMEO_ACCESS_TOKEN` | Yes | Vimeo API access token (Bearer auth) |

## CLI Usage

```bash
# List recent videos
python ai_scripts/vimeo/wrapper.py '{"action":"list_recent_videos","per_page":5}'

# Search videos
python ai_scripts/vimeo/wrapper.py '{"action":"search_videos","query":"sermon"}'

# Get video details
python ai_scripts/vimeo/wrapper.py '{"action":"get_video","video_id":"123456789"}'

# Update metadata (dry-run)
python ai_scripts/vimeo/wrapper.py '{"action":"update_video_metadata","video_id":"123456789","data":{"name":"New Title"},"dry_run":true}'

# Prepare upload ticket
python ai_scripts/vimeo/wrapper.py '{"action":"prepare_upload","name":"My Video","file_size":104857600,"dry_run":true}'
```

## Notes

- `prepare_upload` creates a tus upload ticket only — it does not upload binary data
- Video file upload would need a separate chunked upload step
- The Vimeo API uses OAuth2 Bearer tokens

## API Docs

https://developer.vimeo.com/api/reference
