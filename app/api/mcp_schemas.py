from ninja import Schema
from typing import Optional, List


class MCPResourceSchema(Schema):
    id: str
    name: str
    description: str
    manifest_url: str
    tool_type: str


class MCPDiscoverySchema(Schema):
    resources: List[MCPResourceSchema]


class MCPToolManifestSchema(Schema):
    script_id: int
    name: str
    description: str
    language: str
    tool_name: str
    tool_description: str
    parameters: dict
    is_destructive: bool = False


class MCPInvokeRequestSchema(Schema):
    input_text: Optional[str] = None
    timeout_seconds: Optional[int] = None


class MCPInvokeResponseSchema(Schema):
    id: int
    script_id: int
    status: str
    trigger_type: str
    started_at: Optional[str] = None
