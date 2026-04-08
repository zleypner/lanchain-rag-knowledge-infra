"""RAG chain implementation using LangChain Expression Language (LCEL)."""

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.core.config import settings
from app.core.exceptions import RAGException
from app.observability import get_logger, get_metrics
from app.observability.tracer import get_rag_tracer
from app.services.llm_service import get_llm_service
from app.services.redis_cache import get_redis_cache
from app.services.retrieval_service import get_retrieval_service

logger = get_logger(__name__)
metrics = get_metrics()
tracer = get_rag_tracer()


@dataclass
class RAGResponse:
    """Response from the RAG chain."""

    answer: str
    sources: list[dict[str, Any]] = field(default_factory=list)
    context_used: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "answer": self.answer,
            "sources": self.sources,
            "context_used": self.context_used,
            "metadata": self.metadata,
        }


class RAGChain:
    """RAG chain that orchestrates retrieval and generation."""

    def __init__(
        self,
        k: int | None = None,
        include_sources: bool = True,
        system_prompt: str | None = None,
    ) -> None:
        """
        Initialize the RAG chain.

        Args:
            k: Number of documents to retrieve.
            include_sources: Whether to include source documents in response.
            system_prompt: Custom system prompt for the LLM.
        """
        self.k = k
        self.include_sources = include_sources
        self.system_prompt = system_prompt

        self.retrieval_service = get_retrieval_service()
        self.llm_service = get_llm_service()
        self._cache = get_redis_cache()

        logger.info("Initialized RAG chain")

    def _generate_cache_key(self, question: str, k: int, history_hash: str = "") -> str:
        """Generate a cache key for a query."""
        query_data = f"{question}:{k}:{history_hash}"
        return hashlib.sha256(query_data.encode()).hexdigest()

    def _hash_history(self, chat_history: list[BaseMessage] | None) -> str:
        """Generate a hash for chat history."""
        if not chat_history:
            return ""
        history_str = json.dumps(
            [{"role": type(msg).__name__, "content": msg.content} for msg in chat_history]
        )
        return hashlib.sha256(history_str.encode()).hexdigest()[:16]

    async def query(
        self,
        question: str,
        chat_history: list[BaseMessage] | None = None,
        k: int | None = None,
    ) -> RAGResponse:
        """
        Execute the RAG pipeline: retrieve → generate.

        Args:
            question: User's question.
            chat_history: Optional conversation history.
            k: Number of documents to retrieve (overrides default).

        Returns:
            RAGResponse with answer, sources, and metadata.

        Raises:
            RAGException: If the RAG pipeline fails.
        """
        start_time = time.time()
        logger.info("rag_query_started", query_length=len(question))

        with tracer.trace_query(question) as query_span:
            try:
                # Step 1: Retrieve relevant documents
                k = k or self.k
                retrieval_start = time.time()

                with tracer.trace_retrieval(k=k) as retrieval_span:
                    documents = await self.retrieval_service.retrieve(question, k=k)
                    retrieval_span.set_attribute("documents_retrieved", len(documents))

                retrieval_time = time.time() - retrieval_start

                if not documents:
                    logger.warning("no_documents_found", query=question[:50])
                    metrics.record_rag_query(
                        duration=time.time() - start_time,
                        status="no_results",
                        retrieval_time=retrieval_time,
                        documents_retrieved=0,
                    )
                    return RAGResponse(
                        answer="I couldn't find any relevant information in the knowledge base to answer your question.",
                        sources=[],
                        context_used="",
                        metadata={"documents_found": 0},
                    )

                # Step 2: Format context
                context = self.retrieval_service.format_context(
                    documents, include_metadata=True
                )

                # Step 3: Generate response
                generation_start = time.time()

                with tracer.trace_generation(
                    model=self.llm_service.model_name,
                    provider=self.llm_service.provider_name,
                ) as generation_span:
                    answer = await self.llm_service.generate_with_context(
                        question=question,
                        context=context,
                        chat_history=chat_history,
                        system_prompt=self.system_prompt,
                    )
                    generation_span.set_attribute("answer_length", len(answer))

                generation_time = time.time() - generation_start

                # Step 4: Extract sources
                sources = []
                if self.include_sources:
                    sources = self.retrieval_service.get_source_documents(documents)

                total_time = time.time() - start_time

                logger.info(
                    "rag_query_completed",
                    documents_found=len(documents),
                    sources_count=len(sources),
                    total_time_ms=round(total_time * 1000, 2),
                    retrieval_time_ms=round(retrieval_time * 1000, 2),
                    generation_time_ms=round(generation_time * 1000, 2),
                )

                # Record metrics
                metrics.record_rag_query(
                    duration=total_time,
                    status="success",
                    retrieval_time=retrieval_time,
                    generation_time=generation_time,
                    documents_retrieved=len(documents),
                )

                query_span.set_attribute("documents_found", len(documents))
                query_span.set_attribute("sources_count", len(sources))

                return RAGResponse(
                    answer=answer,
                    sources=sources,
                    context_used=context,
                    metadata={
                        "documents_found": len(documents),
                        "llm_provider": self.llm_service.provider_name,
                        "llm_model": self.llm_service.model_name,
                        "retrieval_time_ms": round(retrieval_time * 1000, 2),
                        "generation_time_ms": round(generation_time * 1000, 2),
                        "total_time_ms": round(total_time * 1000, 2),
                    },
                )

            except Exception as e:
                total_time = time.time() - start_time
                logger.error(
                    "rag_query_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=round(total_time * 1000, 2),
                )
                metrics.record_rag_query(
                    duration=total_time,
                    status="error",
                )
                metrics.record_error(
                    error_type=type(e).__name__,
                    component="rag_chain",
                )
                raise RAGException(
                    message=f"RAG pipeline failed: {str(e)}",
                    details={"question": question},
                ) from e

    async def stream(
        self,
        question: str,
        chat_history: list[BaseMessage] | None = None,
        k: int | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Stream the RAG response.

        Yields events in the format:
        - {"type": "retrieval", "documents": int} - Documents retrieved
        - {"type": "token", "content": str} - Response token
        - {"type": "sources", "sources": list} - Source documents
        - {"type": "done", "metadata": dict} - Completion

        Args:
            question: User's question.
            chat_history: Optional conversation history.
            k: Number of documents to retrieve.

        Yields:
            Event dictionaries for streaming updates.

        Raises:
            RAGException: If the RAG pipeline fails.
        """
        logger.info(f"Streaming RAG query: {question[:50]}...")

        try:
            # Step 1: Retrieve documents
            k = k or self.k
            documents = await self.retrieval_service.retrieve(question, k=k)

            yield {
                "type": "retrieval",
                "documents": len(documents),
            }

            if not documents:
                yield {
                    "type": "token",
                    "content": "I couldn't find any relevant information in the knowledge base to answer your question.",
                }
                yield {
                    "type": "done",
                    "metadata": {"documents_found": 0},
                }
                return

            # Step 2: Format context
            context = self.retrieval_service.format_context(
                documents, include_metadata=True
            )

            # Step 3: Stream response
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

            # Step 4: Send sources
            if self.include_sources:
                sources = self.retrieval_service.get_source_documents(documents)
                yield {
                    "type": "sources",
                    "sources": sources,
                }

            # Step 5: Done
            yield {
                "type": "done",
                "metadata": {
                    "documents_found": len(documents),
                    "response_length": len(full_response),
                    "llm_provider": self.llm_service.provider_name,
                    "llm_model": self.llm_service.model_name,
                },
            }

        except Exception as e:
            logger.exception(f"RAG streaming failed: {e}")
            yield {
                "type": "error",
                "error": str(e),
            }

    async def query_with_history(
        self,
        question: str,
        history: list[dict[str, str]],
        k: int | None = None,
    ) -> RAGResponse:
        """
        Query with conversation history in simple dict format.

        Args:
            question: User's question.
            history: List of {"role": "user"|"assistant", "content": str}.
            k: Number of documents to retrieve.

        Returns:
            RAGResponse with answer and sources.
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

        return await self.query(question, chat_history=chat_history, k=k)

    def get_statistics(self) -> dict[str, Any]:
        """
        Get RAG chain statistics.

        Returns:
            Dictionary with chain configuration and stats.
        """
        return {
            "k": self.k,
            "include_sources": self.include_sources,
            "retrieval": self.retrieval_service.get_statistics(),
            "llm": self.llm_service.get_statistics(),
        }


# Singleton instance
_rag_chain: RAGChain | None = None


def get_rag_chain() -> RAGChain:
    """Get or create the RAG chain instance."""
    global _rag_chain
    if _rag_chain is None:
        _rag_chain = RAGChain()
    return _rag_chain


def reset_rag_chain() -> None:
    """Reset the RAG chain singleton (useful for testing)."""
    global _rag_chain
    _rag_chain = None
