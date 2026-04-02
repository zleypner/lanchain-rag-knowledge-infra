"""Retrieval service for fetching relevant context from the vector store."""

import logging
from typing import Any

from langchain_core.documents import Document

from app.core.config import settings
from app.core.exceptions import RetrievalException
from app.services.embedding_service import get_embedding_service
from app.services.vector_store_service import get_vector_store_service

logger = logging.getLogger(__name__)


class RetrievalService:
    """Service for retrieving relevant documents based on queries."""

    def __init__(
        self,
        k: int | None = None,
        score_threshold: float | None = None,
    ) -> None:
        """
        Initialize the retrieval service.

        Args:
            k: Number of documents to retrieve. Defaults to settings.retrieval_k.
            score_threshold: Minimum similarity score threshold (optional).
                           Documents below this score are filtered out.
        """
        self.k = k or settings.retrieval_k
        self.score_threshold = score_threshold

        self.embedding_service = get_embedding_service()
        self.vector_store = get_vector_store_service()

        logger.info(f"Initialized RetrievalService with k={self.k}")

    async def retrieve(
        self,
        query: str,
        k: int | None = None,
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[Document]:
        """
        Retrieve relevant documents for a query.

        Args:
            query: The search query.
            k: Number of documents to retrieve. Overrides default if provided.
            filter_metadata: Optional metadata filters (not yet implemented).

        Returns:
            List of relevant Document objects with similarity scores.

        Raises:
            RetrievalException: If retrieval fails.
        """
        if not query or not query.strip():
            raise RetrievalException(
                message="Query cannot be empty",
                details={"query": query},
            )

        k = k or self.k

        try:
            # Generate query embedding
            logger.debug(f"Generating embedding for query: {query[:50]}...")
            query_embedding = await self.embedding_service.aembed_query(query)

            # Search vector store
            logger.debug(f"Searching vector store for top {k} documents")
            documents = self.vector_store.similarity_search(query_embedding, k=k)

            # Apply score threshold if set
            if self.score_threshold is not None:
                documents = [
                    doc
                    for doc in documents
                    if doc.metadata.get("similarity_score", 0) <= self.score_threshold
                ]

            # Apply metadata filters if provided
            if filter_metadata:
                documents = self._filter_by_metadata(documents, filter_metadata)

            logger.info(f"Retrieved {len(documents)} documents for query")
            return documents

        except Exception as e:
            logger.exception(f"Retrieval failed: {e}")
            raise RetrievalException(
                message=f"Failed to retrieve documents: {str(e)}",
                details={"query": query, "k": k},
            ) from e

    def _filter_by_metadata(
        self,
        documents: list[Document],
        filters: dict[str, Any],
    ) -> list[Document]:
        """
        Filter documents by metadata.

        Args:
            documents: List of documents to filter.
            filters: Dictionary of metadata key-value pairs to match.

        Returns:
            Filtered list of documents.
        """
        filtered = []
        for doc in documents:
            match = True
            for key, value in filters.items():
                if doc.metadata.get(key) != value:
                    match = False
                    break
            if match:
                filtered.append(doc)
        return filtered

    async def retrieve_with_scores(
        self,
        query: str,
        k: int | None = None,
    ) -> list[tuple[Document, float]]:
        """
        Retrieve documents with their similarity scores.

        Args:
            query: The search query.
            k: Number of documents to retrieve.

        Returns:
            List of (Document, score) tuples.
        """
        documents = await self.retrieve(query, k)
        return [
            (doc, doc.metadata.get("similarity_score", 0.0))
            for doc in documents
        ]

    def format_context(
        self,
        documents: list[Document],
        include_metadata: bool = False,
    ) -> str:
        """
        Format retrieved documents into a context string for the LLM.

        Args:
            documents: List of documents to format.
            include_metadata: Whether to include metadata in the context.

        Returns:
            Formatted context string.
        """
        if not documents:
            return "No relevant context found."

        context_parts = []

        for i, doc in enumerate(documents, 1):
            if include_metadata:
                source = doc.metadata.get("source", "Unknown")
                chunk_idx = doc.metadata.get("chunk_index", "?")
                context_parts.append(
                    f"[Source {i}: {source} (chunk {chunk_idx})]\n{doc.page_content}"
                )
            else:
                context_parts.append(f"[{i}]\n{doc.page_content}")

        return "\n\n---\n\n".join(context_parts)

    def get_source_documents(
        self,
        documents: list[Document],
    ) -> list[dict[str, Any]]:
        """
        Extract source information from documents for citation.

        Args:
            documents: List of documents.

        Returns:
            List of source metadata dictionaries.
        """
        sources = []
        seen_sources = set()

        for doc in documents:
            source = doc.metadata.get("source", "Unknown")
            doc_id = doc.metadata.get("document_id", "")

            # Deduplicate by source
            source_key = f"{source}_{doc_id}"
            if source_key not in seen_sources:
                seen_sources.add(source_key)
                sources.append({
                    "source": source,
                    "document_id": doc_id,
                    "chunk_index": doc.metadata.get("chunk_index"),
                    "similarity_score": doc.metadata.get("similarity_score"),
                })

        return sources

    def get_statistics(self) -> dict[str, Any]:
        """
        Get retrieval statistics.

        Returns:
            Dictionary with retrieval configuration and stats.
        """
        vector_stats = self.vector_store.get_statistics()
        return {
            "k": self.k,
            "score_threshold": self.score_threshold,
            "embedding_provider": self.embedding_service.provider_name,
            "embedding_model": self.embedding_service.model_name,
            "vector_store": vector_stats,
        }


# Singleton instance
_retrieval_service: RetrievalService | None = None


def get_retrieval_service() -> RetrievalService:
    """Get or create the retrieval service instance."""
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = RetrievalService()
    return _retrieval_service


def reset_retrieval_service() -> None:
    """Reset the retrieval service singleton (useful for testing)."""
    global _retrieval_service
    _retrieval_service = None
