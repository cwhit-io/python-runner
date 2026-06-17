# SermonShots API Wrapper

AI-callable wrapper for the SermonShots API.

## Supported Actions

### Read-only
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `list_videos` | List all videos | — |
| `get_video` | Get video details | `video_id` |
| `get_transcript` | Get video transcript | `video_id` |
| `list_clips` | List clips (optionally by video) | — |
| `get_clip` | Get clip details | `clip_id` |
| `list_generated_content` | List generated content (optionally by video) | — |
| `get_summary` | Get AI sermon summary | `video_id` |
| `get_blog_post` | Get AI-generated blog post | `video_id` |
| `get_devotional` | Get AI-generated devotional | `video_id` |
| `get_discussion_guide` | Get AI-generated discussion guide | `video_id` |

### Write (guarded)
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `create_video_from_url` | Create a video from a public URL | `url` |
| `upload_video_metadata` | Update video metadata | `video_id`, `metadata` |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SERMONSHOTS_API_KEY` | Yes | SermonShots API key (Bearer token) |
| `SERMONSHOTS_API_BASE` | No | API base URL (default: `https://api.sermonshots.com`) |

## CLI Usage

```bash
# List videos
python ai_scripts/sermonshots/wrapper.py '{"action":"list_videos","per_page":5}'

# Get video
python ai_scripts/sermonshots/wrapper.py '{"action":"get_video","video_id":"123"}'

# Get transcript
python ai_scripts/sermonshots/wrapper.py '{"action":"get_transcript","video_id":"123"}'

# Get summary
python ai_scripts/sermonshots/wrapper.py '{"action":"get_summary","video_id":"123"}'

# Create video from URL (dry-run)
python ai_scripts/sermonshots/wrapper.py '{"action":"create_video_from_url","url":"https://example.com/sermon.mp4","dry_run":true}'
```

## Notes

- API documentation available at https://sermonshots.com/api/
- Endpoint paths may vary; the wrapper uses RESTful conventions
- Generated content (summary, blog, devotional, discussion guide) endpoints are based on common sermon video API patterns
- If your API base differs, set `SERMONSHOTS_API_BASE` environment variable

## API Docs

https://sermonshots.com/api/
