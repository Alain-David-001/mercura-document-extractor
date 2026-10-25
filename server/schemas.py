"""Validated HTTP and Gemini contracts."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str | None = Field(default=None, max_length=200)
    project_name: str | None = Field(default=None, max_length=1000)

    @field_validator("project_id", "project_name")
    @classmethod
    def normalize(cls, value):
        return value.strip() or None if isinstance(value, str) else value


class DocumentEdit(Metadata):
    revision: int = Field(ge=0)


class CommentInput(BaseModel):
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Comment cannot be empty")
        return value.strip()


class Comment(BaseModel):
    id: str
    text: str
    created_at: str


class Job(BaseModel):
    status: Literal["queued", "processing", "completed", "failed"]
    phase: str
    attempts: int
    completed_chunks: int
    total_chunks: int
    error: str | None
    updated_at: str


class Document(BaseModel):
    id: str
    filename: str
    size_bytes: int
    page_count: int
    project_id: str | None
    project_name: str | None
    ai_project_id: str | None
    ai_project_name: str | None
    warning: str | None
    revision: int
    created_at: str
    updated_at: str
    job: Job


class DocumentDetail(Document):
    comments: list[Comment]


class WorkerAvailability(BaseModel):
    available: bool
    last_seen_at: str | None
