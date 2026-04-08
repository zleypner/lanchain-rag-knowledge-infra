"""Reranking service using cross-encoder models for improved relevance."""

import logging
from typing import Any

from langchain_core.documents import Document
from sentence_transformers import CrossEncoder

from app.core.config import settings
from app.core.exceptions import RetrievalException

logger = logging.getLogger(__name__)


class RerankerService:
    """Service for reranking documents using cross-encoder models."""

    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        top_k: int | None = None,
    ) -> None:
        """
        Initialize the reranker service.

        Args:
            model_name: Cross-encoder model name from sentence-transformers.
                       Default: cross-encoder/ms-marco-MiniLM-L-6-v2 (fast, good quality)
                       Alternatives:
                       - cross-encoder/ms-marco-TinyBERT-L-2-v2 (faster, lower quality)
                       - cross-encoder/ms-marco-MiniLM-L-12-v2 (slower, better quality)
            top_k: Number of top documents to return after reranking.
        """
        self.model_name = model_name
        self.top_k = top_k or settings.retrieval_k

        # Load cross-encoder model
        logger.info(f"Loading cross-encoder model: {model_name}")
        try:
            self.model = CrossEncoder(model_name)
            logger.info("Cross-encoder model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load cross-encoder model: {e}")
            raise RuntimeError(
                f"Failed to load reranker model {model_name}: {str(e)}"
            ) from e

    def rerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int | None = None,
    ) -> list[Document]:
        """
        Rerank documents using cross-encoder model.

        Args:
            query: Search query.
            documents: List of documents to rerank.
            top_k: Number of top documents to return (overrides default).

        Returns:
            Reranked list of documents with updated scores.

        Raises:
            RetrievalException: If reranking fails.
        """
        if not query or not query.strip():
            raise RetrievalException(
                message="Query cannot be empty",
                details={"query": query},
            )

        if not documents:
            logger.warning("No documents to rerank")
            return []

        top_k = top_k or self.top_k

        try:
            logger.debug(f"Reranking {len(documents)} documents for query: {query[:50]}...")

            # Prepare query-document pairs for cross-encoder
            pairs = [[query, doc.page_content] for doc in documents]

            # Get cross-encoder scores
            scores = self.model.predict(pairs)

            # Combine documents with scores
            doc_score_pairs = list(zip(documents, scores))

            # Sort by score (descending - higher is better for cross-encoders)
            doc_score_pairs.sort(key=lambda x: x[1], reverse=True)

            # Take top k
            top_docs = doc_score_pairs[:top_k]

            # Update document metadata with rerank scores
            reranked_documents = []
            for rank, (doc, score) in enumerate(top_docs, 1):
                doc.metadata["rerank_score"] = float(score)
                doc.metadata["rerank_position"] = rank
                reranked_documents.append(doc)

            logger.info(
                f"Reranked {len(documents)} documents, returning top {len(reranked_documents)}"
            )

            return reranked_documents

        except Exception as e:
            logger.exception(f"Reranking failed: {e}")
            raise RetrievalException(
                message=f"Failed to rerank documents: {str(e)}",
                details={"query": query, "document_count": len(documents)},
            ) from e

    async def arerank(
        self,
        query: str,
        documents: list[Document],
        top_k: int | None = None,
    ) -> list[Document]:
        """
        Async wrapper for rerank (cross-encoder is CPU-bound, runs in sync).

        Args:
            query: Search query.
            documents: List of documents to rerank.
            top_k: Number of top documents to return.

        Returns:
            Reranked list of documents.
        """
        # Note: sentence-transformers doesn't have native async support
        # For production, consider running in thread pool executor
        return self.rerank(query, documents, top_k)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get reranker statistics.

        Returns:
            Dictionary with model info and configuration.
        """
        return {
            "model_name": self.model_name,
            "top_k": self.top_k,
            "model_max_length": getattr(self.model, "max_length", None),
        }


# Singleton instance
_reranker_service: RerankerService | None = None


def get_reranker_service() -> RerankerService:
    """Get or create the reranker service instance."""
    global _reranker_service
    if _reranker_service is None:
        _reranker_service = RerankerService()
    return _reranker_service


def reset_reranker_service() -> None:
    """Reset the reranker service singleton (useful for testing)."""
    global _reranker_service
    _reranker_service = None
