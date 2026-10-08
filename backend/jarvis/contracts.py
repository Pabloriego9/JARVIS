from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Status(StrEnum):
    pending = "pending"
    planning = "planning"
    awaiting_approval = "awaiting_approval"
    running = "running"
    paused = "paused"
    cancelled = "cancelled"
    completed = "completed"
    failed = "failed"
    uncertain = "uncertain"


class ToolCall(StrictModel):
    tool_name: str = Field(pattern=r"^[a-z]+\.[a-z_]+$")
    arguments: dict[str, Any] = Field(default_factory=dict)
    expected_resource_version: str | None = None
    approval_id: str | None = None
    call_id: str | None = None


class ToolRequest(ToolCall):
    task_id: str
    request_id: str
    device_id: str
    schema_version: int = 1
    deadline: datetime
    idempotency_key: str


class ToolResult(StrictModel):
    status: str = "completed"
    data: Any = None
    error_code: str | None = None
    user_message: str = ""
    technical_details_redacted: dict = Field(default_factory=dict)
    evidence: list[dict] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)
    retry_safe: bool = False
    resource_version: str | None = None


class ToolError(Exception):
    def __init__(self, code: str, message: str, status="failed", details=None):
        self.result = ToolResult(
            status=status, error_code=code, user_message=message, technical_details_redacted=details or {}
        )
        super().__init__(message)


class TaskCreate(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    device_id: str = "local"
    actions: list[ToolCall] = Field(min_length=1, max_length=12)
    timeout_seconds: int = Field(default=300, ge=5, le=3600)
    idempotency_key: str = Field(min_length=8, max_length=150)


class ChatCreate(StrictModel):
    message: str = Field(min_length=1, max_length=16000)
    conversation_id: str | None = None
    device_id: str = "local"
    idempotency_key: str = Field(min_length=8, max_length=150)


class MemoryWrite(StrictModel):
    content: str = Field(min_length=1, max_length=8000)
    kind: str = Field(default="preference", pattern="^(preference|fact|project|procedure)$")
    expected_revision: int | None = None


class GrantCreate(StrictModel):
    resource: str
    operations: list[str] = Field(min_length=1)
    device_id: str = "local"
    kind: str = Field(default="folder", pattern="^(folder|site|app)$")
    mode: str = Field(default="assisted", pattern="^(consult|assisted|autonomous)$")


class ReminderCreate(StrictModel):
    title: str = Field(min_length=1, max_length=500)
    due_at: datetime
    timezone: str = "America/Argentina/Buenos_Aires"
    interval_seconds: int | None = Field(default=None, ge=60)
