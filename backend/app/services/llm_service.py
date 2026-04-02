"""LLM service for chat completions using OpenAI or Ollama."""

import logging
from typing import Any, AsyncIterator, Protocol

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.core.config import settings
from app.core.exceptions import LLMException

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    """Protocol for LLM providers."""

    def invoke(self, messages: list[BaseMessage]) -> AIMessage:
        """Invoke the LLM with messages."""
        ...

    async def ainvoke(self, messages: list[BaseMessage]) -> AIMessage:
        """Async invoke the LLM with messages."""
        ...


# Default RAG prompt template
RAG_SYSTEM_PROMPT = """You are a helpful assistant that answers questions based on the provided context.

Instructions:
- Use ONLY the information from the context below to answer the question
- If the context doesn't contain enough information to answer, say so clearly
- Do not make up information that isn't in the context
- Cite the relevant parts of the context when appropriate
- Be concise but thorough in your answers

Context:
{context}"""

RAG_HUMAN_PROMPT = """{question}"""


class LLMService:
    """Service for LLM chat completions."""

    def __init__(
        self,
        use_openai: bool = True,
        openai_api_key: str | None = None,
        openai_model: str | None = None,
        ollama_base_url: str | None = None,
        ollama_model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> None:
        """
        Initialize the LLM service.

        Args:
            use_openai: If True, use OpenAI. If False, use Ollama.
            openai_api_key: OpenAI API key. Defaults to settings.openai_api_key.
            openai_model: OpenAI model. Defaults to settings.openai_model.
            ollama_base_url: Ollama base URL. Defaults to settings.ollama_base_url.
            ollama_model: Ollama model. Defaults to settings.ollama_model.
            temperature: Sampling temperature (0-2).
            max_tokens: Maximum tokens in response.
        """
        self.use_openai = use_openai
        self.openai_api_key = openai_api_key or settings.openai_api_key
        self.openai_model = openai_model or settings.openai_model
        self.ollama_base_url = ollama_base_url or settings.ollama_base_url
        self.ollama_model = ollama_model or settings.ollama_model
        self.temperature = temperature
        self.max_tokens = max_tokens

        self._llm: LLMProvider | None = None
        self._initialize_llm()

    def _initialize_llm(self) -> None:
        """Initialize the LLM provider based on configuration."""
        if self.use_openai:
            self._initialize_openai()
        else:
            self._initialize_ollama()

    def _initialize_openai(self) -> None:
        """Initialize OpenAI chat model."""
        if not self.openai_api_key:
            logger.warning(
                "OpenAI API key not configured. "
                "Attempting to fall back to Ollama."
            )
            self.use_openai = False
            self._initialize_ollama()
            return

        try:
            from langchain_openai import ChatOpenAI

            self._llm = ChatOpenAI(
                api_key=self.openai_api_key,
                model=self.openai_model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )
            logger.info(f"Initialized OpenAI LLM with model: {self.openai_model}")

        except ImportError:
            raise LLMException(
                message="langchain-openai package not installed. "
                "Install with: pip install langchain-openai",
                details={"provider": "openai"},
            )
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI LLM: {e}")
            raise LLMException(
                message=f"Failed to initialize OpenAI LLM: {str(e)}",
                details={"provider": "openai", "model": self.openai_model},
            ) from e

    def _initialize_ollama(self) -> None:
        """Initialize Ollama chat model."""
        try:
            from langchain_ollama import ChatOllama

            self._llm = ChatOllama(
                base_url=self.ollama_base_url,
                model=self.ollama_model,
                temperature=self.temperature,
            )
            logger.info(
                f"Initialized Ollama LLM with model: {self.ollama_model} "
                f"at {self.ollama_base_url}"
            )

        except ImportError:
            raise LLMException(
                message="langchain-ollama package not installed. "
                "Install with: pip install langchain-ollama",
                details={"provider": "ollama"},
            )
        except Exception as e:
            logger.error(f"Failed to initialize Ollama LLM: {e}")
            raise LLMException(
                message=f"Failed to initialize Ollama LLM: {str(e)}",
                details={
                    "provider": "ollama",
                    "model": self.ollama_model,
                    "base_url": self.ollama_base_url,
                },
            ) from e

    @property
    def provider_name(self) -> str:
        """Get the name of the current LLM provider."""
        return "openai" if self.use_openai else "ollama"

    @property
    def model_name(self) -> str:
        """Get the model name being used."""
        return self.openai_model if self.use_openai else self.ollama_model

    @property
    def llm(self) -> LLMProvider:
        """Get the underlying LLM instance."""
        if self._llm is None:
            raise LLMException(
                message="LLM not initialized",
                details={"provider": self.provider_name},
            )
        return self._llm

    async def generate(
        self,
        messages: list[BaseMessage],
    ) -> str:
        """
        Generate a response from the LLM.

        Args:
            messages: List of messages in the conversation.

        Returns:
            Generated response text.

        Raises:
            LLMException: If generation fails.
        """
        if not messages:
            raise LLMException(
                message="Messages list cannot be empty",
                details={"provider": self.provider_name},
            )

        try:
            logger.debug(f"Generating response with {len(messages)} messages")
            response = await self.llm.ainvoke(messages)
            return response.content

        except Exception as e:
            logger.exception(f"LLM generation failed: {e}")
            raise LLMException(
                message=f"Failed to generate response: {str(e)}",
                details={
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "num_messages": len(messages),
                },
            ) from e

    async def generate_with_context(
        self,
        question: str,
        context: str,
        chat_history: list[BaseMessage] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """
        Generate a RAG response with context.

        Args:
            question: User's question.
            context: Retrieved context from documents.
            chat_history: Optional conversation history.
            system_prompt: Optional custom system prompt.

        Returns:
            Generated response text.

        Raises:
            LLMException: If generation fails.
        """
        # Build messages
        messages: list[BaseMessage] = []

        # System message with context
        system_content = (system_prompt or RAG_SYSTEM_PROMPT).format(context=context)
        messages.append(SystemMessage(content=system_content))

        # Add chat history if provided
        if chat_history:
            messages.extend(chat_history)

        # Add current question
        messages.append(HumanMessage(content=question))

        return await self.generate(messages)

    async def stream(
        self,
        messages: list[BaseMessage],
    ) -> AsyncIterator[str]:
        """
        Stream a response from the LLM.

        Args:
            messages: List of messages in the conversation.

        Yields:
            Response text chunks.

        Raises:
            LLMException: If streaming fails.
        """
        if not messages:
            raise LLMException(
                message="Messages list cannot be empty",
                details={"provider": self.provider_name},
            )

        try:
            logger.debug(f"Streaming response with {len(messages)} messages")
            async for chunk in self.llm.astream(messages):
                if hasattr(chunk, "content") and chunk.content:
                    yield chunk.content

        except Exception as e:
            logger.exception(f"LLM streaming failed: {e}")
            raise LLMException(
                message=f"Failed to stream response: {str(e)}",
                details={
                    "provider": self.provider_name,
                    "model": self.model_name,
                },
            ) from e

    async def stream_with_context(
        self,
        question: str,
        context: str,
        chat_history: list[BaseMessage] | None = None,
        system_prompt: str | None = None,
    ) -> AsyncIterator[str]:
        """
        Stream a RAG response with context.

        Args:
            question: User's question.
            context: Retrieved context from documents.
            chat_history: Optional conversation history.
            system_prompt: Optional custom system prompt.

        Yields:
            Response text chunks.
        """
        # Build messages
        messages: list[BaseMessage] = []

        # System message with context
        system_content = (system_prompt or RAG_SYSTEM_PROMPT).format(context=context)
        messages.append(SystemMessage(content=system_content))

        # Add chat history if provided
        if chat_history:
            messages.extend(chat_history)

        # Add current question
        messages.append(HumanMessage(content=question))

        async for chunk in self.stream(messages):
            yield chunk

    def create_rag_prompt(
        self,
        system_prompt: str | None = None,
        include_history: bool = True,
    ) -> ChatPromptTemplate:
        """
        Create a RAG prompt template.

        Args:
            system_prompt: Custom system prompt. Defaults to RAG_SYSTEM_PROMPT.
            include_history: Whether to include chat history placeholder.

        Returns:
            ChatPromptTemplate for RAG.
        """
        system = system_prompt or RAG_SYSTEM_PROMPT

        if include_history:
            return ChatPromptTemplate.from_messages([
                ("system", system),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("human", RAG_HUMAN_PROMPT),
            ])
        else:
            return ChatPromptTemplate.from_messages([
                ("system", system),
                ("human", RAG_HUMAN_PROMPT),
            ])

    def get_statistics(self) -> dict[str, Any]:
        """
        Get LLM service statistics.

        Returns:
            Dictionary with LLM configuration.
        """
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }


# Singleton instance
_llm_service: LLMService | None = None


def get_llm_service(use_openai: bool = True) -> LLMService:
    """
    Get or create the LLM service instance.

    Args:
        use_openai: If True, use OpenAI. If False, use Ollama.

    Returns:
        LLMService instance.
    """
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService(use_openai=use_openai)
    return _llm_service


def reset_llm_service() -> None:
    """Reset the LLM service singleton (useful for testing)."""
    global _llm_service
    _llm_service = None
