from ninja import Schema
from typing import Optional, List
from datetime import datetime


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


class TagSchema(Schema):
    id: int
    name: str
    color: str


class ScriptSchema(Schema):
    id: int
    name: str
    description: str
    code: str
    dependencies: str
    tags: List[TagSchema]
    last_status: str
    last_run: Optional[datetime]
    execution_count: int
    is_public: bool
    created_at: datetime
    updated_at: datetime


class ScriptCreateSchema(Schema):
    name: str
    description: Optional[str] = ""
    code: Optional[str] = "# Write your Python script here\nprint('Hello, World!')"
    dependencies: Optional[str] = ""
    tags: Optional[List[str]] = []


class ScriptUpdateSchema(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    code: Optional[str] = None
    dependencies: Optional[str] = None
    is_public: Optional[bool] = None
    tags: Optional[List[str]] = None


class ExecutionSchema(Schema):
    id: int
    script_id: int
    status: str
    trigger_type: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_seconds: Optional[float]
    exit_code: Optional[int]
    created_at: datetime


class ExecutionDetailSchema(ExecutionSchema):
    stdout: str
    stderr: str
    error_message: str


class ScheduleSchema(Schema):
    id: int
    script_id: int
    name: str
    cron_expression: str
    timezone: str
    is_active: bool
    last_run: Optional[datetime]
    next_run: Optional[datetime]


class ScheduleCreateSchema(Schema):
    name: str
    cron_expression: str
