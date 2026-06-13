"""
ASGI config for app project.

Mounts the Django app, WebSocket routing, and the MCP Streamable HTTP server.
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# ── Import routing after Django ASGI app is initialized ─────────────────
from app.routing import websocket_urlpatterns

# ── Build the MCP ASGI app (import triggers django.setup internally) ────
from app.mcp_server import create_mcp_asgi_app

mcp_asgi_app = create_mcp_asgi_app()

# ── Django + WebSocket router ───────────────────────────────────────────
_django_app = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)

# ── Top-level ASGI router ────────────────────────────────────────────────
# FastMCP exposes the streamable_http_app (a Starlette instance) which
# already handles its own route at /mcp. We call it directly for http
# requests whose path starts with /mcp.  Everything else goes to Django.
from starlette.types import Scope, Receive, Send


async def application(scope: Scope, receive: Receive, send: Send) -> None:
    """Route /mcp/* to FastMCP, everything else to Django + WebSockets."""
    path = scope.get("path", "")
    if scope["type"] == "http" and path.startswith("/mcp"):
        await mcp_asgi_app(scope, receive, send)
    else:
        await _django_app(scope, receive, send)

