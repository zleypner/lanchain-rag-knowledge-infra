"""Repository for document database operations."""

import logging
from typing import Any
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DocumentChunkModel, DocumentModel
from app.models.document import Document as DocumentDataclass
from app.models.document import DocumentStatus

logger = logging.getLogger(__name__)


class DocumentRepository:
    """Repository for document CRUD operations."""

    async def create(
        self,
        session: AsyncSession,
        filename: str,
        original_filename: str,
        file_path: str,
        file_type: str,
        file_size: int,
        metadata: dict[str, Any] | None = None,
    ) -> DocumentModel:
        """
        Create a new document record.

        Args:
            session: Database session.
            filename: Storage filename.
            original_filename: Original uploaded filename.
            file_path: Path to stored file.
            file_type: File extension/type.
            file_size: File size in bytes.
            metadata: Optional metadata dictionary.

        Returns:
            Created DocumentModel instance.
        """
        document = DocumentModel(
            id=str(uuid4()),
            filename=filename,
            original_filename=original_filename,
            file_path=file_path,
            file_type=file_type,
            file_size=file_size,
            status=DocumentStatus.PENDING,
            chunk_count=0,
            metadata_=metadata or {},
        )

        session.add(document)
        await session.flush()

        logger.info(f"Created document record: {document.id}")
        return document

    async def get_by_id(
        self,
        session: AsyncSession,
        document_id: str,
    ) -> DocumentModel | None:
        """
        Get a document by its ID.

        Args:
            session: Database session.
            document_id: The document ID.

        Returns:
            DocumentModel if found, None otherwise.
        """
        result = await session.execute(
            select(DocumentModel).where(DocumentModel.id == document_id)
        )
        return result.scalar_one_or_none()

    async def list_documents(
        self,
        session: AsyncSession,
        skip: int = 0,
        limit: int = 10,
        status: DocumentStatus | None = None,
    ) -> tuple[list[DocumentModel], int]:
        """
        List documents with pagination.

        Args:
            session: Database session.
            skip: Number of records to skip.
            limit: Maximum number of records to return.
            status: Optional status filter.

        Returns:
            Tuple of (documents list, total count).
        """
        # Build base query
        query = select(DocumentModel)
        count_query = select(func.count(DocumentModel.id))

        # Apply status filter if provided
        if status is not None:
            query = query.where(DocumentModel.status == status)
            count_query = count_query.where(DocumentModel.status == status)

        # Get total count
        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        # Get paginated results
        query = (
            query.order_by(DocumentModel.created_at.desc()).offset(skip).limit(limit)
        )
        result = await session.execute(query)
        documents = list(result.scalars().all())

        return documents, total

    async def update_status(
        self,
        session: AsyncSession,
        document_id: str,
        status: DocumentStatus,
        chunk_count: int | None = None,
    ) -> DocumentModel | None:
        """
        Update a document's status.

        Args:
            session: Database session.
            document_id: The document ID.
            status: New status.
            chunk_count: Optional chunk count to update.

        Returns:
            Updated DocumentModel if found, None otherwise.
        """
        values: dict[str, Any] = {"status": status}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count

        await session.execute(
            update(DocumentModel)
            .where(DocumentModel.id == document_id)
            .values(**values)
        )

        # Fetch and return updated document
        return await self.get_by_id(session, document_id)

    async def update_metadata(
        self,
        session: AsyncSession,
        document_id: str,
        metadata: dict[str, Any],
    ) -> DocumentModel | None:
        """
        Update a document's metadata.

        Args:
            session: Database session.
            document_id: The document ID.
            metadata: New metadata dictionary.

        Returns:
            Updated DocumentModel if found, None otherwise.
        """
        await session.execute(
            update(DocumentModel)
            .where(DocumentModel.id == document_id)
            .values(metadata_=metadata)
        )

        return await self.get_by_id(session, document_id)

    async def delete(
        self,
        session: AsyncSession,
        document_id: str,
    ) -> bool:
        """
        Delete a document and its chunks.

        Args:
            session: Database session.
            document_id: The document ID.

        Returns:
            True if document was deleted, False if not found.
        """
        # Delete chunks first (cascade should handle this, but being explicit)
        await session.execute(
            delete(DocumentChunkModel).where(
                DocumentChunkModel.document_id == document_id
            )
        )

        # Delete document
        result = await session.execute(
            delete(DocumentModel).where(DocumentModel.id == document_id)
        )

        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Deleted document: {document_id}")

        return deleted

    async def get_statistics(
        self,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """
        Get document statistics.

        Args:
            session: Database session.

        Returns:
            Dictionary with document statistics.
        """
        # Total documents
        total_result = await session.execute(select(func.count(DocumentModel.id)))
        total = total_result.scalar() or 0

        # Documents by status
        status_counts = {}
        for status in DocumentStatus:
            count_result = await session.execute(
                select(func.count(DocumentModel.id)).where(
                    DocumentModel.status == status
                )
            )
            status_counts[status.value] = count_result.scalar() or 0

        # Total chunks
        chunks_result = await session.execute(
            select(func.count(DocumentChunkModel.id))
        )
        total_chunks = chunks_result.scalar() or 0

        # Total file size
        size_result = await session.execute(
            select(func.sum(DocumentModel.file_size))
        )
        total_size = size_result.scalar() or 0

        return {
            "total_documents": total,
            "documents_by_status": status_counts,
            "total_chunks": total_chunks,
            "total_file_size_bytes": total_size,
        }

    def model_to_dataclass(self, model: DocumentModel) -> DocumentDataclass:
        """
        Convert a DocumentModel to a Document dataclass.

        Args:
            model: The DocumentModel instance.

        Returns:
            Document dataclass instance.
        """
        return DocumentDataclass(
            id=model.id,
            filename=model.filename,
            original_filename=model.original_filename,
            file_path=model.file_path,
            file_type=model.file_type,
            file_size=model.file_size,
            status=model.status,
            chunk_count=model.chunk_count,
            created_at=model.created_at,
            updated_at=model.updated_at,
            metadata=model.metadata_,
        )


# Singleton instance
_document_repository: DocumentRepository | None = None


def get_document_repository() -> DocumentRepository:
    """Get or create the document repository instance."""
    global _document_repository
    if _document_repository is None:
        _document_repository = DocumentRepository()
    return _document_repository
