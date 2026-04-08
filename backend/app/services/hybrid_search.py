"""Hybrid search combining BM25 keyword search with semantic vector search."""

import logging
from typing import Any

from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.core.exceptions import RetrievalException
from app.services.embedding_service import get_embedding_service
from app.services.vector_store_service import get_vector_store_service

logger = logging.getLogger(__name__)


class HybridSearchService:
    """Service for hybrid search combining keyword and semantic search."""

    def __init__(
        self,
        k: int | None = None,
        semantic_weight: float = 0.5,
        keyword_weight: float = 0.5,
    ) -> None:
        """
        Initialize the hybrid search service.

        Args:
            k: Number of documents to retrieve per search method.
            semantic_weight: Weight for semantic search scores (0-1).
            keyword_weight: Weight for keyword search scores (0-1).
        """
        self.k = k or settings.retrieval_k
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight

        # Normalize weights
        total_weight = semantic_weight + keyword_weight
        self.semantic_weight = semantic_weight / total_weight
        self.keyword_weight = keyword_weight / total_weight

        self.embedding_service = get_embedding_service()
        self.vector_store = get_vector_store_service()

        # BM25 index (will be built on demand)
        self.bm25_index: BM25Okapi | None = None
        self.bm25_documents: list[Document] = []

        logger.info(
            f"Initialized HybridSearchService with k={self.k}, "
            f"semantic_weight={self.semantic_weight:.2f}, "
            f"keyword_weight={self.keyword_weight:.2f}"
        )

    def _build_bm25_index(self, documents: list[Document]) -> None:
        """
        Build BM25 index from documents.

        Args:
            documents: List of documents to index.
        """
        if not documents:
            logger.warning("No documents to build BM25 index")
            return

        # Tokenize documents (simple word splitting)
        tokenized_corpus = [
            doc.page_content.lower().split() for doc in documents
        ]

        self.bm25_index = BM25Okapi(tokenized_corpus)
        self.bm25_documents = documents

        logger.info(f"Built BM25 index with {len(documents)} documents")

    def _keyword_search(self, query: str, k: int) -> list[tuple[Document, float]]:
        """
        Perform BM25 keyword search.

        Args:
            query: Search query.
            k: Number of results to return.

        Returns:
            List of (Document, score) tuples.
        """
        if not self.bm25_index or not self.bm25_documents:
            logger.warning("BM25 index not built, returning empty results")
            return []

        # Tokenize query
        tokenized_query = query.lower().split()

        # Get BM25 scores
        bm25_scores = self.bm25_index.get_scores(tokenized_query)

        # Get top k documents with scores
        top_k_indices = bm25_scores.argsort()[-k:][::-1]

        results = []
        for idx in top_k_indices:
            if idx < len(self.bm25_documents):
                doc = self.bm25_documents[idx]
                score = float(bm25_scores[idx])
                results.append((doc, score))

        logger.debug(f"BM25 search returned {len(results)} results")
        return results

    async def _semantic_search(
        self, query: str, k: int
    ) -> list[tuple[Document, float]]:
        """
        Perform semantic vector search.

        Args:
            query: Search query.
            k: Number of results to return.

        Returns:
            List of (Document, score) tuples.
        """
        # Generate query embedding
        query_embedding = await self.embedding_service.aembed_query(query)

        # Search vector store
        documents = self.vector_store.similarity_search(query_embedding, k=k)

        # Extract scores from metadata
        results = []
        for doc in documents:
            score = doc.metadata.get("similarity_score", 0.0)
            results.append((doc, score))

        logger.debug(f"Semantic search returned {len(results)} results")
        return results

    def _normalize_scores(
        self, results: list[tuple[Document, float]]
    ) -> list[tuple[Document, float]]:
        """
        Normalize scores to 0-1 range using min-max normalization.

        Args:
            results: List of (Document, score) tuples.

        Returns:
            List with normalized scores.
        """
        if not results:
            return []

        scores = [score for _, score in results]
        min_score = min(scores)
        max_score = max(scores)

        if max_score == min_score:
            # All scores are the same, set to 0.5
            return [(doc, 0.5) for doc, _ in results]

        normalized = []
        for doc, score in results:
            normalized_score = (score - min_score) / (max_score - min_score)
            normalized.append((doc, normalized_score))

        return normalized

    def _reciprocal_rank_fusion(
        self,
        keyword_results: list[tuple[Document, float]],
        semantic_results: list[tuple[Document, float]],
        k: int = 60,
    ) -> list[tuple[Document, float]]:
        """
        Combine results using Reciprocal Rank Fusion (RRF).

        Args:
            keyword_results: BM25 search results.
            semantic_results: Vector search results.
            k: RRF constant (default 60).

        Returns:
            Combined and ranked results.
        """
        # Build document ID to document mapping
        doc_scores: dict[str, tuple[Document, float]] = {}

        # Process keyword results
        for rank, (doc, _) in enumerate(keyword_results, 1):
            doc_id = id(doc)  # Use object ID for deduplication
            rrf_score = 1.0 / (k + rank)
            doc_scores[doc_id] = (doc, rrf_score * self.keyword_weight)

        # Process semantic results
        for rank, (doc, _) in enumerate(semantic_results, 1):
            doc_id = id(doc)
            rrf_score = 1.0 / (k + rank)

            if doc_id in doc_scores:
                # Document exists, add scores
                existing_doc, existing_score = doc_scores[doc_id]
                doc_scores[doc_id] = (
                    existing_doc,
                    existing_score + (rrf_score * self.semantic_weight),
                )
            else:
                doc_scores[doc_id] = (doc, rrf_score * self.semantic_weight)

        # Sort by score (descending)
        sorted_results = sorted(
            doc_scores.values(), key=lambda x: x[1], reverse=True
        )

        logger.debug(f"RRF fusion produced {len(sorted_results)} unique results")
        return sorted_results

    def _weighted_score_fusion(
        self,
        keyword_results: list[tuple[Document, float]],
        semantic_results: list[tuple[Document, float]],
    ) -> list[tuple[Document, float]]:
        """
        Combine results using weighted score fusion.

        Args:
            keyword_results: Normalized BM25 results.
            semantic_results: Normalized vector results.

        Returns:
            Combined and ranked results.
        """
        # Build document to score mapping
        doc_scores: dict[str, tuple[Document, float]] = {}

        # Process keyword results
        for doc, score in keyword_results:
            doc_id = id(doc)
            doc_scores[doc_id] = (doc, score * self.keyword_weight)

        # Process semantic results
        for doc, score in semantic_results:
            doc_id = id(doc)
            if doc_id in doc_scores:
                existing_doc, existing_score = doc_scores[doc_id]
                doc_scores[doc_id] = (
                    existing_doc,
                    existing_score + (score * self.semantic_weight),
                )
            else:
                doc_scores[doc_id] = (doc, score * self.semantic_weight)

        # Sort by score (descending)
        sorted_results = sorted(
            doc_scores.values(), key=lambda x: x[1], reverse=True
        )

        logger.debug(
            f"Weighted fusion produced {len(sorted_results)} unique results"
        )
        return sorted_results

    async def hybrid_search(
        self,
        query: str,
        k: int | None = None,
        fusion_method: str = "rrf",
        filter_metadata: dict[str, Any] | None = None,
    ) -> list[Document]:
        """
        Perform hybrid search combining keyword and semantic search.

        Args:
            query: Search query.
            k: Number of documents to retrieve (total).
            fusion_method: Fusion method ('rrf' or 'weighted').
            filter_metadata: Optional metadata filters.

        Returns:
            List of relevant documents ranked by hybrid scores.

        Raises:
            RetrievalException: If search fails.
        """
        if not query or not query.strip():
            raise RetrievalException(
                message="Query cannot be empty",
                details={"query": query},
            )

        k = k or self.k

        try:
            # Build BM25 index if needed (in production, this should be pre-built)
            if not self.bm25_index:
                logger.info("Building BM25 index from vector store...")
                # Get all documents from vector store for BM25 indexing
                # This is a simplification; in production, maintain separate index
                all_docs = self.vector_store.similarity_search(
                    await self.embedding_service.aembed_query(""), k=1000
                )
                self._build_bm25_index(all_docs)

            # Retrieve more documents than needed for better fusion
            retrieval_k = k * 2

            # Perform keyword search
            logger.debug(f"Performing BM25 search for: {query[:50]}...")
            keyword_results = self._keyword_search(query, retrieval_k)

            # Perform semantic search
            logger.debug(f"Performing semantic search for: {query[:50]}...")
            semantic_results = await self._semantic_search(query, retrieval_k)

            # Combine results based on fusion method
            if fusion_method == "rrf":
                logger.debug("Using Reciprocal Rank Fusion")
                combined_results = self._reciprocal_rank_fusion(
                    keyword_results, semantic_results
                )
            else:  # weighted
                logger.debug("Using weighted score fusion")
                # Normalize scores before fusion
                keyword_results = self._normalize_scores(keyword_results)
                semantic_results = self._normalize_scores(semantic_results)
                combined_results = self._weighted_score_fusion(
                    keyword_results, semantic_results
                )

            # Take top k results
            top_results = combined_results[:k]

            # Extract documents and add hybrid scores to metadata
            documents = []
            for doc, score in top_results:
                doc.metadata["hybrid_score"] = score
                documents.append(doc)

            # Apply metadata filters if provided
            if filter_metadata:
                documents = self._filter_by_metadata(documents, filter_metadata)

            logger.info(
                f"Hybrid search returned {len(documents)} documents for query"
            )
            return documents

        except Exception as e:
            logger.exception(f"Hybrid search failed: {e}")
            raise RetrievalException(
                message=f"Failed to perform hybrid search: {str(e)}",
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

    def rebuild_bm25_index(self, documents: list[Document]) -> None:
        """
        Rebuild the BM25 index with new documents.

        Args:
            documents: List of documents to index.
        """
        self._build_bm25_index(documents)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get hybrid search statistics.

        Returns:
            Dictionary with configuration and stats.
        """
        return {
            "k": self.k,
            "semantic_weight": self.semantic_weight,
            "keyword_weight": self.keyword_weight,
            "bm25_documents_count": len(self.bm25_documents),
            "bm25_index_built": self.bm25_index is not None,
        }


# Singleton instance
_hybrid_search_service: HybridSearchService | None = None


def get_hybrid_search_service() -> HybridSearchService:
    """Get or create the hybrid search service instance."""
    global _hybrid_search_service
    if _hybrid_search_service is None:
        _hybrid_search_service = HybridSearchService()
    return _hybrid_search_service


def reset_hybrid_search_service() -> None:
    """Reset the hybrid search service singleton (useful for testing)."""
    global _hybrid_search_service
    _hybrid_search_service = None
