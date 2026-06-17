#!/usr/bin/env python3
"""
Planning Center Giving API wrapper for AI agents.

Read-only wrapper for donations, funds, batches, designations,
recurring donations, and refunds via the Planning Center Giving API.

Write/destructive actions are intentionally omitted.
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

def build_planning_center_auth() -> tuple[str, str] | str | None:
    """Build auth for Planning Center API.

    Returns:
        - A (client_id, secret) tuple for Basic auth if those env vars are set.
        - A Bearer token string if PLANNING_CENTER_ACCESS_TOKEN is set.
        - None if neither is configured.
    """
    access_token = os.environ.get("PLANNING_CENTER_ACCESS_TOKEN")
    client_id = os.environ.get("PLANNING_CENTER_CLIENT_ID")
    client_secret = os.environ.get("PLANNING_CENTER_CLIENT_SECRET")

    if access_token:
        return access_token  # Bearer token
    if client_id and client_secret:
        return (client_id, client_secret)  # Basic auth tuple
    return None

def planning_center_request(method: str, url: str, action: str,
                            params: dict | None = None,
                            json_body: dict | None = None,
                            timeout_seconds: int = 30) -> str:
    """Make a Planning Center API request with consistent auth/error handling.

    Returns a JSON result string (success or error).
    """
    import requests as req

    auth = build_planning_center_auth()
    if auth is None:
        return error_result(
            action,
            "Planning Center credentials not configured. "
            "Set PLANNING_CENTER_ACCESS_TOKEN or "
            "PLANNING_CENTER_CLIENT_ID + PLANNING_CENTER_CLIENT_SECRET."
        )

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    try:
        if isinstance(auth, tuple):
            # Basic auth with client_id:client_secret
            resp = req.request(
                method, url, auth=auth,
                headers=headers, params=params,
                json=json_body, timeout=timeout_seconds,
            )
        else:
            # Bearer token auth
            headers["Authorization"] = f"Bearer {auth}"
            resp = req.request(
                method, url,
                headers=headers, params=params,
                json=json_body, timeout=timeout_seconds,
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

BASE_URL = "https://api.planningcenteronline.com/giving/v2"
SERVICE_NAME = "planning_center_giving"


def handle_action(data: dict, action: str) -> str:
    params = build_params(data)

    if action == "list_donations":
        return planning_center_request("GET", f"{BASE_URL}/donations", action, params=params)

    if action == "get_donation":
        require_fields(data, ["donation_id"], action)
        return planning_center_request(
            "GET", f"{BASE_URL}/donations/{data['donation_id']}", action, params=params
        )

    if action == "list_funds":
        return planning_center_request("GET", f"{BASE_URL}/funds", action, params=params)

    if action == "list_batches":
        return planning_center_request("GET", f"{BASE_URL}/batches", action, params=params)

    if action == "list_designations":
        params = build_params(data)
        if data.get("donation_id"):
            return planning_center_request(
                "GET", f"{BASE_URL}/donations/{data['donation_id']}/designations",
                action, params=params
            )
        return planning_center_request("GET", f"{BASE_URL}/designations", action, params=params)

    if action == "list_recurring_donations":
        return planning_center_request(
            "GET", f"{BASE_URL}/recurring_donations", action, params=params
        )

    if action == "list_refunds":
        return planning_center_request("GET", f"{BASE_URL}/refunds", action, params=params)

    return error_result(action, f"Unknown action: {action}")


def build_params(data: dict) -> dict:
    params = {}
    for key in ("per_page", "offset", "order", "include", "where", "filter", "query", "fields"):
        if key in data:
            params[key] = data[key]
    return params


def main():
    run_wrapper(handle_action, SERVICE_NAME)


if __name__ == "__main__":
    main()
