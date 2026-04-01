"""Document management endpoints."""

import math

from fastapi import APIRouter, File, Query, UploadFile

from app.api.deps import DocumentServiceDep, IngestionServiceDep
from app.models.document import DocumentStatus
from app.schemas.document import (
    DocumentDeleteResponse,
    DocumentIngestResponse,
    DocumentListResponse,
    DocumentResponse,
    DocumentUploadResponse,
)

router = APIRouter()


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    service: DocumentServiceDep,
    file: UploadFile = File(..., description="Document file to upload"),
) -> DocumentUploadResponse:
    """
    Upload a document for processing.

    Accepts PDF, TXT, DOCX, and MD files up to the configured size limit.
    The document will be stored and queued for processing.
    """
    document = await service.upload_document(file=file)

    return DocumentUploadResponse(
        upload_id=document.id,
        status=document.status,
        message="Document uploaded successfully",
        document=DocumentResponse(
            id=document.id,
            filename=document.filename,
            original_filename=document.original_filename,
            file_type=document.file_type,
            file_size=document.file_size,
            status=document.status,
            chunk_count=document.chunk_count,
            created_at=document.created_at,
            updated_at=document.updated_at,
            metadata=document.metadata,
        ),
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    service: DocumentServiceDep,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(
        default=10, ge=1, le=100, description="Number of items per page"
    ),
    status: DocumentStatus | None = Query(
        default=None, description="Filter by document status"
    ),
) -> DocumentListResponse:
    """
    List all documents with pagination.

    Returns a paginated list of documents, optionally filtered by status.
    """
    documents, total = await service.list_documents(
        page=page,
        page_size=page_size,
        status=status,
    )

    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=doc.id,
                filename=doc.filename,
                original_filename=doc.original_filename,
                file_type=doc.file_type,
                file_size=doc.file_size,
                status=doc.status,
                chunk_count=doc.chunk_count,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
                metadata=doc.metadata,
            )
            for doc in documents
        ],
        total=total,
        page=page,
        page_size=page_size,
        pages=total_pages,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: str,
    service: DocumentServiceDep,
) -> DocumentResponse:
    """
    Get a specific document by ID.

    Returns the document details including status and metadata.
    """
    document = await service.get_document(document_id)

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        original_filename=document.original_filename,
        file_type=document.file_type,
        file_size=document.file_size,
        status=document.status,
        chunk_count=document.chunk_count,
        created_at=document.created_at,
        updated_at=document.updated_at,
        metadata=document.metadata,
    )


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    document_id: str,
    service: DocumentServiceDep,
) -> DocumentDeleteResponse:
    """
    Delete a document.

    Removes the document record and deletes the associated file from storage.
    """
    await service.delete_document(document_id)

    return DocumentDeleteResponse(
        success=True,
        message="Document deleted successfully",
        document_id=document_id,
    )


@router.post("/{document_id}/ingest", response_model=DocumentIngestResponse)
async def ingest_document(
    document_id: str,
    ingestion_service: IngestionServiceDep,
) -> DocumentIngestResponse:
    """
    Ingest a document into the knowledge base.

    Processes the document through the full pipeline:
    1. Parse text from the document file
    2. Split into chunks
    3. Generate embeddings
    4. Store in vector database

    The document must already be uploaded before calling this endpoint.
    """
    result = await ingestion_service.ingest_document(document_id)

    return DocumentIngestResponse(
        document_id=result.document_id,
        success=result.success,
        chunk_count=result.chunk_count,
        error=result.error,
        details=result.details,
    )
