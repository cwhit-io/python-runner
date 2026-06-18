# WordPress REST API Wrapper

AI-callable wrapper for the [WordPress REST API v2](https://developer.wordpress.org/rest-api/).

## Supported Actions

### Read-only
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `list_posts` | List posts | — |
| `get_post` | Get a post by ID | `post_id` |
| `list_pages` | List pages | — |
| `get_page` | Get a page by ID | `page_id` |
| `list_categories` | List categories | — |
| `list_tags` | List tags | — |
| `list_media` | List media items | — |
| `get_media` | Get a media item | `media_id` |
| `search` | Search site content | — (use `search`) |
| `get_current_user` | Verify auth / get current user | — |

### Write (guarded)
| Action | Description | Required Fields |
|--------|-------------|-----------------|
| `create_post` | Create a post | `title` |
| `update_post` | Update a post | `post_id` |
| `create_page` | Create a page | `title` |
| `update_page` | Update a page | `page_id` |

All write actions support `dry_run`. No delete actions are implemented.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `WORDPRESS_SITE_URL` | Yes | Site base URL (e.g. `https://yoursite.org`) |
| `WORDPRESS_USERNAME` | For writes / private content | WordPress username |
| `WORDPRESS_APP_PASSWORD` | For writes / private content | Application Password from WP admin |

Create an Application Password under **Users → Profile → Application Passwords** in WordPress.

## CLI Usage

```bash
# List published posts (public, no auth needed)
python ai_scripts/wordpress/wrapper.py '{"action":"list_posts","per_page":5,"status":"publish"}'

# Search
python ai_scripts/wordpress/wrapper.py '{"action":"search","search":"sermon"}'

# Create draft post (dry-run)
python ai_scripts/wordpress/wrapper.py '{"action":"create_post","title":"Test","status":"draft","dry_run":true}'

# Verify credentials
python ai_scripts/wordpress/wrapper.py '{"action":"get_current_user"}'
```

## Notes

- Uses Application Password Basic auth (`username:app_password` base64)
- Published content is readable without auth; drafts/private content need credentials
- Pagination uses `per_page` and `wp_page` (not `page` — clearer and avoids ambiguity)
- List actions return metadata-only by default (`id`, `title`, `slug`, `link`, etc.). Pass `include_content: true` for full HTML bodies
- `per_page` is capped at 25 — higher values can trigger WordPress HTTP 500 errors on this site
- Use `wp_context` (not `context`) for WordPress response detail level — `context` is reserved by ScriptDash MCP
- Use `request_timeout_seconds` for HTTP timeout — `timeout_seconds` is reserved by ScriptDash MCP for script execution time

## API Docs

https://developer.wordpress.org/rest-api/reference/