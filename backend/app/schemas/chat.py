"""Chat schemas for request/response validation."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """Schema for a single chat message."""

    role: Literal["user", "assistant", "system"] = Field(
        description="Role of the message sender"
    )
    content: str = Field(description="Message content")
    timestamp: datetime | None = Field(
        default=None, description="Message timestamp"
    )


class MetadataFilter(BaseModel):
    """Schema for metadata filtering."""

    document_type: str | None = Field(
        default=None,
        description="Filter by document type (pdf, txt, docx, md)"
    )
    document_id: str | None = Field(
        default=None,
        description="Filter by specific document ID"
    )
    source: str | None = Field(
        default=None,
        description="Filter by source filename"
    )
    date_from: str | None = Field(
        default=None,
        description="Filter documents from this date (ISO format)"
    )
    date_to: str | None = Field(
        default=None,
        description="Filter documents up to this date (ISO format)"
    )


class ChatRequest(BaseModel):
    """Request schema for chat endpoint."""

    message: str = Field(
        min_length=1,
        max_length=10000,
        description="User's question or message"
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID for conversation continuity"
    )
    history: list[ChatMessage] | None = Field(
        default=None,
        description="Previous messages in the conversation"
    )
    k: int | None = Field(
        default=None,
        ge=1,
        le=20,
        description="Number of documents to retrieve"
    )
    include_sources: bool = Field(
        default=True,
        description="Whether to include source documents in response"
    )
    use_hybrid_search: bool = Field(
        default=False,
        description="Use hybrid search (keyword + semantic)"
    )
    use_reranking: bool = Field(
        default=False,
        description="Use cross-encoder reranking"
    )
    use_query_expansion: bool = Field(
        default=False,
        description="Use query expansion for better retrieval"
    )
    metadata_filter: MetadataFilter | None = Field(
        default=None,
        description="Filter documents by metadata"
    )


class SourceDocument(BaseModel):
    """Schema for a source document reference."""

    source: str = Field(description="Source filename or identifier")
    document_id: str | None = Field(
        default=None, description="Document ID in the system"
    )
    chunk_index: int | None = Field(
        default=None, description="Chunk index within the document"
    )
    similarity_score: float | None = Field(
        default=None, description="Similarity score (lower is better for L2)"
    )
    content_preview: str | None = Field(
        default=None, description="Preview of the source content"
    )


class ChatResponse(BaseModel):
    """Response schema for chat endpoint."""

    answer: str = Field(description="Generated answer from the RAG system")
    sources: list[SourceDocument] = Field(
        default_factory=list,
        description="Source documents used to generate the answer"
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID for conversation continuity"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the response"
    )


class StreamEvent(BaseModel):
    """Schema for SSE stream events."""

    event: Literal["retrieval", "token", "sources", "done", "error"] = Field(
        description="Type of stream event"
    )
    data: dict[str, Any] = Field(
        description="Event payload data"
    )


class ChatStreamRequest(BaseModel):
    """Request schema for streaming chat endpoint."""

    message: str = Field(
        min_length=1,
        max_length=10000,
        description="User's question or message"
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID for conversation continuity"
    )
    history: list[ChatMessage] | None = Field(
        default=None,
        description="Previous messages in the conversation"
    )
    k: int | None = Field(
        default=None,
        ge=1,
        le=20,
        description="Number of documents to retrieve"
    )
    use_hybrid_search: bool = Field(
        default=False,
        description="Use hybrid search (keyword + semantic)"
    )
    use_reranking: bool = Field(
        default=False,
        description="Use cross-encoder reranking"
    )
    use_query_expansion: bool = Field(
        default=False,
        description="Use query expansion for better retrieval"
    )
    metadata_filter: MetadataFilter | None = Field(
        default=None,
        description="Filter documents by metadata"
    )


