"""Embedding service for generating vector embeddings from text."""

import logging
from typing import Protocol

from langchain_core.documents import Document

from app.core.config import settings
from app.core.exceptions import EmbeddingException

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of documents."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query."""
        ...


class EmbeddingService:
    """Service for generating embeddings using OpenAI or Ollama."""

    def __init__(
        self,
        use_openai: bool = True,
        openai_api_key: str | None = None,
        openai_model: str | None = None,
        ollama_base_url: str | None = None,
        ollama_model: str | None = None,
    ) -> None:
        """
        Initialize the embedding service.

        Args:
            use_openai: If True, use OpenAI embeddings. If False, use Ollama.
            openai_api_key: OpenAI API key. Defaults to settings.openai_api_key.
            openai_model: OpenAI embedding model. Defaults to settings.openai_embedding_model.
            ollama_base_url: Ollama base URL. Defaults to settings.ollama_base_url.
            ollama_model: Ollama embedding model. Defaults to settings.ollama_embedding_model.
        """
        self.use_openai = use_openai
        self.openai_api_key = openai_api_key or settings.openai_api_key
        self.openai_model = openai_model or settings.openai_embedding_model
        self.ollama_base_url = ollama_base_url or settings.ollama_base_url
        self.ollama_model = ollama_model or settings.ollama_embedding_model

        self._embedding_provider: EmbeddingProvider | None = None
        self._initialize_provider()

    def _initialize_provider(self) -> None:
        """Initialize the embedding provider based on configuration."""
        if self.use_openai:
            self._initialize_openai()
        else:
            self._initialize_ollama()

    def _initialize_openai(self) -> None:
        """Initialize OpenAI embeddings."""
        if not self.openai_api_key:
            logger.warning(
                "OpenAI API key not configured. "
                "Attempting to fall back to Ollama embeddings."
            )
            self.use_openai = False
            self._initialize_ollama()
            return

        try:
            from langchain_openai import OpenAIEmbeddings

            self._embedding_provider = OpenAIEmbeddings(
                api_key=self.openai_api_key,
                model=self.openai_model,
            )
            logger.info(f"Initialized OpenAI embeddings with model: {self.openai_model}")

        except ImportError:
            raise EmbeddingException(
                message="langchain-openai package not installed. "
                "Install with: pip install langchain-openai",
                details={"provider": "openai"},
            )
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI embeddings: {e}")
            raise EmbeddingException(
                message=f"Failed to initialize OpenAI embeddings: {str(e)}",
                details={"provider": "openai", "model": self.openai_model},
            ) from e

    def _initialize_ollama(self) -> None:
        """Initialize Ollama embeddings."""
        try:
            from langchain_ollama import OllamaEmbeddings

            self._embedding_provider = OllamaEmbeddings(
                base_url=self.ollama_base_url,
                model=self.ollama_model,
            )
            logger.info(
                f"Initialized Ollama embeddings with model: {self.ollama_model} "
                f"at {self.ollama_base_url}"
            )

        except ImportError:
            raise EmbeddingException(
                message="langchain-ollama package not installed. "
                "Install with: pip install langchain-ollama",
                details={"provider": "ollama"},
            )
        except Exception as e:
            logger.error(f"Failed to initialize Ollama embeddings: {e}")
            raise EmbeddingException(
                message=f"Failed to initialize Ollama embeddings: {str(e)}",
                details={
                    "provider": "ollama",
                    "model": self.ollama_model,
                    "base_url": self.ollama_base_url,
                },
            ) from e

    @property
    def provider_name(self) -> str:
        """Get the name of the current embedding provider."""
        return "openai" if self.use_openai else "ollama"

    @property
    def model_name(self) -> str:
        """Get the model name being used."""
        return self.openai_model if self.use_openai else self.ollama_model

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors (each is a list of floats).

        Raises:
            EmbeddingException: If embedding generation fails.
        """
        if not texts:
            return []

        if self._embedding_provider is None:
            raise EmbeddingException(
                message="Embedding provider not initialized",
                details={"provider": self.provider_name},
            )

        try:
            logger.debug(f"Generating embeddings for {len(texts)} texts")
            embeddings = self._embedding_provider.embed_documents(texts)
            logger.info(
                f"Generated {len(embeddings)} embeddings using {self.provider_name}"
            )
            return embeddings

        except Exception as e:
            logger.exception(f"Failed to generate embeddings: {e}")
            raise EmbeddingException(
                message=f"Failed to generate embeddings: {str(e)}",
                details={
                    "provider": self.provider_name,
                    "model": self.model_name,
                    "num_texts": len(texts),
                },
            ) from e

    def embed_documents(self, documents: list[Document]) -> list[list[float]]:
        """
        Generate embeddings for a list of LangChain Documents.

        Args:
            documents: List of LangChain Document objects.

        Returns:
            List of embedding vectors (each is a list of floats).

        Raises:
            EmbeddingException: If embedding generation fails.
        """
        if not documents:
            return []

        texts = [doc.page_content for doc in documents]
        return self.get_embeddings(texts)

    def embed_query(self, query: str) -> list[float]:
        """
        Generate embedding for a single query text.

        This method may use different embedding strategies for queries
        vs documents depending on the provider.

        Args:
            query: Query text to embed.

        Returns:
            Embedding vector as a list of floats.

        Raises:
            EmbeddingException: If embedding generation fails.
        """
        if not query:
            raise EmbeddingException(
                message="Cannot embed empty query",
                details={"provider": self.provider_name},
            )

        if self._embedding_provider is None:
            raise EmbeddingException(
                message="Embedding provider not initialized",
                details={"provider": self.provider_name},
            )

        try:
            logger.debug(f"Generating query embedding using {self.provider_name}")
            embedding = self._embedding_provider.embed_query(query)
            return embedding

        except Exception as e:
            logger.exception(f"Failed to generate query embedding: {e}")
            raise EmbeddingException(
                message=f"Failed to generate query embedding: {str(e)}",
                details={
                    "provider": self.provider_name,
                    "model": self.model_name,
                },
            ) from e

    async def aget_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Async version of get_embeddings.

        Note: This currently wraps the synchronous method.
        Future versions may use native async embedding APIs.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors.
        """
        # For now, delegate to synchronous method
        # LangChain's OpenAI embeddings have async support but we keep it simple
        return self.get_embeddings(texts)

    async def aembed_query(self, query: str) -> list[float]:
        """
        Async version of embed_query.

        Args:
            query: Query text to embed.

        Returns:
            Embedding vector.
        """
        return self.embed_query(query)


# Singleton instance for dependency injection
_embedding_service: EmbeddingService | None = None


def get_embedding_service(use_openai: bool = True) -> EmbeddingService:
    """
    Get or create the embedding service instance.

    Args:
        use_openai: If True, use OpenAI. If False, use Ollama.

    Returns:
        EmbeddingService instance.
    """
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(use_openai=use_openai)
    return _embedding_service


def reset_embedding_service() -> None:
    """Reset the embedding service singleton (useful for testing)."""
    global _embedding_service
    _embedding_service = None
