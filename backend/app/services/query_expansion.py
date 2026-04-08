"""Query expansion service for improving retrieval through query reformulation."""

import logging
from typing import Any

from app.core.config import settings
from app.core.exceptions import RAGException
from app.services.llm_service import get_llm_service

logger = logging.getLogger(__name__)


class QueryExpansionService:
    """Service for expanding and reformulating queries using LLM."""

    def __init__(self, num_expansions: int = 3) -> None:
        """
        Initialize the query expansion service.

        Args:
            num_expansions: Number of query variations to generate.
        """
        self.num_expansions = num_expansions
        self.llm_service = get_llm_service()

        logger.info(
            f"Initialized QueryExpansionService with num_expansions={num_expansions}"
        )

    async def expand_query(
        self,
        query: str,
        num_expansions: int | None = None,
    ) -> list[str]:
        """
        Expand a query into multiple variations.

        Args:
            query: Original search query.
            num_expansions: Number of variations to generate (overrides default).

        Returns:
            List of query variations including the original.

        Raises:
            RAGException: If query expansion fails.
        """
        if not query or not query.strip():
            raise RAGException(
                message="Query cannot be empty",
                details={"query": query},
            )

        num_expansions = num_expansions or self.num_expansions

        try:
            logger.debug(f"Expanding query: {query[:50]}...")

            # Build prompt for query expansion
            expansion_prompt = self._build_expansion_prompt(query, num_expansions)

            # Generate expansions using LLM
            response = await self.llm_service.generate(expansion_prompt)

            # Parse expansions from response
            expansions = self._parse_expansions(response, query)

            # Add original query as first item
            all_queries = [query] + expansions

            logger.info(
                f"Generated {len(expansions)} query expansions (total: {len(all_queries)})"
            )

            return all_queries

        except Exception as e:
            logger.exception(f"Query expansion failed: {e}")
            # Fallback to original query if expansion fails
            logger.warning("Falling back to original query")
            return [query]

    async def expand_with_context(
        self,
        query: str,
        context: str,
        num_expansions: int | None = None,
    ) -> list[str]:
        """
        Expand query with conversation context.

        Args:
            query: Current search query.
            context: Previous conversation context.
            num_expansions: Number of variations to generate.

        Returns:
            List of contextual query variations.
        """
        if not query or not query.strip():
            raise RAGException(
                message="Query cannot be empty",
                details={"query": query},
            )

        num_expansions = num_expansions or self.num_expansions

        try:
            logger.debug(f"Expanding query with context: {query[:50]}...")

            # Build contextual expansion prompt
            expansion_prompt = self._build_contextual_prompt(
                query, context, num_expansions
            )

            # Generate expansions
            response = await self.llm_service.generate(expansion_prompt)

            # Parse expansions
            expansions = self._parse_expansions(response, query)

            # Add original query
            all_queries = [query] + expansions

            logger.info(
                f"Generated {len(expansions)} contextual expansions (total: {len(all_queries)})"
            )

            return all_queries

        except Exception as e:
            logger.exception(f"Contextual query expansion failed: {e}")
            return [query]

    async def reformulate_query(self, query: str, context: str = "") -> str:
        """
        Reformulate a query for better retrieval (single variant).

        Args:
            query: Original query.
            context: Optional conversation context.

        Returns:
            Reformulated query string.
        """
        try:
            logger.debug(f"Reformulating query: {query[:50]}...")

            if context:
                prompt = f"""Given this conversation context and the user's question, reformulate the question to be more specific and complete for information retrieval.

Context: {context}

Current Question: {query}

Reformulated Question:"""
            else:
                prompt = f"""Reformulate this question to be more specific and better suited for information retrieval. Keep it concise.

Original Question: {query}

Reformulated Question:"""

            response = await self.llm_service.generate(prompt)
            reformulated = response.strip()

            logger.info(f"Reformulated query: {reformulated}")
            return reformulated

        except Exception as e:
            logger.exception(f"Query reformulation failed: {e}")
            return query

    def _build_expansion_prompt(self, query: str, num_expansions: int) -> str:
        """
        Build prompt for query expansion.

        Args:
            query: Original query.
            num_expansions: Number of variations to generate.

        Returns:
            Prompt string.
        """
        return f"""Generate {num_expansions} alternative ways to ask the following question. Each variation should maintain the same intent but use different wording or focus on different aspects. Return only the questions, one per line, without numbering.

Original Question: {query}

Alternative Questions:"""

    def _build_contextual_prompt(
        self, query: str, context: str, num_expansions: int
    ) -> str:
        """
        Build prompt for contextual query expansion.

        Args:
            query: Current query.
            context: Conversation context.
            num_expansions: Number of variations.

        Returns:
            Prompt string.
        """
        return f"""Given the conversation context below, generate {num_expansions} variations of the user's question that incorporate relevant context. Each variation should be self-contained and suitable for information retrieval. Return only the questions, one per line, without numbering.

Context: {context}

Current Question: {query}

Contextual Variations:"""

    def _parse_expansions(self, response: str, original_query: str) -> list[str]:
        """
        Parse query expansions from LLM response.

        Args:
            response: LLM response text.
            original_query: Original query for deduplication.

        Returns:
            List of parsed query variations.
        """
        # Split by newlines and clean up
        lines = response.strip().split("\n")

        expansions = []
        for line in lines:
            # Clean line
            line = line.strip()

            # Remove numbering (1., 2., etc.)
            if line and line[0].isdigit():
                line = line.split(".", 1)[-1].strip()
            if line and line[0] == "-":
                line = line[1:].strip()

            # Skip empty lines and duplicates
            if line and line != original_query and line not in expansions:
                expansions.append(line)

        return expansions

    async def multi_query_retrieval(
        self,
        query: str,
        retrieval_func,
        num_expansions: int | None = None,
        k_per_query: int = 3,
    ) -> list[Any]:
        """
        Retrieve documents using multiple query variations.

        Args:
            query: Original query.
            retrieval_func: Async function that takes a query and returns documents.
            num_expansions: Number of query variations to generate.
            k_per_query: Number of documents to retrieve per query.

        Returns:
            Combined and deduplicated list of documents.
        """
        try:
            # Expand query
            queries = await self.expand_query(query, num_expansions)

            logger.debug(f"Performing multi-query retrieval with {len(queries)} queries")

            # Retrieve for each query
            all_documents = []
            seen_doc_ids = set()

            for q in queries:
                try:
                    docs = await retrieval_func(q, k=k_per_query)

                    # Deduplicate by document content hash
                    for doc in docs:
                        doc_id = hash(doc.page_content)
                        if doc_id not in seen_doc_ids:
                            seen_doc_ids.add(doc_id)
                            all_documents.append(doc)
                except Exception as e:
                    logger.warning(f"Retrieval failed for query '{q[:50]}...': {e}")
                    continue

            logger.info(
                f"Multi-query retrieval returned {len(all_documents)} unique documents"
            )

            return all_documents

        except Exception as e:
            logger.exception(f"Multi-query retrieval failed: {e}")
            raise RAGException(
                message=f"Failed to perform multi-query retrieval: {str(e)}",
                details={"query": query},
            ) from e

    def get_statistics(self) -> dict[str, Any]:
        """
        Get query expansion statistics.

        Returns:
            Dictionary with configuration.
        """
        return {
            "num_expansions": self.num_expansions,
            "llm_provider": self.llm_service.provider_name,
            "llm_model": self.llm_service.model_name,
        }


# Singleton instance
_query_expansion_service: QueryExpansionService | None = None


def get_query_expansion_service() -> QueryExpansionService:
    """Get or create the query expansion service instance."""
    global _query_expansion_service
    if _query_expansion_service is None:
        _query_expansion_service = QueryExpansionService()
    return _query_expansion_service


def reset_query_expansion_service() -> None:
    """Reset the query expansion service singleton (useful for testing)."""
    global _query_expansion_service
    _query_expansion_service = None
