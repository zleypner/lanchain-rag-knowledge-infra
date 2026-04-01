"""Document ingestion pipeline for processing and indexing documents."""

import logging
from typing import Any

from langchain_core.documents import Document as LangchainDocument

from app.core.exceptions import (
    DocumentNotFoundError,
    DocumentParsingError,
    EmbeddingException,
    VectorStoreException,
)
from app.models.document import Document, DocumentStatus
from app.services.chunking_service import get_chunking_service
from app.services.document_service import get_document_service
from app.services.embedding_service import get_embedding_service
from app.services.parser_service import get_parser_service
from app.services.vector_store_service import get_vector_store_service

logger = logging.getLogger(__name__)


class IngestionResult:
    """Result of a document ingestion operation."""

    def __init__(
        self,
        document_id: str,
        success: bool,
        chunk_count: int = 0,
        error: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.document_id = document_id
        self.success = success
        self.chunk_count = chunk_count
        self.error = error
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "document_id": self.document_id,
            "success": self.success,
            "chunk_count": self.chunk_count,
            "error": self.error,
            "details": self.details,
        }


class IngestionService:
    """Service for orchestrating the document ingestion pipeline."""

    def __init__(self) -> None:
        """Initialize the ingestion service with required dependencies."""
        self.document_service = get_document_service()
        self.parser_service = get_parser_service()
        self.chunking_service = get_chunking_service()
        self.embedding_service = get_embedding_service()
        self.vector_store_service = get_vector_store_service()

    async def ingest_document(self, document_id: str) -> IngestionResult:
        """
        Ingest a document through the full pipeline.

        Pipeline steps:
        1. Retrieve document metadata
        2. Parse text from document file
        3. Split text into chunks
        4. Generate embeddings for chunks
        5. Store in vector store
        6. Update document status

        Args:
            document_id: The ID of the document to ingest.

        Returns:
            IngestionResult with success status and details.
        """
        logger.info(f"Starting ingestion for document: {document_id}")

        try:
            # Step 1: Get document metadata
            document = await self.document_service.get_document(document_id)
            logger.debug(f"Retrieved document: {document.original_filename}")

            # Update status to processing
            await self.document_service.update_document_status(
                document_id, DocumentStatus.PROCESSING
            )

            # Step 2: Parse the document
            logger.info(f"Parsing document: {document.file_path}")
            text = self.parser_service.parse_document(
                document.file_path, document.file_type
            )

            if not text.strip():
                raise DocumentParsingError(
                    message="Document contains no extractable text",
                    details={"document_id": document_id},
                )

            logger.debug(f"Extracted {len(text)} characters from document")

            # Step 3: Chunk the text
            logger.info("Chunking document text")
            metadata = {
                "source": document.original_filename,
                "document_id": document_id,
                "file_type": document.file_type,
            }
            chunks = self.chunking_service.chunk_text(text, metadata)
            chunk_count = len(chunks)

            logger.info(f"Created {chunk_count} chunks from document")

            if chunk_count == 0:
                raise DocumentParsingError(
                    message="Document produced no chunks",
                    details={"document_id": document_id, "text_length": len(text)},
                )

            # Step 4: Generate embeddings
            logger.info(f"Generating embeddings for {chunk_count} chunks")
            texts = [chunk.page_content for chunk in chunks]
            embeddings = self.embedding_service.get_embeddings(texts)

            logger.debug(f"Generated {len(embeddings)} embeddings")

            # Step 5: Store in vector store
            logger.info("Storing chunks in vector store")
            chunk_ids = [f"{document_id}_{i}" for i in range(chunk_count)]
            self.vector_store_service.add_documents(chunks, embeddings, chunk_ids)

            # Step 6: Update document status
            await self.document_service.update_document_status(
                document_id, DocumentStatus.INDEXED, chunk_count=chunk_count
            )

            logger.info(
                f"Successfully ingested document {document_id} "
                f"with {chunk_count} chunks"
            )

            return IngestionResult(
                document_id=document_id,
                success=True,
                chunk_count=chunk_count,
                details={
                    "text_length": len(text),
                    "embedding_dimension": len(embeddings[0]) if embeddings else 0,
                },
            )

        except DocumentNotFoundError:
            logger.error(f"Document not found: {document_id}")
            return IngestionResult(
                document_id=document_id,
                success=False,
                error=f"Document not found: {document_id}",
            )

        except DocumentParsingError as e:
            logger.error(f"Parsing error for document {document_id}: {e}")
            await self._mark_failed(document_id)
            return IngestionResult(
                document_id=document_id,
                success=False,
                error=str(e),
                details=e.details if hasattr(e, "details") else {},
            )

        except EmbeddingException as e:
            logger.error(f"Embedding error for document {document_id}: {e}")
            await self._mark_failed(document_id)
            return IngestionResult(
                document_id=document_id,
                success=False,
                error=f"Failed to generate embeddings: {str(e)}",
            )

        except VectorStoreException as e:
            logger.error(f"Vector store error for document {document_id}: {e}")
            await self._mark_failed(document_id)
            return IngestionResult(
                document_id=document_id,
                success=False,
                error=f"Failed to store in vector store: {str(e)}",
            )

        except Exception as e:
            logger.exception(f"Unexpected error ingesting document {document_id}")
            await self._mark_failed(document_id)
            return IngestionResult(
                document_id=document_id,
                success=False,
                error=f"Unexpected error: {str(e)}",
            )

    async def _mark_failed(self, document_id: str) -> None:
        """Mark a document as failed."""
        try:
            await self.document_service.update_document_status(
                document_id, DocumentStatus.FAILED
            )
        except Exception as e:
            logger.error(f"Failed to mark document {document_id} as failed: {e}")

    async def ingest_multiple(
        self, document_ids: list[str]
    ) -> list[IngestionResult]:
        """
        Ingest multiple documents.

        Args:
            document_ids: List of document IDs to ingest.

        Returns:
            List of IngestionResult objects.
        """
        results = []
        for doc_id in document_ids:
            result = await self.ingest_document(doc_id)
            results.append(result)
        return results

    def get_ingestion_statistics(self) -> dict[str, Any]:
        """
        Get statistics about ingested documents.

        Returns:
            Dictionary with ingestion statistics.
        """
        vector_stats = self.vector_store_service.get_statistics()
        doc_count = self.document_service.get_document_count()

        return {
            "total_documents": doc_count,
            "indexed_chunks": vector_stats["vector_count"],
            "vector_store": vector_stats,
        }


# Singleton instance
_ingestion_service: IngestionService | None = None


def get_ingestion_service() -> IngestionService:
    """Get or create the ingestion service instance."""
    global _ingestion_service
    if _ingestion_service is None:
        _ingestion_service = IngestionService()
    return _ingestion_service


def reset_ingestion_service() -> None:
    """Reset the ingestion service singleton (useful for testing)."""
    global _ingestion_service
    _ingestion_service = None
