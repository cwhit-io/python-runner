from ninja import Schema
from typing import Optional


class MessageSchema(Schema):
    message: str
    timestamp: str


class ItemSchema(Schema):
    id: int
    name: str
    description: Optional[str] = None


class ItemCreateSchema(Schema):
    name: str
    description: Optional[str] = None


class ItemUpdateSchema(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
