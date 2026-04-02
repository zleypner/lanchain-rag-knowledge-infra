"""Conversation management endpoints."""

import logging
import math

from fastapi import APIRouter, HTTPException, Query

from app.core.exceptions import ConversationNotFoundError
from app.schemas.conversation import (
    ConversationClearResponse,
    ConversationCreateRequest,
    ConversationCreateResponse,
    ConversationDeleteResponse,
    ConversationHistoryResponse,
    ConversationListResponse,
    ConversationSchema,
    MessageSchema,
)
from app.services.conversation_service import get_conversation_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=ConversationCreateResponse)
async def create_conversation(
    request: ConversationCreateRequest | None = None,
) -> ConversationCreateResponse:
    """
    Create a new conversation session.

    Optionally provide a custom session ID and metadata.
    """
    service = get_conversation_service()
    request = request or ConversationCreateRequest()

    conversation = service.create_conversation(
        session_id=request.session_id,
        metadata=request.metadata,
    )

    return ConversationCreateResponse(
        session_id=conversation.id,
        message="Conversation created successfully",
    )


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(
        default=10, ge=1, le=100, description="Items per page"
    ),
) -> ConversationListResponse:
    """
    List all conversations with pagination.
    """
    service = get_conversation_service()
    conversations, total = service.list_conversations(page=page, page_size=page_size)

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return ConversationListResponse(
        conversations=[
            ConversationSchema(
                id=conv.id,
                messages=[
                    MessageSchema(
                        id=msg.id,
                        role=msg.role.value,
                        content=msg.content,
                        timestamp=msg.timestamp,
                        metadata=msg.metadata,
                    )
                    for msg in conv.messages[-5:]  # Last 5 messages preview
                ],
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=len(conv.messages),
                metadata=conv.metadata,
            )
            for conv in conversations
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=total_pages,
    )


@router.get("/{session_id}", response_model=ConversationSchema)
async def get_conversation(session_id: str) -> ConversationSchema:
    """
    Get a specific conversation by session ID.
    """
    service = get_conversation_service()

    try:
        conversation = service.get_conversation(session_id)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {session_id}")

    return ConversationSchema(
        id=conversation.id,
        messages=[
            MessageSchema(
                id=msg.id,
                role=msg.role.value,
                content=msg.content,
                timestamp=msg.timestamp,
                metadata=msg.metadata,
            )
            for msg in conversation.messages
        ],
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        message_count=len(conversation.messages),
        metadata=conversation.metadata,
    )


@router.get("/{session_id}/history", response_model=ConversationHistoryResponse)
async def get_conversation_history(
    session_id: str,
    limit: int | None = Query(
        default=None, ge=1, le=100, description="Max messages to return"
    ),
) -> ConversationHistoryResponse:
    """
    Get message history for a conversation.
    """
    service = get_conversation_service()

    try:
        messages = service.get_history(session_id, limit=limit)
        conversation = service.get_conversation(session_id)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {session_id}")

    return ConversationHistoryResponse(
        session_id=session_id,
        messages=[
            MessageSchema(
                id=msg.id,
                role=msg.role.value,
                content=msg.content,
                timestamp=msg.timestamp,
                metadata=msg.metadata,
            )
            for msg in messages
        ],
        total_messages=len(conversation.messages),
    )


@router.delete("/{session_id}", response_model=ConversationDeleteResponse)
async def delete_conversation(session_id: str) -> ConversationDeleteResponse:
    """
    Delete a conversation and all its messages.
    """
    service = get_conversation_service()
    deleted = service.delete_conversation(session_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {session_id}")

    return ConversationDeleteResponse(
        success=True,
        session_id=session_id,
        message="Conversation deleted successfully",
    )


@router.post("/{session_id}/clear", response_model=ConversationClearResponse)
async def clear_conversation_history(session_id: str) -> ConversationClearResponse:
    """
    Clear all messages from a conversation while keeping the session.
    """
    service = get_conversation_service()

    try:
        service.clear_history(session_id)
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail=f"Conversation not found: {session_id}")

    return ConversationClearResponse(
        success=True,
        session_id=session_id,
        message="Conversation history cleared",
    )


@router.get("/statistics/summary")
async def get_conversation_statistics() -> dict:
    """
    Get statistics about conversations.
    """
    service = get_conversation_service()
    return service.get_statistics()
