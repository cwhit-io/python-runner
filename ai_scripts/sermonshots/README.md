# SermonShots API Wrapper

AI-callable wrapper for the SermonShots API. Matches the [OpenAPI 3.0 spec](https://api.sermonshots.com/docs).

## Supported Actions

### Read-only
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `get_church_meta` | Get public church metadata (no auth) | `church_name` |
| `list_videos` | List all videos | — |
| `get_video` | Get video details | `video_id` |
| `get_transcript` | Get video transcription | `video_id` |
| `list_clips` | List clips for a video | `video_id` |
| `get_images` | Get sermon images by type | `video_id`, `image_type` |
| `get_downloadable` | Get downloadable content by type | `video_id`, `downloadable_type` |
| `get_all_content` | Get all generated content at once | `video_id` |
| `get_summary` | Get AI sermon summary | `video_id` |
| `get_blog_post` | Get AI-generated blog post | `video_id` |
| `get_devotionals` | Get AI-generated devotionals (returns array) | `video_id` |
| `get_discussion_guide` | Get AI-generated discussion guide | `video_id` |
| `get_quotes` | Get quotes | `video_id` |
| `get_titles` | Get title suggestions | `video_id` |

### Write (guarded)
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `create_video_from_url` | Upload a video from a public URL | `public_url`, `language`, `filename` |
| `create_video_from_stream` | Upload from HLS or DASH source | `source`, `public_url`, `language`, `filename` |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SERMONSHOTS_API_KEY` | Yes* | SermonShots API key (sent as `auth-token` header, no prefix) |
| `SERMONSHOTS_API_BASE` | No | API base URL (default: `https://api.sermonshots.com`) |

\*Not required for `get_church_meta` (public endpoint).

## CLI Usage

```bash
python ai_scripts/sermonshots/wrapper.py '{"action":"list_videos","limit":5}'
python ai_scripts/sermonshots/wrapper.py '{"action":"get_video","video_id":"123"}'
python ai_scripts/sermonshots/wrapper.py '{"action":"get_all_content","video_id":"123"}'
python ai_scripts/sermonshots/wrapper.py '{"action":"create_video_from_url","public_url":"https://example.com/video.mp4","language":"english","filename":"sermon","dry_run":true}'
```

## Notes

- Auth uses `auth-token` header with no prefix per the spec
- Query params use `page`, `limit`, `sort_by`, and `direction` for list_videos
- `sort: DESC` is accepted as an alias for `direction` (OpenAPI documents `sort` as direction, but the live API expects a field + `direction`)
- `language` uses full names per spec (e.g. `english`, not `en`)
- Only officially documented endpoints are implemented

## API Docs

https://api.sermonshots.com/docs