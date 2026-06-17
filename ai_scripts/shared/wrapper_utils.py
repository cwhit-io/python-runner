#!/usr/bin/env python3
"""Shared helpers for AI-callable API wrapper scripts.

Each wrapper accepts one JSON object from argv[1] or stdin and prints one JSON
result object. The helpers avoid third-party dependencies so these scripts are
portable inside ScriptDash or a local shell.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterable, Mapping, Optional

Json = Dict[str, Any]


def read_input() -> Json:
    raw = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read()
    raw = (raw or "{}").strip() or "{}"
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Input must be valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Input must be a single JSON object")
    return data


def require(data: Mapping[str, Any], *fields: str) -> None:
    missing = [field for field in fields if data.get(field) in (None, "")]
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")


def pick(data: Mapping[str, Any], *fields: str) -> Json:
    return {field: data[field] for field in fields if field in data and data[field] is not None}


def boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def result(success: bool, action: str, service: str, data: Any = None, warnings: Optional[list[str]] = None,
           error: Optional[str] = None, started_at: Optional[float] = None, meta: Optional[Json] = None) -> Json:
    payload: Json = {
        "success": success,
        "action": action,
        "data": data,
        "warnings": warnings or [],
        "meta": {"service": service},
    }
    if started_at is not None:
        payload["meta"]["duration_ms"] = int((time.time() - started_at) * 1000)
    if meta:
        payload["meta"].update(meta)
    if error:
        payload["error"] = error
    return payload


def print_json(payload: Json) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def env_any(*names: str, required: bool = False) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    if required:
        raise RuntimeError(f"Missing required environment variable. Tried: {', '.join(names)}")
    return None


def build_query(params: Optional[Mapping[str, Any]]) -> str:
    if not params:
        return ""
    cleaned: Json = {}
    for key, value in params.items():
        if value is None or value == "":
            continue
        if isinstance(value, (list, tuple)):
            cleaned[key] = ",".join(str(v) for v in value)
        else:
            cleaned[key] = str(value)
    return urllib.parse.urlencode(cleaned)


def join_url(base: str, path: str) -> str:
    return base.rstrip("/") + "/" + path.lstrip("/")


def http_request(method: str, url: str, *, headers: Optional[Mapping[str, str]] = None,
                 query: Optional[Mapping[str, Any]] = None, body: Any = None,
                 timeout: int = 30) -> Json:
    qs = build_query(query)
    full_url = f"{url}?{qs}" if qs else url
    data = None
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update({k: v for k, v in headers.items() if v is not None})
    if body is not None:
        if isinstance(body, (str, bytes)):
            data = body.encode("utf-8") if isinstance(body, str) else body
        else:
            data = json.dumps(body).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(full_url, data=data, headers=request_headers, method=method.upper())
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
            parsed: Any
            try:
                parsed = json.loads(text) if text else None
            except json.JSONDecodeError:
                parsed = text
            return {
                "ok": 200 <= response.status < 300,
                "status": response.status,
                "url": full_url,
                "duration_ms": int((time.time() - started) * 1000),
                "body": parsed,
            }
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(text) if text else None
        except json.JSONDecodeError:
            parsed = text
        return {"ok": False, "status": exc.code, "url": full_url, "duration_ms": int((time.time() - started) * 1000), "body": parsed}
    except Exception as exc:
        return {"ok": False, "status": None, "url": full_url, "duration_ms": int((time.time() - started) * 1000), "body": None, "error": str(exc)}


def basic_auth_header(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def json_api_payload(resource_type: str, attributes: Optional[Mapping[str, Any]] = None,
                     relationships: Optional[Mapping[str, Any]] = None, resource_id: Optional[str] = None) -> Json:
    data: Json = {"type": resource_type}
    if resource_id:
        data["id"] = str(resource_id)
    if attributes:
        data["attributes"] = dict(attributes)
    if relationships:
        data["relationships"] = dict(relationships)
    return {"data": data}


def run_wrapper(service: str, handler) -> None:
    started = time.time()
    action = "unknown"
    try:
        data = read_input()
        action = str(data.get("action", "")).strip()
        if not action:
            raise ValueError("Missing required field: action")
        output = handler(data, started)
        print_json(output)
    except Exception as exc:
        print_json(result(False, action, service, data=None, error=str(exc), started_at=started,
                          meta={"traceback": traceback.format_exc(limit=2) if boolish(os.getenv("DEBUG_WRAPPERS")) else None}))
