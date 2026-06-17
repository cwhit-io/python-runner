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


class ItemCreateSchema(ItemSchema):
    pass


class ItemUpdateSchema(Schema):
    name: Optional[str] = None
    description: Optional[str] = None


class TagSchema(Schema):
    id: int
    name: str
    color: str


class CredentialTypeSchema(Schema):
    value: str
    label: str


class GlobalCredentialSchema(Schema):
    id: int
    name: str
    credential_type: str
    masked_value: str
    created_at: datetime
    updated_at: datetime


class GlobalCredentialCreateSchema(Schema):
    name: str
    credential_type: str
    api_key: Optional[str] = None
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_url: Optional[str] = None
    key: Optional[str] = None
    value: Optional[str] = None


class GlobalCredentialUpdateSchema(Schema):
    name: Optional[str] = None
    api_key: Optional[str] = None
    token: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    token_url: Optional[str] = None
    key: Optional[str] = None
    value: Optional[str] = None


class ScriptSchema(Schema):
    id: int
    name: str
    description: str
    code: str
    dependencies: str
    tags: List[TagSchema]
    credentials: List[GlobalCredentialSchema]
    expose_to_mcp: bool
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
    expose_to_mcp: Optional[bool] = False


class ScriptUpdateSchema(Schema):
    name: Optional[str] = None
    description: Optional[str] = None
    code: Optional[str] = None
    dependencies: Optional[str] = None
    is_public: Optional[bool] = None
    expose_to_mcp: Optional[bool] = None
    tags: Optional[List[str]] = None
    credentials: Optional[List[int]] = None


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


class ExecutionResultSchema(ExecutionDetailSchema):
    """Schema for execution results with parsed JSON output."""
    result: Optional[dict] = None


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


class SecretSchema(Schema):
    name: str


class SecretSetSchema(Schema):
    name: str
    value: str
