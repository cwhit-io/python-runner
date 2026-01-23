"""
WebSocket consumers for real-time features.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for user notifications.
    
    Usage:
        const ws = new WebSocket('ws://localhost:8000/ws/notifications/');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Notification:', data.message);
        };
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope["user"]
        
        if self.user.is_authenticated:
            # Join user-specific notification group
            self.group_name = f"notifications_{self.user.id}"
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            await self.accept()
        else:
            await self.close()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if self.user.is_authenticated:
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Receive message from WebSocket."""
        data = json.loads(text_data)
        message = data.get('message', '')
        
        # Echo message back to user
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': f'Echo: {message}'
        }))
    
    async def notification_message(self, event):
        """
        Send notification to WebSocket.
        Called when a message is sent to the group.
        """
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'message': event['message']
        }))


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for chat rooms.
    
    Usage:
        const ws = new WebSocket('ws://localhost:8000/ws/chat/room1/');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log(`${data.username}: ${data.message}`);
        };
        ws.send(JSON.stringify({message: 'Hello!'}));
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.room_name = self.scope['url_route']['kwargs']['room_name']
        self.room_group_name = f'chat_{self.room_name}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send welcome message
        await self.send(text_data=json.dumps({
            'type': 'system',
            'message': f'Welcome to room: {self.room_name}'
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Receive message from WebSocket."""
        data = json.loads(text_data)
        message = data.get('message', '')
        
        user = self.scope["user"]
        username = user.username if user.is_authenticated else 'Anonymous'
        
        # Send message to room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username
            }
        )
    
    async def chat_message(self, event):
        """
        Send chat message to WebSocket.
        Called when a message is sent to the room group.
        """
        await self.send(text_data=json.dumps({
            'type': 'chat',
            'message': event['message'],
            'username': event['username']
        }))
