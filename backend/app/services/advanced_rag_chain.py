"""Advanced RAG chain with hybrid search, reranking, and query expansion."""

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.core.exceptions import RAGException
from app.services.hybrid_search import get_hybrid_search_service
from app.services.llm_service import get_llm_service
from app.services.query_expansion import get_query_expansion_service
from app.services.reranker import get_reranker_service
from app.services.retrieval_service import get_retrieval_service

logger = logging.getLogger(__name__)


@dataclass
class AdvancedRAGResponse:
    """Response from the advanced RAG chain."""

    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    context_used: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    expanded_queries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "answer": self.answer,
            "sources": self.sources,
            "context_used": self.context_used,
            "metadata": self.metadata,
            "expanded_queries": self.expanded_queries,
        }


class AdvancedRAGChain:
    """Advanced RAG chain with multiple retrieval strategies."""

    def __init__(
        self,
        k: int | None = None,
        include_sources: bool = True,
        system_prompt: str | None = None,
    ) -> None:
        """
        Initialize the advanced RAG chain.

        Args:
            k: Number of documents to retrieve.
            include_sources: Whether to include source documents in response.
            system_prompt: Custom system prompt for the LLM.
        """
        self.k = k
        self.include_sources = include_sources
        self.system_prompt = system_prompt

        # Initialize services
        self.retrieval_service = get_retrieval_service()
        self.hybrid_search_service = get_hybrid_search_service()
        self.reranker_service = get_reranker_service()
        self.query_expansion_service = get_query_expansion_service()
        self.llm_service = get_llm_service()

        logger.info("Initialized Advanced RAG chain")

    async def query(
        self,
        question: str,
        chat_history: list[BaseMessage] | None = None,
        k: int | None = None,
        use_hybrid_search: bool = False,
        use_reranking: bool = False,
        use_query_expansion: bool = False,
        filter_metadata: dict[str, Any] | None = None,
    ) -> AdvancedRAGResponse:
        """
        Execute the advanced RAG pipeline with optional features.

        Args:
            question: User's question.
            chat_history: Optional conversation history.
            k: Number of documents to retrieve (overrides default).
            use_hybrid_search: Use hybrid search instead of semantic-only.
            use_reranking: Apply cross-encoder reranking.
            use_query_expansion: Expand query before retrieval.
            filter_metadata: Optional metadata filters.

        Returns:
            AdvancedRAGResponse with answer, sources, and metadata.

        Raises:
            RAGException: If the RAG pipeline fails.
        """
        logger.info(f"Processing advanced RAG query: {question[:50]}...")
        logger.info(
            f"Options: hybrid={use_hybrid_search}, rerank={use_reranking}, "
            f"expand={use_query_expansion}"
        )

        k = k or self.k
        expanded_queries = []

        try:
            # Step 1: Query expansion (if enabled)
            queries_to_process = [question]
            if use_query_expansion:
                logger.debug("Expanding query...")
                expanded_queries = await self.query_expansion_service.expand_query(
                    question, num_expansions=2
                )
                queries_to_process = expanded_queries
                logger.info(f"Expanded to {len(queries_to_process)} queries")

            # Step 2: Retrieve documents
            all_documents = []
            retrieval_k = k * 2 if use_reranking else k

            for query in queries_to_process:
                if use_hybrid_search:
                    logger.debug(f"Using hybrid search for: {query[:50]}...")
                    docs = await self.hybrid_search_service.hybrid_search(
                        query,
                        k=retrieval_k,
                        filter_metadata=filter_metadata,
                    )
                else:
                    logger.debug(f"Using semantic search for: {query[:50]}...")
                    docs = await self.retrieval_service.retrieve(
                        query,
                        k=retrieval_k,
                        filter_metadata=filter_metadata,
                    )

                # Deduplicate documents by content hash
                for doc in docs:
                    doc_hash = hash(doc.page_content)
                    if not any(
                        hash(d.page_content) == doc_hash for d in all_documents
                    ):
                        all_documents.append(doc)

            logger.info(f"Retrieved {len(all_documents)} unique documents")

            if not all_documents:
                logger.warning("No relevant documents found")
                return AdvancedRAGResponse(
                    answer="I couldn't find any relevant information in the knowledge base to answer your question.",
                    sources=[],
                    context_used="",
                    metadata={"documents_found": 0},
                    expanded_queries=expanded_queries,
                )

            # Step 3: Reranking (if enabled)
            if use_reranking:
                logger.debug(f"Reranking {len(all_documents)} documents...")
                all_documents = await self.reranker_service.arerank(
                    question, all_documents, top_k=k
                )
                logger.info(f"Reranked to top {len(all_documents)} documents")
            else:
                # Just take top k
                all_documents = all_documents[:k]

            # Step 4: Format context
            context = self.retrieval_service.format_context(
                all_documents, include_metadata=True
            )

            # Step 5: Generate response
            answer = await self.llm_service.generate_with_context(
                question=question,
                context=context,
                chat_history=chat_history,
                system_prompt=self.system_prompt,
            )

            # Step 6: Extract sources
            sources = []
            if self.include_sources:
                sources = self.retrieval_service.get_source_documents(all_documents)

            # Add rerank scores to sources if available
            for i, source in enumerate(sources):
                if i < len(all_documents):
                    doc = all_documents[i]
                    if "rerank_score" in doc.metadata:
                        source["rerank_score"] = doc.metadata["rerank_score"]
                    if "hybrid_score" in doc.metadata:
                        source["hybrid_score"] = doc.metadata["hybrid_score"]

            logger.info(f"Generated response with {len(sources)} sources")

            return AdvancedRAGResponse(
                answer=answer,
                sources=sources,
                context_used=context,
                metadata={
                    "documents_found": len(all_documents),
                    "llm_provider": self.llm_service.provider_name,
                    "llm_model": self.llm_service.model_name,
                    "hybrid_search_used": use_hybrid_search,
                    "reranking_used": use_reranking,
                    "query_expansion_used": use_query_expansion,
                },
                expanded_queries=expanded_queries,
            )

        except Exception as e:
            logger.exception(f"Advanced RAG query failed: {e}")
            raise RAGException(
                message=f"Advanced RAG pipeline failed: {str(e)}",
                details={"question": question},
            ) from e

    async def stream(
        self,
        question: str,
        chat_history: list[BaseMessage] | None = None,
        k: int | None = None,
        use_hybrid_search: bool = False,
        use_reranking: bool = False,
        use_query_expansion: bool = False,
        filter_metadata: dict[str, Any] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Stream the advanced RAG response.

        Yields events in the format:
        - {"type": "expansion", "queries": list} - Expanded queries
        - {"type": "retrieval", "documents": int} - Documents retrieved
        - {"type": "reranking", "documents": int} - Documents after reranking
        - {"type": "token", "content": str} - Response token
        - {"type": "sources", "sources": list} - Source documents
        - {"type": "done", "metadata": dict} - Completion

        Args:
            question: User's question.
            chat_history: Optional conversation history.
            k: Number of documents to retrieve.
            use_hybrid_search: Use hybrid search.
            use_reranking: Apply reranking.
            use_query_expansion: Expand query.
            filter_metadata: Metadata filters.

        Yields:
            Event dictionaries for streaming updates.

        Raises:
            RAGException: If the RAG pipeline fails.
        """
        logger.info(f"Streaming advanced RAG query: {question[:50]}...")

        k = k or self.k
        expanded_queries = []

        try:
            # Step 1: Query expansion
            queries_to_process = [question]
            if use_query_expansion:
                expanded_queries = await self.query_expansion_service.expand_query(
                    question, num_expansions=2
                )
                queries_to_process = expanded_queries

                yield {
                    "type": "expansion",
                    "queries": expanded_queries,
                }

            # Step 2: Retrieve documents
            all_documents = []
            retrieval_k = k * 2 if use_reranking else k

            for query in queries_to_process:
                if use_hybrid_search:
                    docs = await self.hybrid_search_service.hybrid_search(
                        query,
                        k=retrieval_k,
                        filter_metadata=filter_metadata,
                    )
                else:
                    docs = await self.retrieval_service.retrieve(
                        query,
                        k=retrieval_k,
                        filter_metadata=filter_metadata,
                    )

                for doc in docs:
                    doc_hash = hash(doc.page_content)
                    if not any(
                        hash(d.page_content) == doc_hash for d in all_documents
                    ):
                        all_documents.append(doc)

            yield {
                "type": "retrieval",
                "documents": len(all_documents),
            }

            if not all_documents:
                yield {
                    "type": "token",
                    "content": "I couldn't find any relevant information in the knowledge base to answer your question.",
                }
                yield {
                    "type": "done",
                    "metadata": {"documents_found": 0},
                }
                return

            # Step 3: Reranking
            if use_reranking:
                all_documents = await self.reranker_service.arerank(
                    question, all_documents, top_k=k
                )

                yield {
                    "type": "reranking",
                    "documents": len(all_documents),
                }
            else:
                all_documents = all_documents[:k]

            # Step 4: Format context
            context = self.retrieval_service.format_context(
                all_documents, include_metadata=True
            )

            # Step 5: Stream response
            full_response = ""
            async for token in self.llm_service.stream_with_context(
                question=question,
                context=context,
                chat_history=chat_history,
                system_prompt=self.system_prompt,
            ):
                full_response += token
                yield {
                    "type": "token",
                    "content": token,
                }

            # Step 6: Send sources
            if self.include_sources:
                sources = self.retrieval_service.get_source_documents(all_documents)

                # Add advanced scores
                for i, source in enumerate(sources):
                    if i < len(all_documents):
                        doc = all_documents[i]
                        if "rerank_score" in doc.metadata:
                            source["rerank_score"] = doc.metadata["rerank_score"]
                        if "hybrid_score" in doc.metadata:
                            source["hybrid_score"] = doc.metadata["hybrid_score"]

                yield {
                    "type": "sources",
                    "sources": sources,
                }

            # Step 7: Done
            yield {
                "type": "done",
                "metadata": {
                    "documents_found": len(all_documents),
                    "response_length": len(full_response),
                    "llm_provider": self.llm_service.provider_name,
                    "llm_model": self.llm_service.model_name,
                    "hybrid_search_used": use_hybrid_search,
                    "reranking_used": use_reranking,
                    "query_expansion_used": use_query_expansion,
                    "expanded_queries": expanded_queries,
                },
            }

        except Exception as e:
            logger.exception(f"Advanced RAG streaming failed: {e}")
            yield {
                "type": "error",
                "error": str(e),
            }

    async def query_with_history(
        self,
        question: str,
        history: list[dict[str, str]],
        k: int | None = None,
        use_hybrid_search: bool = False,
        use_reranking: bool = False,
        use_query_expansion: bool = False,
        filter_metadata: dict[str, Any] | None = None,
    ) -> AdvancedRAGResponse:
        """
        Query with conversation history in simple dict format.

        Args:
            question: User's question.
            history: List of {"role": "user"|"assistant", "content": str}.
            k: Number of documents to retrieve.
            use_hybrid_search: Use hybrid search.
            use_reranking: Apply reranking.
            use_query_expansion: Expand query.
            filter_metadata: Metadata filters.

        Returns:
            AdvancedRAGResponse with answer and sources.
        """
        # Convert dict history to LangChain messages
        chat_history: list[BaseMessage] = []
        for msg in history:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                chat_history.append(HumanMessage(content=content))
            elif role == "assistant":
                chat_history.append(AIMessage(content=content))

        return await self.query(
            question,
            chat_history=chat_history,
            k=k,
            use_hybrid_search=use_hybrid_search,
            use_reranking=use_reranking,
            use_query_expansion=use_query_expansion,
            filter_metadata=filter_metadata,
        )


# Singleton instance
_advanced_rag_chain: AdvancedRAGChain | None = None


def get_advanced_rag_chain() -> AdvancedRAGChain:
    """Get or create the advanced RAG chain instance."""
    global _advanced_rag_chain
    if _advanced_rag_chain is None:
        _advanced_rag_chain = AdvancedRAGChain()
    return _advanced_rag_chain


def reset_advanced_rag_chain() -> None:
    """Reset the advanced RAG chain singleton (useful for testing)."""
    global _advanced_rag_chain
    _advanced_rag_chain = None
