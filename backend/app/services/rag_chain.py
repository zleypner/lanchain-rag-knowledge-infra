"""RAG chain implementation using LangChain Expression Language (LCEL)."""

import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.core.exceptions import RAGException
from app.services.llm_service import get_llm_service
from app.services.retrieval_service import get_retrieval_service

logger = logging.getLogger(__name__)


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

        logger.info("Initialized RAG chain")

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
        logger.info(f"Processing RAG query: {question[:50]}...")

        try:
            # Step 1: Retrieve relevant documents
            k = k or self.k
            documents = await self.retrieval_service.retrieve(question, k=k)

            if not documents:
                logger.warning("No relevant documents found")
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
            answer = await self.llm_service.generate_with_context(
                question=question,
                context=context,
                chat_history=chat_history,
                system_prompt=self.system_prompt,
            )

            # Step 4: Extract sources
            sources = []
            if self.include_sources:
                sources = self.retrieval_service.get_source_documents(documents)

            logger.info(f"Generated response with {len(sources)} sources")

            return RAGResponse(
                answer=answer,
                sources=sources,
                context_used=context,
                metadata={
                    "documents_found": len(documents),
                    "llm_provider": self.llm_service.provider_name,
                    "llm_model": self.llm_service.model_name,
                },
            )

        except Exception as e:
            logger.exception(f"RAG query failed: {e}")
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
