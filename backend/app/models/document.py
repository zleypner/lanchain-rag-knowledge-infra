"""Document model for tracking uploaded documents."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class DocumentStatus(str, Enum):
    """Status of document processing."""

    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


@dataclass
class Document:
    """Document model representing an uploaded file."""

    id: str = field(default_factory=lambda: str(uuid4()))
    filename: str = ""
    original_filename: str = ""
    file_path: str = ""
    file_type: str = ""
    file_size: int = 0
    status: DocumentStatus = DocumentStatus.PENDING
    chunk_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert document to dictionary representation."""
        return {
            "id": self.id,
            "filename": self.filename,
            "original_filename": self.original_filename,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "file_size": self.file_size,
            "status": self.status.value,
            "chunk_count": self.chunk_count,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    def update_status(self, status: DocumentStatus) -> None:
        """Update document status and updated_at timestamp."""
        self.status = status
        self.updated_at = datetime.now(timezone.utc)
