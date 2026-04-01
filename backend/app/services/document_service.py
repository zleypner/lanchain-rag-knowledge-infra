"""Document service for managing document operations."""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import UploadFile

from app.core.exceptions import DocumentNotFoundError
from app.models.document import Document, DocumentStatus
from app.utils.storage import delete_file, get_file_path, save_upload_file

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for managing document operations."""

    def __init__(self) -> None:
        """Initialize the document service with in-memory storage."""
        # In-memory storage (will be replaced with database later)
        self._documents: dict[str, Document] = {}

    async def upload_document(
        self,
        file: UploadFile,
        metadata: dict[str, Any] | None = None,
    ) -> Document:
        """
        Upload and save a document.

        Args:
            file: The uploaded file from FastAPI.
            metadata: Optional metadata to attach to the document.

        Returns:
            The created Document instance.

        Raises:
            InvalidFileTypeError: If the file type is not allowed.
            FileSizeLimitError: If the file size exceeds the limit.
            DocumentUploadError: If there's an error saving the file.
        """
        # Save the file to storage
        stored_filename, file_ext, file_size = await save_upload_file(file)

        # Create document record
        document = Document(
            filename=stored_filename,
            original_filename=file.filename or "unknown",
            file_path=str(get_file_path(stored_filename)),
            file_type=file_ext,
            file_size=file_size,
            status=DocumentStatus.PENDING,
            metadata=metadata or {},
        )

        # Store in memory
        self._documents[document.id] = document

        logger.info(f"Document uploaded: {document.id} ({document.original_filename})")
        return document

    async def get_document(self, document_id: str) -> Document:
        """
        Retrieve a document by ID.

        Args:
            document_id: The unique document identifier.

        Returns:
            The Document instance.

        Raises:
            DocumentNotFoundError: If the document is not found.
        """
        document = self._documents.get(document_id)

        if document is None:
            raise DocumentNotFoundError(document_id=document_id)

        return document

    async def list_documents(
        self,
        page: int = 1,
        page_size: int = 10,
        status: DocumentStatus | None = None,
    ) -> tuple[list[Document], int]:
        """
        List all documents with pagination.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.
            status: Optional filter by document status.

        Returns:
            Tuple of (list of documents, total count).
        """
        # Filter documents
        documents = list(self._documents.values())

        if status is not None:
            documents = [doc for doc in documents if doc.status == status]

        # Sort by created_at descending (newest first)
        documents.sort(key=lambda x: x.created_at, reverse=True)

        # Get total count before pagination
        total = len(documents)

        # Apply pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_documents = documents[start_idx:end_idx]

        return paginated_documents, total

    async def delete_document(self, document_id: str) -> Document:
        """
        Delete a document and its file.

        Args:
            document_id: The unique document identifier.

        Returns:
            The deleted Document instance.

        Raises:
            DocumentNotFoundError: If the document is not found.
        """
        # Get the document first
        document = await self.get_document(document_id)

        # Delete the file from storage
        await delete_file(document.filename)

        # Remove from memory storage
        del self._documents[document_id]

        logger.info(f"Document deleted: {document_id}")
        return document

    async def update_document_status(
        self,
        document_id: str,
        status: DocumentStatus,
        chunk_count: int | None = None,
    ) -> Document:
        """
        Update a document's status.

        Args:
            document_id: The unique document identifier.
            status: New status for the document.
            chunk_count: Optional chunk count to update.

        Returns:
            The updated Document instance.

        Raises:
            DocumentNotFoundError: If the document is not found.
        """
        document = await self.get_document(document_id)

        document.update_status(status)

        if chunk_count is not None:
            document.chunk_count = chunk_count

        logger.info(f"Document {document_id} status updated to: {status.value}")
        return document

    def get_document_count(self) -> int:
        """Get the total number of documents."""
        return len(self._documents)


# Global service instance (singleton pattern for in-memory storage)
_document_service: DocumentService | None = None


def get_document_service() -> DocumentService:
    """Get or create the document service instance."""
    global _document_service
    if _document_service is None:
        _document_service = DocumentService()
    return _document_service
