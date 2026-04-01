"""Custom exceptions for the application."""

from typing import Any


class RAGException(Exception):
    """Base exception for RAG application."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class DocumentException(RAGException):
    """Exception raised for document-related errors."""

    pass


class DocumentNotFoundError(DocumentException):
    """Exception raised when a document is not found."""

    def __init__(self, document_id: str) -> None:
        super().__init__(
            message=f"Document not found: {document_id}",
            details={"document_id": document_id},
        )


class DocumentUploadError(DocumentException):
    """Exception raised when document upload fails."""

    pass


class DocumentParsingError(DocumentException):
    """Exception raised when document parsing fails."""

    pass


class InvalidFileTypeError(DocumentException):
    """Exception raised when file type is not allowed."""

    def __init__(self, file_type: str, allowed_types: list[str]) -> None:
        super().__init__(
            message=f"Invalid file type: {file_type}. Allowed: {', '.join(allowed_types)}",
            details={"file_type": file_type, "allowed_types": allowed_types},
        )


class FileSizeLimitError(DocumentException):
    """Exception raised when file size exceeds limit."""

    def __init__(self, size_mb: float, max_size_mb: int) -> None:
        super().__init__(
            message=f"File size ({size_mb:.2f}MB) exceeds limit ({max_size_mb}MB)",
            details={"size_mb": size_mb, "max_size_mb": max_size_mb},
        )


class EmbeddingException(RAGException):
    """Exception raised for embedding-related errors."""

    pass


class VectorStoreException(RAGException):
    """Exception raised for vector store errors."""

    pass


class LLMException(RAGException):
    """Exception raised for LLM-related errors."""

    pass


class RetrievalException(RAGException):
    """Exception raised for retrieval errors."""

    pass


class ConversationException(RAGException):
    """Exception raised for conversation management errors."""

    pass


class ConversationNotFoundError(ConversationException):
    """Exception raised when a conversation is not found."""

    def __init__(self, session_id: str) -> None:
        super().__init__(
            message=f"Conversation not found: {session_id}",
            details={"session_id": session_id},
        )
