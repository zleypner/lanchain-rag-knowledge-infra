"""Conversation models for session and message management."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


class MessageRole(str, Enum):
    """Role of a message sender."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class Message:
    """Represents a single message in a conversation."""

    role: MessageRole
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    id: str = field(default_factory=lambda: str(uuid4()))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Message":
        """Create message from dictionary."""
        return cls(
            id=data.get("id", str(uuid4())),
            role=MessageRole(data["role"]),
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"])
            if "timestamp" in data
            else datetime.now(timezone.utc),
            metadata=data.get("metadata", {}),
        )


@dataclass
class Conversation:
    """Represents a conversation session with message history."""

    id: str = field(default_factory=lambda: str(uuid4()))
    messages: list[Message] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_message(
        self,
        role: MessageRole,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        """
        Add a message to the conversation.

        Args:
            role: Role of the message sender.
            content: Message content.
            metadata: Optional metadata for the message.

        Returns:
            The created Message.
        """
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {},
        )
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)
        return message

    def add_user_message(self, content: str) -> Message:
        """Add a user message."""
        return self.add_message(MessageRole.USER, content)

    def add_assistant_message(
        self,
        content: str,
        sources: list[dict[str, Any]] | None = None,
    ) -> Message:
        """Add an assistant message with optional sources."""
        metadata = {}
        if sources:
            metadata["sources"] = sources
        return self.add_message(MessageRole.ASSISTANT, content, metadata)

    def get_messages(
        self,
        limit: int | None = None,
        exclude_system: bool = False,
    ) -> list[Message]:
        """
        Get messages from the conversation.

        Args:
            limit: Maximum number of messages to return (from most recent).
            exclude_system: Whether to exclude system messages.

        Returns:
            List of messages.
        """
        messages = self.messages

        if exclude_system:
            messages = [m for m in messages if m.role != MessageRole.SYSTEM]

        if limit is not None and limit > 0:
            messages = messages[-limit:]

        return messages

    def get_message_count(self) -> int:
        """Get total number of messages."""
        return len(self.messages)

    def clear_messages(self) -> None:
        """Clear all messages from the conversation."""
        self.messages = []
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert conversation to dictionary."""
        return {
            "id": self.id,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
        }

    def to_langchain_messages(
        self,
        limit: int | None = None,
    ) -> list[tuple[str, str]]:
        """
        Convert to LangChain message format.

        Args:
            limit: Maximum number of message pairs to include.

        Returns:
            List of (role, content) tuples for LangChain.
        """
        from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

        messages = self.get_messages(limit=limit)
        langchain_messages = []

        for msg in messages:
            if msg.role == MessageRole.USER:
                langchain_messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.ASSISTANT:
                langchain_messages.append(AIMessage(content=msg.content))
            elif msg.role == MessageRole.SYSTEM:
                langchain_messages.append(SystemMessage(content=msg.content))

        return langchain_messages
