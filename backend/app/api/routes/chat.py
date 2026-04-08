"""Chat endpoints for RAG queries."""

import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatStreamRequest,
    SourceDocument,
)
from app.services.advanced_rag_chain import get_advanced_rag_chain
from app.services.conversation_service import get_conversation_service
from app.services.rag_chain import get_rag_chain

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """
    Send a message and get a RAG-powered response.

    The system will:
    1. Search the knowledge base for relevant documents
    2. Use the context to generate an accurate answer
    3. Return the answer with source attribution
    4. Automatically maintain conversation history if session_id is provided

    Args:
        request: Chat request with message and optional history.

    Returns:
        ChatResponse with answer and sources.
    """
    logger.info(f"Chat request: {request.message[:50]}...")

    try:
        rag_chain = get_rag_chain()
        conversation_service = get_conversation_service()

        # Get or build chat history
        chat_history = None

        if request.session_id:
            # Use conversation service for automatic history management
            chat_history = conversation_service.get_langchain_history(
                request.session_id
            )
        elif request.history:
            # Use provided history
            chat_history = [
                {"role": msg.role, "content": msg.content}
                for msg in request.history
            ]

        # Execute RAG query
        if chat_history:
            response = await rag_chain.query_with_history(
                question=request.message,
                history=chat_history if isinstance(chat_history, list) and chat_history and isinstance(chat_history[0], dict) else [],
                k=request.k,
            )
        else:
            response = await rag_chain.query(
                question=request.message,
                chat_history=chat_history,
                k=request.k,
            )

        # Convert sources to schema
        sources = []
        if request.include_sources:
            sources = [
                SourceDocument(
                    source=src.get("source", "Unknown"),
                    document_id=src.get("document_id"),
                    chunk_index=src.get("chunk_index"),
                    similarity_score=src.get("similarity_score"),
                )
                for src in response.sources
            ]

        # Store exchange in conversation history if session_id provided
        session_id = request.session_id
        if session_id:
            conversation_service.add_exchange(
                session_id=session_id,
                user_message=request.message,
                assistant_message=response.answer,
                sources=response.sources if request.include_sources else None,
            )
        else:
            # Generate a new session ID for tracking
            conversation = conversation_service.create_conversation()
            session_id = conversation.id
            conversation_service.add_exchange(
                session_id=session_id,
                user_message=request.message,
                assistant_message=response.answer,
                sources=response.sources if request.include_sources else None,
            )

        return ChatResponse(
            answer=response.answer,
            sources=sources,
            session_id=session_id,
            metadata=response.metadata,
        )

    except Exception as e:
        logger.exception(f"Chat request failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat request: {str(e)}",
        )


@router.post("/stream")
async def chat_stream(request: ChatStreamRequest) -> StreamingResponse:
    """
    Stream a RAG-powered response using Server-Sent Events (SSE).

    Events sent:
    - retrieval: Number of documents retrieved
    - token: Response token (streamed incrementally)
    - sources: Source documents (sent once after response)
    - done: Completion with metadata
    - error: Error information if something fails

    Args:
        request: Stream request with message and optional history.

    Returns:
        StreamingResponse with SSE events.
    """
    logger.info(f"Stream request: {request.message[:50]}...")

    async def event_generator() -> AsyncIterator[str]:
        """Generate SSE events."""
        try:
            rag_chain = get_rag_chain()
            conversation_service = get_conversation_service()

            # Get chat history from session or request
            chat_history = None
            if request.session_id:
                chat_history = conversation_service.get_langchain_history(
                    request.session_id
                )
            elif request.history:
                chat_history = [
                    {"role": msg.role, "content": msg.content}
                    for msg in request.history
                ]

            # Track full response for conversation storage
            full_response = ""
            sources_data = []

            # Stream the response
            async for event in rag_chain.stream(
                question=request.message,
                chat_history=chat_history,
                k=request.k,
            ):
                event_type = event.get("type", "unknown")

                if event_type == "token":
                    full_response += event.get("content", "")
                elif event_type == "sources":
                    sources_data = event.get("sources", [])

                event_data = json.dumps(event)
                yield f"event: {event_type}\ndata: {event_data}\n\n"

            # Store exchange in conversation history
            session_id = request.session_id
            if session_id and full_response:
                conversation_service.add_exchange(
                    session_id=session_id,
                    user_message=request.message,
                    assistant_message=full_response,
                    sources=sources_data,
                )

        except Exception as e:
            logger.exception(f"Stream error: {e}")
            error_event = json.dumps({
                "type": "error",
                "error": str(e),
            })
            yield f"event: error\ndata: {error_event}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/statistics")
async def get_chat_statistics() -> dict:
    """
    Get statistics about the RAG system and conversations.

    Returns:
        Dictionary with retrieval, LLM, and conversation statistics.
    """
    try:
        rag_chain = get_rag_chain()
        conversation_service = get_conversation_service()

        stats = rag_chain.get_statistics()
        stats["conversations"] = conversation_service.get_statistics()

        return stats
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get statistics: {str(e)}",
        )
