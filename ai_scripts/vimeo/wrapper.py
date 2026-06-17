#!/usr/bin/env python3
"""
Vimeo API wrapper for AI agents.

Supports listing recent videos, searching videos, getting video details,
finding livestreams, updating video metadata, and preparing uploads
via the Vimeo API.
"""

import sys
import os

# ── Inline shared utilities ──────────────────────────────────────────

class Timer:
    """Simple context manager for measuring duration in milliseconds."""

    def __init__(self):
        self.start: float = 0.0
        self.duration_ms: float = 0.0

    def __enter__(self):
        self.start = time.monotonic()
        return self

    def __exit__(self, *args):
        self.duration_ms = (time.monotonic() - self.start) * 1000

def error_exit(error: str, action: str = "", warnings: list | None = None,
               meta: dict | None = None) -> None:
    """Print an error result and exit with code 1."""
    print(error_result(action or "unknown", error, warnings, meta))
    sys.exit(1)

def error_result(action: str, error: str, warnings: list | None = None,
                 meta: dict | None = None, status_code: int | None = None) -> str:
    """Return a standardized error JSON string."""
    result = {
        "success": False,
        "action": action,
        "data": None,
        "warnings": warnings or [],
        "error": error,
        "meta": {
            **(meta or {}),
        },
    }
    if status_code is not None:
        result["status_code"] = status_code
    return json.dumps(result, indent=2, default=str)

def success_result(action: str, data, warnings: list | None = None,
                   meta: dict | None = None) -> str:
    """Return a standardized success JSON string."""
    result = {
        "success": True,
        "action": action,
        "data": data,
        "warnings": warnings or [],
        "meta": {
            **(meta or {}),
        },
    }
    return json.dumps(result, indent=2, default=str)

def parse_input() -> dict:
    """Read a JSON object from argv[1] or stdin.

    Returns:
        Parsed dict, or {} on empty input.

    Raises:
        SystemExit(1) if JSON is invalid.
    """
    raw = None
    if len(sys.argv) > 1 and sys.argv[1].strip():
        raw = sys.argv[1]
    else:
        try:
            data = sys.stdin.read()
            if data.strip():
                raw = data
        except Exception:
            pass

    if not raw:
        return {}

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        error_exit(f"Invalid JSON input: {e}")

def require_action(data: dict) -> str:
    """Extract and return the 'action' field or raise ValueError."""
    action = data.get("action")
    if not action:
        raise ValueError("Missing required field: 'action'")
    return action

def require_fields(data: dict, fields: list[str], action: str = "") -> None:
    """Raise ValueError if any required fields are missing."""
    missing = [f for f in fields if f not in data or data[f] is None]
    if missing:
        label = f" for action '{action}'" if action else ""
        raise ValueError(f"Missing required field(s){label}: {', '.join(missing)}")

def build_dry_run_response(action: str, method: str, url: str,
                           headers: dict | None = None,
                           body: dict | None = None) -> str:
    """Return a dry-run result describing what would have been sent."""
    payload = {
        "dry_run": True,
        "method": method.upper(),
        "url": url,
    }
    # Strip Authorization from headers shown in dry-run
    safe_headers = dict(headers or {})
    if "Authorization" in safe_headers:
        safe_headers["Authorization"] = "Bearer <redacted>" if "Bearer" in safe_headers["Authorization"] else "Basic <redacted>"
    if safe_headers:
        payload["headers"] = safe_headers
    if body:
        payload["body"] = body
    return success_result(action, payload,
                          warnings=["Dry-run: no request was sent"])

def simple_api_request(method: str, url: str, action: str,
                       api_key: str | None = None,
                       api_key_header: str = "Authorization",
                       api_key_prefix: str = "Bearer ",
                       params: dict | None = None,
                       json_body: dict | None = None,
                       timeout_seconds: int = 30) -> str:
    """Make a simple REST API request with optional API key auth.

    Args:
        method: HTTP method (GET, POST, PATCH, DELETE, etc.)
        url: Full request URL
        action: Action name for result formatting
        api_key: Optional API key/token
        api_key_header: Header name for the API key
        api_key_prefix: Prefix before the key value (e.g. 'Bearer ' or '')
        params: Query parameters
        json_body: JSON body for POST/PATCH/PUT
        timeout_seconds: Request timeout

    Returns:
        JSON result string.
    """
    import requests as req

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    if api_key:
        headers[api_key_header] = f"{api_key_prefix}{api_key}"

    try:
        resp = req.request(
            method, url,
            headers=headers,
            params=params,
            json=json_body,
            timeout=timeout_seconds,
        )
        resp.raise_for_status()
        if resp.content:
            data = resp.json()
        else:
            data = {"status": resp.status_code, "message": "No content"}
        return success_result(action, data)

    except req.exceptions.Timeout:
        return error_result(action, f"Request timed out after {timeout_seconds}s")
    except req.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        detail = ""
        try:
            detail = e.response.json() if e.response is not None else ""
        except Exception:
            detail = e.response.text[:500] if e.response is not None else ""
        return error_result(action, f"HTTP {status}: {detail}", status_code=status)
    except req.exceptions.ConnectionError:
        return error_result(action, "Connection error: unable to reach API")
    except req.exceptions.RequestException as e:
        return error_result(action, f"Request failed: {e}")

def run_wrapper(handler_fn, service_name: str) -> None:
    """Standard entry point for a wrapper script.

    Args:
        handler_fn: Callable that takes (data, action) and returns a JSON string.
        service_name: Service name for meta timing.
    """
    with Timer() as timer:
        try:
            data = parse_input()
            action = require_action(data)
            result = handler_fn(data, action)
        except SystemExit:
            raise
        except ValueError as e:
            result = error_result("", str(e))
        except Exception as e:
            result = error_result("", str(e))

    # Inject timing into meta
    result_obj = json.loads(result)
    if "meta" not in result_obj:
        result_obj["meta"] = {}
    result_obj["meta"]["service"] = service_name
    result_obj["meta"]["duration_ms"] = round(timer.duration_ms, 1)
    print(json.dumps(result_obj, indent=2, default=str))

VIMEO_API_BASE = "https://api.vimeo.com"
SERVICE_NAME = "vimeo"


def get_api_key():
    key = os.environ.get("VIMEO_ACCESS_TOKEN")
    if not key:
        return None
    return key


def vimeo_request(method: str, path: str, action: str,
                  params: dict | None = None,
                  json_body: dict | None = None,
                  timeout_seconds: int = 30) -> str:
    """Make a Vimeo API request with Bearer token auth."""
    api_key = get_api_key()
    if not api_key:
        return error_result(
            action,
            "Vimeo credentials not configured. Set VIMEO_ACCESS_TOKEN."
        )
    return simple_api_request(
        method, f"{VIMEO_API_BASE}{path}", action,
        api_key=api_key, api_key_prefix="Bearer ",
        params=params, json_body=json_body,
        timeout_seconds=timeout_seconds,
    )


def handle_action(data: dict, action: str) -> str:
    params = build_params(data)

    if action == "list_recent_videos":
        return vimeo_request("GET", "/me/videos", action, params=params)

    if action == "search_videos":
        query = data.get("query", "")
        if query:
            params["query"] = query
        return vimeo_request("GET", "/videos", action, params=params)

    if action == "get_video":
        require_fields(data, ["video_id"], action)
        return vimeo_request(
            "GET", f"/videos/{data['video_id']}", action, params=params
        )

    if action == "find_recent_livestreams":
        params["filter"] = "live"
        params["sort"] = "date"
        return vimeo_request("GET", "/me/videos", action, params=params)

    if action == "update_video_metadata":
        require_fields(data, ["video_id", "data"], action)
        url = f"/videos/{data['video_id']}"
        if data.get("dry_run", False):
            return build_dry_run_response(action, "PATCH",
                                          f"{VIMEO_API_BASE}{url}", body=data["data"])
        return vimeo_request("PATCH", url, action, json_body=data["data"])

    if action == "prepare_upload":
        """Initiate a video upload using Vimeo's tus-based upload protocol.
        Returns an upload ticket with the upload link.
        """
        require_fields(data, ["upload_type"], action)
        body = {
            "upload": {
                "approach": "tus",
                "size": data.get("file_size", 0),
            },
            "name": data.get("name", "AI Upload"),
        }
        if data.get("description"):
            body["description"] = data["description"]
        if data.get("privacy"):
            body["privacy"] = {"view": data["privacy"]}

        if data.get("dry_run", False):
            return build_dry_run_response(action, "POST",
                                          f"{VIMEO_API_BASE}/me/videos", body=body)
        return vimeo_request("POST", "/me/videos", action, json_body=body)

    return error_result(action, f"Unknown action: {action}")


def build_params(data: dict) -> dict:
    params = {}
    for key in ("per_page", "page", "sort", "direction", "query", "filter", "fields"):
        if key in data:
            params[key] = data[key]
    # Vimeo uses 'per_page', 'page' for pagination
    if "per_page" not in params and "per_page" in data:
        params["per_page"] = str(data["per_page"])
    return params


def main():
    run_wrapper(handle_action, SERVICE_NAME)


if __name__ == "__main__":
    main()
