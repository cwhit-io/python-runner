#!/usr/bin/env python3
"""
EmailOctopus API wrapper for AI agents.

Supports managing mailing lists, contacts, campaigns, and templates
via the EmailOctopus API v1.
"""

import json
import time

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

EMAILOCTOPUS_API_BASE = "https://emailoctopus.com/api/1.6"
SERVICE_NAME = "emailoctopus"


def get_api_key():
    key = os.environ.get("EMAILOCTOPUS_API_KEY")
    if not key:
        return None
    return key


def eo_request(method: str, path: str, action: str,
               params: dict | None = None,
               json_body: dict | None = None,
               timeout_seconds: int = 30) -> str:
    """Make an EmailOctopus API request. API key is sent as a query parameter."""
    api_key = get_api_key()
    if not api_key:
        return error_result(
            action,
            "EmailOctopus credentials not configured. Set EMAILOCTOPUS_API_KEY."
        )

    # EmailOctopus expects api_key as a query param
    req_params = dict(params or {})
    if "api_key" not in req_params:
        req_params["api_key"] = api_key

    return simple_api_request(
        method, f"{EMAILOCTOPUS_API_BASE}{path}", action,
        params=req_params, json_body=json_body,
        timeout_seconds=timeout_seconds,
    )


def handle_action(data: dict, action: str) -> str:
    params = build_params(data)

    if action == "list_lists":
        return eo_request("GET", "/lists", action, params=params)

    if action == "get_list":
        require_fields(data, ["list_id"], action)
        return eo_request("GET", f"/lists/{data['list_id']}", action, params=params)

    if action == "list_contacts":
        require_fields(data, ["list_id"], action)
        return eo_request(
            "GET", f"/lists/{data['list_id']}/contacts", action, params=params
        )

    if action == "get_contact":
        require_fields(data, ["list_id", "contact_id"], action)
        return eo_request(
            "GET", f"/lists/{data['list_id']}/contacts/{data['contact_id']}",
            action, params=params
        )

    if action == "create_contact":
        require_fields(data, ["list_id", "email"], action)
        body = {
            "email_address": data["email"],
        }
        if data.get("fields"):
            body["fields"] = data["fields"]
        if data.get("tags"):
            body["tags"] = data["tags"]
        if data.get("status"):
            body["status"] = data["status"]

        url = f"/lists/{data['list_id']}/contacts"
        if data.get("dry_run", False):
            return build_dry_run_response(action, "POST",
                                          f"{EMAILOCTOPUS_API_BASE}{url}", body=body)
        return eo_request("POST", url, action, json_body=body)

    if action == "update_contact":
        require_fields(data, ["list_id", "contact_id"], action)
        body = {}
        if data.get("email"):
            body["email_address"] = data["email"]
        if data.get("fields"):
            body["fields"] = data["fields"]
        if data.get("tags"):
            body["tags"] = data["tags"]
        if data.get("status"):
            body["status"] = data["status"]

        url = f"/lists/{data['list_id']}/contacts/{data['contact_id']}"
        if data.get("dry_run", False):
            return build_dry_run_response(action, "PUT",
                                          f"{EMAILOCTOPUS_API_BASE}{url}", body=body)
        return eo_request("PUT", url, action, json_body=body)

    if action == "list_campaigns":
        return eo_request("GET", "/campaigns", action, params=params)

    if action == "get_campaign":
        require_fields(data, ["campaign_id"], action)
        return eo_request(
            "GET", f"/campaigns/{data['campaign_id']}", action, params=params
        )

    if action == "create_draft_campaign":
        require_fields(data, ["list_id", "subject", "name"], action)
        body = {
            "subject": data["subject"],
            "name": data["name"],
            "list_id": data["list_id"],
        }
        if data.get("from_name"):
            body["from_name"] = data["from_name"]
        if data.get("reply_to"):
            body["reply_to"] = data["reply_to"]
        if data.get("template_id"):
            body["template_id"] = data["template_id"]
        if data.get("content"):
            body["content"] = data["content"]

        if data.get("dry_run", False):
            return build_dry_run_response(action, "POST",
                                          f"{EMAILOCTOPUS_API_BASE}/campaigns", body=body)
        return eo_request("POST", "/campaigns", action, json_body=body)

    if action == "list_templates":
        return eo_request("GET", "/templates", action, params=params)

    return error_result(action, f"Unknown action: {action}")


def build_params(data: dict) -> dict:
    params = {}
    for key in ("per_page", "page", "search", "order_by", "direction"):
        if key in data:
            params[key] = data[key]
    return params


def main():
    run_wrapper(handle_action, SERVICE_NAME)


if __name__ == "__main__":
    main()
