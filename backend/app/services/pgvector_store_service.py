"""Vector store service using PostgreSQL with pgvector extension."""

import logging
from typing import Any
from uuid import uuid4

from langchain_core.documents import Document as LangchainDocument
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import VectorStoreException
from app.db.models import DocumentChunkModel

logger = logging.getLogger(__name__)


class PGVectorStoreService:
    """Service for managing document vectors using PostgreSQL pgvector."""

    def __init__(
        self,
        embedding_dimension: int = 1536,  # Default for text-embedding-3-small
    ) -> None:
        """
        Initialize the PGVector store service.

        Args:
            embedding_dimension: Dimension of the embedding vectors.
        """
        self.embedding_dimension = embedding_dimension

    async def add_documents(
        self,
        session: AsyncSession,
        documents: list[LangchainDocument],
        embeddings: list[list[float]],
        document_id: str,
        doc_ids: list[str] | None = None,
    ) -> list[str]:
        """
        Add documents and their embeddings to the vector store.

        Args:
            session: Database session.
            documents: List of LangChain Document objects.
            embeddings: List of embedding vectors corresponding to documents.
            document_id: The parent document ID these chunks belong to.
            doc_ids: Optional list of chunk IDs. If not provided, UUIDs are generated.

        Returns:
            List of chunk IDs for the added documents.

        Raises:
            VectorStoreException: If adding documents fails.
        """
        if len(documents) != len(embeddings):
            raise VectorStoreException(
                message="Number of documents and embeddings must match",
                details={
                    "num_documents": len(documents),
                    "num_embeddings": len(embeddings),
                },
            )

        if not documents:
            return []

        # Generate chunk IDs if not provided
        if doc_ids is None:
            doc_ids = [str(uuid4()) for _ in documents]

        if len(doc_ids) != len(documents):
            raise VectorStoreException(
                message="Number of chunk IDs must match number of documents",
                details={
                    "num_documents": len(documents),
                    "num_doc_ids": len(doc_ids),
                },
            )

        try:
            chunk_ids = []

            for i, (chunk_id, doc, embedding) in enumerate(
                zip(doc_ids, documents, embeddings)
            ):
                # Verify embedding dimensions
                if len(embedding) != self.embedding_dimension:
                    raise VectorStoreException(
                        message="Embedding dimension mismatch",
                        details={
                            "expected": self.embedding_dimension,
                            "got": len(embedding),
                        },
                    )

                # Create chunk model
                chunk = DocumentChunkModel(
                    id=chunk_id,
                    document_id=document_id,
                    chunk_index=i,
                    content=doc.page_content,
                    embedding=embedding,
                    metadata_={
                        **doc.metadata,
                        "doc_id": chunk_id,
                    },
                )

                session.add(chunk)
                chunk_ids.append(chunk_id)

            await session.flush()

            logger.info(
                f"Added {len(documents)} document chunks to pgvector store "
                f"for document {document_id}"
            )

            return chunk_ids

        except VectorStoreException:
            raise
        except Exception as e:
            logger.exception(f"Failed to add documents to pgvector: {e}")
            raise VectorStoreException(
                message=f"Failed to add documents to vector store: {str(e)}",
                details={"num_documents": len(documents)},
            ) from e

    async def similarity_search(
        self,
        session: AsyncSession,
        query_embedding: list[float],
        k: int | None = None,
        document_ids: list[str] | None = None,
        score_threshold: float | None = None,
    ) -> list[LangchainDocument]:
        """
        Search for similar documents using a query embedding.

        Args:
            session: Database session.
            query_embedding: The embedding vector for the query.
            k: Number of results to return. Defaults to settings.retrieval_k.
            document_ids: Optional list of document IDs to filter by.
            score_threshold: Optional minimum similarity score threshold.

        Returns:
            List of Document objects most similar to the query.

        Raises:
            VectorStoreException: If search fails.
        """
        k = k or settings.retrieval_k

        try:
            # Build the query using pgvector's cosine distance
            # Lower distance = more similar (cosine distance = 1 - cosine similarity)
            embedding_str = f"[{','.join(map(str, query_embedding))}]"

            query = (
                select(
                    DocumentChunkModel,
                    (
                        DocumentChunkModel.embedding.cosine_distance(
                            text(f"'{embedding_str}'::vector")
                        )
                    ).label("distance"),
                )
                .order_by("distance")
                .limit(k)
            )

            # Filter by document IDs if provided
            if document_ids:
                query = query.where(DocumentChunkModel.document_id.in_(document_ids))

            result = await session.execute(query)
            rows = result.all()

            # Convert to LangChain documents
            documents: list[LangchainDocument] = []
            for chunk, distance in rows:
                # Convert cosine distance to similarity score (1 - distance)
                similarity_score = 1 - distance

                # Apply score threshold if provided
                if score_threshold is not None and similarity_score < score_threshold:
                    continue

                doc = LangchainDocument(
                    page_content=chunk.content,
                    metadata={
                        **chunk.metadata_,
                        "doc_id": chunk.id,
                        "document_id": chunk.document_id,
                        "chunk_index": chunk.chunk_index,
                        "similarity_score": similarity_score,
                    },
                )
                documents.append(doc)

            logger.debug(f"Found {len(documents)} similar documents")
            return documents

        except Exception as e:
            logger.exception(f"Failed to perform similarity search: {e}")
            raise VectorStoreException(
                message=f"Failed to perform similarity search: {str(e)}",
                details={"k": k},
            ) from e

    async def similarity_search_with_scores(
        self,
        session: AsyncSession,
        query_embedding: list[float],
        k: int | None = None,
        document_ids: list[str] | None = None,
    ) -> list[tuple[LangchainDocument, float]]:
        """
        Search for similar documents and return with similarity scores.

        Args:
            session: Database session.
            query_embedding: The embedding vector for the query.
            k: Number of results to return.
            document_ids: Optional list of document IDs to filter by.

        Returns:
            List of (Document, score) tuples.
        """
        documents = await self.similarity_search(
            session, query_embedding, k, document_ids
        )
        return [
            (doc, doc.metadata.get("similarity_score", 0.0)) for doc in documents
        ]

    async def delete_documents(
        self,
        session: AsyncSession,
        doc_ids: list[str],
    ) -> int:
        """
        Delete document chunks from the vector store.

        Args:
            session: Database session.
            doc_ids: List of chunk IDs to delete.

        Returns:
            Number of chunks actually deleted.

        Raises:
            VectorStoreException: If deletion fails.
        """
        try:
            result = await session.execute(
                delete(DocumentChunkModel).where(DocumentChunkModel.id.in_(doc_ids))
            )
            deleted_count = result.rowcount

            logger.info(f"Deleted {deleted_count} document chunks from pgvector store")
            return deleted_count

        except Exception as e:
            logger.exception(f"Failed to delete documents: {e}")
            raise VectorStoreException(
                message=f"Failed to delete documents: {str(e)}",
                details={"doc_ids": doc_ids},
            ) from e

    async def delete_by_document_id(
        self,
        session: AsyncSession,
        document_id: str,
    ) -> int:
        """
        Delete all chunks for a specific document.

        Args:
            session: Database session.
            document_id: The parent document ID.

        Returns:
            Number of chunks deleted.
        """
        try:
            result = await session.execute(
                delete(DocumentChunkModel).where(
                    DocumentChunkModel.document_id == document_id
                )
            )
            deleted_count = result.rowcount

            logger.info(
                f"Deleted {deleted_count} chunks for document {document_id}"
            )
            return deleted_count

        except Exception as e:
            logger.exception(f"Failed to delete document chunks: {e}")
            raise VectorStoreException(
                message=f"Failed to delete document chunks: {str(e)}",
                details={"document_id": document_id},
            ) from e

    async def get_chunk(
        self,
        session: AsyncSession,
        chunk_id: str,
    ) -> LangchainDocument | None:
        """
        Get a document chunk by its ID.

        Args:
            session: Database session.
            chunk_id: The chunk ID.

        Returns:
            The Document if found, None otherwise.
        """
        result = await session.execute(
            select(DocumentChunkModel).where(DocumentChunkModel.id == chunk_id)
        )
        chunk = result.scalar_one_or_none()

        if chunk is None:
            return None

        return LangchainDocument(
            page_content=chunk.content,
            metadata={
                **chunk.metadata_,
                "doc_id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
            },
        )

    async def get_chunks_by_document(
        self,
        session: AsyncSession,
        document_id: str,
    ) -> list[LangchainDocument]:
        """
        Get all chunks for a specific document.

        Args:
            session: Database session.
            document_id: The parent document ID.

        Returns:
            List of Document objects for all chunks.
        """
        result = await session.execute(
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.chunk_index)
        )
        chunks = result.scalars().all()

        return [
            LangchainDocument(
                page_content=chunk.content,
                metadata={
                    **chunk.metadata_,
                    "doc_id": chunk.id,
                    "document_id": chunk.document_id,
                    "chunk_index": chunk.chunk_index,
                },
            )
            for chunk in chunks
        ]

    async def get_document_count(self, session: AsyncSession) -> int:
        """
        Get the number of unique documents in the vector store.

        Args:
            session: Database session.

        Returns:
            Number of unique documents.
        """
        result = await session.execute(
            select(func.count(func.distinct(DocumentChunkModel.document_id)))
        )
        return result.scalar() or 0

    async def get_chunk_count(self, session: AsyncSession) -> int:
        """
        Get the total number of chunks in the vector store.

        Args:
            session: Database session.

        Returns:
            Total number of chunks.
        """
        result = await session.execute(select(func.count(DocumentChunkModel.id)))
        return result.scalar() or 0

    async def get_statistics(self, session: AsyncSession) -> dict[str, Any]:
        """
        Get statistics about the vector store.

        Args:
            session: Database session.

        Returns:
            Dictionary with store statistics.
        """
        document_count = await self.get_document_count(session)
        chunk_count = await self.get_chunk_count(session)

        return {
            "document_count": document_count,
            "chunk_count": chunk_count,
            "embedding_dimension": self.embedding_dimension,
            "store_type": "pgvector",
        }


# Singleton instance for dependency injection
_pgvector_store_service: PGVectorStoreService | None = None


def get_pgvector_store_service() -> PGVectorStoreService:
    """Get or create the PGVector store service instance."""
    global _pgvector_store_service
    if _pgvector_store_service is None:
        _pgvector_store_service = PGVectorStoreService(
            embedding_dimension=settings.embedding_dimensions
        )
    return _pgvector_store_service


def reset_pgvector_store_service() -> None:
    """Reset the PGVector store service singleton (useful for testing)."""
    global _pgvector_store_service
    _pgvector_store_service = None
