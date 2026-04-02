"""Conversation schemas for request/response validation."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import PaginatedResponse


class MessageSchema(BaseModel):
    """Schema for a conversation message."""

    id: str = Field(description="Message unique identifier")
    role: str = Field(description="Role: user, assistant, or system")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(description="Message timestamp")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Message metadata"
    )


class ConversationSchema(BaseModel):
    """Schema for a conversation."""

    id: str = Field(description="Conversation/session identifier")
    messages: list[MessageSchema] = Field(description="Conversation messages")
    created_at: datetime = Field(description="When conversation started")
    updated_at: datetime = Field(description="Last activity timestamp")
    message_count: int = Field(description="Total number of messages")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Conversation metadata"
    )


class ConversationListResponse(PaginatedResponse):
    """Response schema for listing conversations."""

    conversations: list[ConversationSchema] = Field(
        description="List of conversations"
    )


class ConversationHistoryResponse(BaseModel):
    """Response schema for conversation history."""

    session_id: str = Field(description="Session identifier")
    messages: list[MessageSchema] = Field(description="Conversation messages")
    total_messages: int = Field(description="Total message count")


class ConversationCreateRequest(BaseModel):
    """Request schema for creating a conversation."""

    session_id: str | None = Field(
        default=None, description="Optional custom session ID"
    )
    metadata: dict[str, Any] | None = Field(
        default=None, description="Optional metadata"
    )


class ConversationCreateResponse(BaseModel):
    """Response schema for conversation creation."""

    session_id: str = Field(description="Created session ID")
    message: str = Field(description="Status message")


class ConversationDeleteResponse(BaseModel):
    """Response schema for conversation deletion."""

    success: bool = Field(description="Whether deletion was successful")
    session_id: str = Field(description="Deleted session ID")
    message: str = Field(description="Status message")


class ConversationClearResponse(BaseModel):
    """Response schema for clearing conversation history."""

    success: bool = Field(description="Whether clear was successful")
    session_id: str = Field(description="Session ID")
    message: str = Field(description="Status message")
