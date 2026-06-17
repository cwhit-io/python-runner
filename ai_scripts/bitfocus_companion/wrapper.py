#!/usr/bin/env python3
"""
Bitfocus Companion HTTP remote control wrapper for AI agents.

Supports pressing buttons, rotating encoders, setting styles,
managing custom/module variables, and rescanning surfaces.
Targets Companion v4.x HTTP API.
"""

import sys
import os
import json

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

COMPANION_DEFAULT_BASE = "http://localhost:8000"
SERVICE_NAME = "bitfocus_companion"


def get_config():
    """Get Companion connection config from environment."""
    base_url = os.environ.get("COMPANION_BASE_URL", COMPANION_DEFAULT_BASE).rstrip("/")
    token = os.environ.get("COMPANION_API_KEY") or os.environ.get("COMPANION_TOKEN") or ""
    return base_url, token


def companion_request(method: str, path: str, action: str,
                      json_body: dict | None = None,
                      timeout_seconds: int = 10) -> str:
    """Make a request to Companion's HTTP API."""
    import requests as req

    base_url, token = get_config()
    url = f"{base_url}{path}"

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = req.request(
            method, url, headers=headers,
            json=json_body, timeout=timeout_seconds,
        )
        resp.raise_for_status()
        if resp.content:
            data = resp.json()
        else:
            data = {"status": resp.status_code}
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
        return error_result(
            action,
            f"Connection error: unable to reach Companion at {base_url}. "
            "Ensure Companion is running and COMPANION_BASE_URL is correct."
        )
    except req.exceptions.RequestException as e:
        return error_result(action, f"Request failed: {e}")


def build_location_path(data: dict) -> str:
    """Build the location path segment for button/surface operations.

    Format: /<page>/<bank>/<x>/<y>
    """
    page = data.get("page", "0")
    bank = data.get("bank", "0")
    x = data.get("x", "0")
    y = data.get("y", "0")
    return f"/{page}/{bank}/{x}/{y}"


def handle_action(data: dict, action: str) -> str:
    # ── Button / Surface actions ─────────────────────────────────────────

    if action == "press_button":
        loc = build_location_path(data)
        return companion_request("POST", f"/api/location{loc}/press", action)

    if action == "button_down":
        loc = build_location_path(data)
        return companion_request("POST", f"/api/location{loc}/down", action)

    if action == "button_up":
        loc = build_location_path(data)
        return companion_request("POST", f"/api/location{loc}/up", action)

    if action == "rotate_left":
        loc = build_location_path(data)
        return companion_request("POST", f"/api/location{loc}/rotate-left", action)

    if action == "rotate_right":
        loc = build_location_path(data)
        return companion_request("POST", f"/api/location{loc}/rotate-right", action)

    if action == "set_step":
        require_fields(data, ["step"], action)
        loc = build_location_path(data)
        return companion_request(
            "POST", f"/api/location{loc}/step/{data['step']}", action
        )

    if action == "set_button_style":
        require_fields(data, ["style"], action)
        loc = build_location_path(data)
        body = data.get("style", {})
        return companion_request(
            "PUT", f"/api/location{loc}/style", action, json_body=body
        )

    # ── Custom variables ─────────────────────────────────────────────────

    if action == "set_custom_variable":
        require_fields(data, ["name", "value"], action)
        return companion_request(
            "PUT",
            f"/api/custom-variable/{data['name']}/value",
            action,
            json_body={"value": data["value"]},
        )

    if action == "get_custom_variable":
        require_fields(data, ["name"], action)
        return companion_request(
            "GET",
            f"/api/custom-variable/{data['name']}/value",
            action,
        )

    # ── Module variables ─────────────────────────────────────────────────

    if action == "get_module_variable":
        require_fields(data, ["module_name", "variable_name"], action)
        return companion_request(
            "GET",
            f"/api/variable/{data['module_name']}/{data['variable_name']}/value",
            action,
        )

    # ── Surface management ───────────────────────────────────────────────

    if action == "rescan_surfaces":
        return companion_request("POST", "/api/surfaces/rescan", action)

    return error_result(action, f"Unknown action: {action}")


def main():
    run_wrapper(handle_action, SERVICE_NAME)


if __name__ == "__main__":
    main()
