"""
WebSocket URL routing configuration.
"""

from django.urls import re_path
from app.consumers import NotificationConsumer, ChatConsumer, ExecutionMonitorConsumer

websocket_urlpatterns = [
    re_path(r"ws/notifications/$", NotificationConsumer.as_asgi()),
    re_path(r"ws/chat/(?P<room_name>\w+)/$", ChatConsumer.as_asgi()),
    re_path(
        r"ws/execution/(?P<execution_id>\d+)/$", ExecutionMonitorConsumer.as_asgi()
    ),
]
