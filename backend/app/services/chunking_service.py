"""Text chunking service using LangChain's text splitters."""

import logging
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import settings

logger = logging.getLogger(__name__)


class ChunkingService:
    """Service for splitting text into chunks for embedding and retrieval."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        separators: list[str] | None = None,
    ) -> None:
        """
        Initialize the chunking service.

        Args:
            chunk_size: Maximum size of each chunk in characters.
                       Defaults to settings.chunk_size.
            chunk_overlap: Number of overlapping characters between chunks.
                          Defaults to settings.chunk_overlap.
            separators: List of separators to use for splitting.
                       Defaults to common text separators.
        """
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.separators = separators or [
            "\n\n",  # Paragraph breaks
            "\n",  # Line breaks
            ". ",  # Sentence endings
            "? ",  # Question endings
            "! ",  # Exclamation endings
            "; ",  # Semicolon
            ", ",  # Comma
            " ",  # Word boundary
            "",  # Character boundary (last resort)
        ]

        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators,
            length_function=len,
            is_separator_regex=False,
        )

        logger.info(
            f"Initialized ChunkingService with chunk_size={self.chunk_size}, "
            f"chunk_overlap={self.chunk_overlap}"
        )

    def chunk_text(
        self,
        text: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[Document]:
        """
        Split text into chunks and create LangChain Documents.

        Args:
            text: The text content to split into chunks.
            metadata: Optional metadata to attach to each chunk.
                     Common fields: source, document_id, file_name, etc.

        Returns:
            List of LangChain Document objects, each representing a chunk.
            Each document has:
            - page_content: The chunk text
            - metadata: Including source metadata and chunk_index
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for chunking")
            return []

        base_metadata = metadata or {}

        # Use LangChain's text splitter to create documents
        chunks = self._text_splitter.split_text(text)

        documents: list[Document] = []
        for index, chunk_text in enumerate(chunks):
            # Create metadata for this chunk
            chunk_metadata = {
                **base_metadata,
                "chunk_index": index,
                "total_chunks": len(chunks),
                "chunk_size": len(chunk_text),
            }

            doc = Document(
                page_content=chunk_text,
                metadata=chunk_metadata,
            )
            documents.append(doc)

        logger.info(
            f"Created {len(documents)} chunks from text "
            f"(original length: {len(text)} chars)"
        )

        return documents

    def chunk_documents(
        self,
        documents: list[Document],
    ) -> list[Document]:
        """
        Split multiple documents into chunks.

        This preserves the original document metadata while adding
        chunk-specific metadata.

        Args:
            documents: List of LangChain Documents to split.

        Returns:
            List of chunked Documents with preserved and extended metadata.
        """
        all_chunks: list[Document] = []

        for doc_index, doc in enumerate(documents):
            # Add document index to base metadata
            base_metadata = {
                **doc.metadata,
                "original_doc_index": doc_index,
            }

            chunks = self.chunk_text(
                text=doc.page_content,
                metadata=base_metadata,
            )
            all_chunks.extend(chunks)

        logger.info(
            f"Split {len(documents)} documents into {len(all_chunks)} total chunks"
        )

        return all_chunks

    def estimate_chunk_count(self, text: str) -> int:
        """
        Estimate the number of chunks that will be created from text.

        This is useful for progress estimation without actually chunking.

        Args:
            text: The text to estimate chunks for.

        Returns:
            Estimated number of chunks.
        """
        if not text:
            return 0

        text_length = len(text)
        effective_chunk_size = self.chunk_size - self.chunk_overlap

        if effective_chunk_size <= 0:
            return 1

        # Estimate based on text length and effective chunk size
        estimated = max(1, (text_length + effective_chunk_size - 1) // effective_chunk_size)

        return estimated

    def get_chunk_statistics(self, documents: list[Document]) -> dict[str, Any]:
        """
        Calculate statistics about chunked documents.

        Args:
            documents: List of chunked Documents.

        Returns:
            Dictionary with statistics about the chunks.
        """
        if not documents:
            return {
                "total_chunks": 0,
                "avg_chunk_size": 0,
                "min_chunk_size": 0,
                "max_chunk_size": 0,
                "total_characters": 0,
            }

        sizes = [len(doc.page_content) for doc in documents]

        return {
            "total_chunks": len(documents),
            "avg_chunk_size": sum(sizes) / len(sizes),
            "min_chunk_size": min(sizes),
            "max_chunk_size": max(sizes),
            "total_characters": sum(sizes),
        }


# Singleton instance for dependency injection
_chunking_service: ChunkingService | None = None


def get_chunking_service() -> ChunkingService:
    """Get or create the chunking service instance."""
    global _chunking_service
    if _chunking_service is None:
        _chunking_service = ChunkingService()
    return _chunking_service
