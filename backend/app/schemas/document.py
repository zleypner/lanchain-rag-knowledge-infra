"""Document schemas for request/response validation."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.document import DocumentStatus
from app.schemas.common import PaginatedResponse


class DocumentCreate(BaseModel):
    """Schema for document creation metadata."""

    metadata: dict[str, Any] | None = Field(
        default=None, description="Optional metadata for the document"
    )


class DocumentResponse(BaseModel):
    """Response schema for a single document."""

    id: str = Field(description="Unique document identifier")
    filename: str = Field(description="Stored filename")
    original_filename: str = Field(description="Original uploaded filename")
    file_type: str = Field(description="File extension/type")
    file_size: int = Field(description="File size in bytes")
    status: DocumentStatus = Field(description="Document processing status")
    chunk_count: int = Field(description="Number of text chunks created")
    created_at: datetime = Field(description="Document creation timestamp")
    updated_at: datetime = Field(description="Last update timestamp")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Document metadata"
    )

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class DocumentUploadResponse(BaseModel):
    """Response schema for document upload."""

    upload_id: str = Field(description="Unique identifier for the uploaded document")
    status: DocumentStatus = Field(description="Initial document status")
    message: str = Field(description="Upload status message")
    document: DocumentResponse = Field(description="Uploaded document details")


class DocumentListResponse(PaginatedResponse):
    """Response schema for listing documents."""

    documents: list[DocumentResponse] = Field(description="List of documents")


class DocumentDeleteResponse(BaseModel):
    """Response schema for document deletion."""

    success: bool = Field(description="Whether deletion was successful")
    message: str = Field(description="Deletion status message")
    document_id: str = Field(description="ID of deleted document")


class DocumentIngestResponse(BaseModel):
    """Response schema for document ingestion."""

    document_id: str = Field(description="ID of the ingested document")
    success: bool = Field(description="Whether ingestion was successful")
    chunk_count: int = Field(default=0, description="Number of chunks created")
    error: str | None = Field(default=None, description="Error message if failed")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Additional ingestion details"
    )
