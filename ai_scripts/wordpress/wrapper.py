#!/usr/bin/env python3
"""
WordPress REST API wrapper for AI agents.

Supports listing and managing posts, pages, media, categories, and tags
via the WordPress REST API v2 (Application Password auth).
"""

import base64
import json
import time

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from shared.wrapper_utils import (
    build_dry_run_response,
    error_result,
    require_fields,
    run_wrapper,
    simple_api_request,
)

SERVICE_NAME = "wordpress"

# Full page/post payloads can exceed PHP limits on large per_page values.
MAX_PER_PAGE = 25
LIST_DEFAULT_FIELDS = (
    "id,title,slug,link,status,modified,parent,menu_order,author,"
    "featured_media,type"
)


def get_site_url() -> str | None:
    site = os.environ.get("WORDPRESS_SITE_URL", "").strip().rstrip("/")
    return site or None


def get_api_base() -> str | None:
    site = get_site_url()
    if not site:
        return None
    return f"{site}/wp-json/wp/v2"


def get_basic_auth_token() -> str | None:
    username = os.environ.get("WORDPRESS_USERNAME", "").strip()
    password = os.environ.get("WORDPRESS_APP_PASSWORD", "").strip()
    if not username or not password:
        return None
    return base64.b64encode(f"{username}:{password}".encode()).decode()


def wp_request(
    method: str,
    path: str,
    action: str,
    params: dict | None = None,
    json_body: dict | None = None,
    require_auth: bool = False,
    timeout_seconds: int = 30,
) -> str:
    """Make a WordPress REST API request with optional Basic auth."""
    api_base = get_api_base()
    if not api_base:
        return error_result(
            action,
            "WordPress site not configured. Set WORDPRESS_SITE_URL.",
        )

    auth = get_basic_auth_token()
    if require_auth and not auth:
        return error_result(
            action,
            "WordPress credentials required. Set WORDPRESS_USERNAME and "
            "WORDPRESS_APP_PASSWORD.",
        )

    return simple_api_request(
        method,
        f"{api_base}{path}",
        action,
        api_key=auth,
        api_key_header="Authorization",
        api_key_prefix="Basic ",
        params=params,
        json_body=json_body,
        timeout_seconds=timeout_seconds,
    )


def build_list_params(data: dict, *, apply_list_defaults: bool = False) -> dict:
    """Map wrapper input to WordPress collection query parameters."""
    params = {}
    mapping = {
        "page": "page",
        "wp_page": "page",
        "search": "search",
        "slug": "slug",
        "status": "status",
        "categories": "categories",
        "tags": "tags",
        "orderby": "orderby",
        "order": "order",
        "parent": "parent",
        "wp_context": "context",
        "fields": "_fields",
    }
    for src, dst in mapping.items():
        if src in data and data[src] is not None:
            params[dst] = data[src]

    if "per_page" in data and data["per_page"] is not None:
        params["per_page"] = min(int(data["per_page"]), MAX_PER_PAGE)
    elif apply_list_defaults:
        params["per_page"] = 10

    if apply_list_defaults and not data.get("fields") and not data.get("include_content"):
        params["_fields"] = LIST_DEFAULT_FIELDS

    # CLI backward compat only — do not use via MCP (conflicts with Context param)
    if "context" in data and data["context"] is not None and "wp_context" not in data:
        params["context"] = data["context"]
    return params


def build_content_body(data: dict) -> dict:
    """Build a post/page create or update body from input fields."""
    body = {}
    for key in (
        "title",
        "content",
        "excerpt",
        "status",
        "slug",
        "featured_media",
        "categories",
        "tags",
        "parent",
        "menu_order",
        "comment_status",
        "ping_status",
        "template",
        "format",
    ):
        if key in data and data[key] is not None:
            body[key] = data[key]
    return body


def write_content(
    data: dict,
    action: str,
    resource: str,
    item_id: str | None = None,
) -> str:
    """Create or update a WordPress post or page."""
    body = build_content_body(data)
    if not body:
        raise ValueError(
            f"At least one content field is required for action '{action}'"
        )

    method = "POST" if item_id is None else "POST"
    path = f"/{resource}" if item_id is None else f"/{resource}/{item_id}"
    api_base = get_api_base() or ""

    if data.get("dry_run", False):
        return build_dry_run_response(
            action, method, f"{api_base}{path}", body=body
        )
    return wp_request(
        method, path, action, json_body=body, require_auth=True
    )


def handle_action(data: dict, action: str) -> str:
    timeout = data.get("request_timeout_seconds", data.get("timeout_seconds", 30))

    # ── Posts ─────────────────────────────────────────────────────────────

    if action == "list_posts":
        params = build_list_params(data, apply_list_defaults=True)
        return wp_request(
            "GET", "/posts", action, params=params, timeout_seconds=timeout
        )

    if action == "get_post":
        require_fields(data, ["post_id"], action)
        params = build_list_params(data)
        return wp_request(
            "GET",
            f"/posts/{data['post_id']}",
            action,
            params=params,
            timeout_seconds=timeout,
        )

    if action == "create_post":
        require_fields(data, ["title"], action)
        return write_content(data, action, "posts")

    if action == "update_post":
        require_fields(data, ["post_id"], action)
        return write_content(data, action, "posts", item_id=data["post_id"])

    # ── Pages ─────────────────────────────────────────────────────────────

    if action == "list_pages":
        params = build_list_params(data, apply_list_defaults=True)
        return wp_request(
            "GET", "/pages", action, params=params, timeout_seconds=timeout
        )

    if action == "get_page":
        require_fields(data, ["page_id"], action)
        params = build_list_params(data)
        return wp_request(
            "GET",
            f"/pages/{data['page_id']}",
            action,
            params=params,
            timeout_seconds=timeout,
        )

    if action == "create_page":
        require_fields(data, ["title"], action)
        return write_content(data, action, "pages")

    if action == "update_page":
        require_fields(data, ["page_id"], action)
        return write_content(data, action, "pages", item_id=data["page_id"])

    # ── Taxonomy & media ──────────────────────────────────────────────────

    if action == "list_categories":
        params = build_list_params(data, apply_list_defaults=True)
        return wp_request(
            "GET", "/categories", action, params=params, timeout_seconds=timeout
        )

    if action == "list_tags":
        params = build_list_params(data, apply_list_defaults=True)
        return wp_request(
            "GET", "/tags", action, params=params, timeout_seconds=timeout
        )

    if action == "list_media":
        params = build_list_params(data, apply_list_defaults=True)
        return wp_request(
            "GET", "/media", action, params=params, timeout_seconds=timeout
        )

    if action == "get_media":
        require_fields(data, ["media_id"], action)
        params = build_list_params(data)
        return wp_request(
            "GET",
            f"/media/{data['media_id']}",
            action,
            params=params,
            timeout_seconds=timeout,
        )

    # ── Search & auth ─────────────────────────────────────────────────────

    if action == "search":
        search_params = build_list_params(data, apply_list_defaults=True)
        if data.get("type"):
            search_params["type"] = data["type"]
        if data.get("subtype"):
            search_params["subtype"] = data["subtype"]
        return wp_request(
            "GET",
            "/search",
            action,
            params=search_params,
            timeout_seconds=timeout,
        )

    if action == "get_current_user":
        return wp_request(
            "GET", "/users/me", action, require_auth=True, timeout_seconds=timeout
        )

    return error_result(action, f"Unknown action: {action}")


def main():
    run_wrapper(handle_action, SERVICE_NAME)


if __name__ == "__main__":
    main()