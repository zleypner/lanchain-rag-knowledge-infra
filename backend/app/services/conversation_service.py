"""Conversation service for managing chat sessions and history."""

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.core.exceptions import ConversationNotFoundError
from app.models.conversation import Conversation, Message, MessageRole

logger = logging.getLogger(__name__)


class ConversationService:
    """Service for managing conversations and message history."""

    def __init__(
        self,
        max_history_length: int = 50,
        memory_window_size: int = 10,
    ) -> None:
        """
        Initialize the conversation service.

        Args:
            max_history_length: Maximum messages to store per conversation.
            memory_window_size: Number of recent messages to include in context.
        """
        self.max_history_length = max_history_length
        self.memory_window_size = memory_window_size

        # In-memory storage (will be replaced with database in Phase 5)
        self._conversations: dict[str, Conversation] = {}

        logger.info(
            f"Initialized ConversationService with "
            f"max_history={max_history_length}, window_size={memory_window_size}"
        )

    def create_conversation(
        self,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Conversation:
        """
        Create a new conversation.

        Args:
            session_id: Optional session ID. If not provided, one is generated.
            metadata: Optional metadata for the conversation.

        Returns:
            The created Conversation.
        """
        conversation = Conversation(metadata=metadata or {})

        if session_id:
            conversation.id = session_id

        self._conversations[conversation.id] = conversation
        logger.info(f"Created conversation: {conversation.id}")
        return conversation

    def get_conversation(self, session_id: str) -> Conversation:
        """
        Get a conversation by session ID.

        Args:
            session_id: The session identifier.

        Returns:
            The Conversation.

        Raises:
            ConversationNotFoundError: If conversation doesn't exist.
        """
        conversation = self._conversations.get(session_id)
        if conversation is None:
            raise ConversationNotFoundError(session_id=session_id)
        return conversation

    def get_or_create_conversation(
        self,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Conversation:
        """
        Get an existing conversation or create a new one.

        Args:
            session_id: Optional session ID.
            metadata: Optional metadata for new conversations.

        Returns:
            The Conversation (existing or new).
        """
        if session_id and session_id in self._conversations:
            return self._conversations[session_id]
        return self.create_conversation(session_id=session_id, metadata=metadata)

    def add_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> Message:
        """
        Add a message to a conversation.

        Args:
            session_id: The session identifier.
            role: Role of the message sender.
            content: Message content.
            metadata: Optional message metadata.

        Returns:
            The created Message.

        Raises:
            ConversationNotFoundError: If conversation doesn't exist.
        """
        conversation = self.get_conversation(session_id)
        message = conversation.add_message(role, content, metadata)

        # Trim history if too long
        if len(conversation.messages) > self.max_history_length:
            conversation.messages = conversation.messages[-self.max_history_length :]

        logger.debug(f"Added {role.value} message to conversation {session_id}")
        return message

    def add_exchange(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        sources: list[dict[str, Any]] | None = None,
    ) -> tuple[Message, Message]:
        """
        Add a user-assistant exchange to a conversation.

        Args:
            session_id: The session identifier.
            user_message: User's message content.
            assistant_message: Assistant's response content.
            sources: Optional source documents for the response.

        Returns:
            Tuple of (user_message, assistant_message).
        """
        conversation = self.get_or_create_conversation(session_id)

        user_msg = conversation.add_user_message(user_message)
        assistant_msg = conversation.add_assistant_message(assistant_message, sources)

        # Trim history if too long
        if len(conversation.messages) > self.max_history_length:
            conversation.messages = conversation.messages[-self.max_history_length :]

        return user_msg, assistant_msg

    def get_history(
        self,
        session_id: str,
        limit: int | None = None,
    ) -> list[Message]:
        """
        Get message history for a conversation.

        Args:
            session_id: The session identifier.
            limit: Maximum number of messages to return.

        Returns:
            List of messages.

        Raises:
            ConversationNotFoundError: If conversation doesn't exist.
        """
        conversation = self.get_conversation(session_id)
        return conversation.get_messages(limit=limit)

    def get_context_window(
        self,
        session_id: str,
        window_size: int | None = None,
    ) -> list[Message]:
        """
        Get the recent message window for context.

        Args:
            session_id: The session identifier.
            window_size: Number of messages to include. Defaults to memory_window_size.

        Returns:
            List of recent messages for context.
        """
        try:
            conversation = self.get_conversation(session_id)
            size = window_size or self.memory_window_size
            return conversation.get_messages(limit=size, exclude_system=True)
        except ConversationNotFoundError:
            return []

    def get_langchain_history(
        self,
        session_id: str,
        window_size: int | None = None,
    ) -> list:
        """
        Get conversation history in LangChain message format.

        Args:
            session_id: The session identifier.
            window_size: Number of messages to include.

        Returns:
            List of LangChain BaseMessage objects.
        """
        try:
            conversation = self.get_conversation(session_id)
            size = window_size or self.memory_window_size
            return conversation.to_langchain_messages(limit=size)
        except ConversationNotFoundError:
            return []

    def delete_conversation(self, session_id: str) -> bool:
        """
        Delete a conversation.

        Args:
            session_id: The session identifier.

        Returns:
            True if deleted, False if not found.
        """
        if session_id in self._conversations:
            del self._conversations[session_id]
            logger.info(f"Deleted conversation: {session_id}")
            return True
        return False

    def clear_history(self, session_id: str) -> None:
        """
        Clear message history for a conversation.

        Args:
            session_id: The session identifier.

        Raises:
            ConversationNotFoundError: If conversation doesn't exist.
        """
        conversation = self.get_conversation(session_id)
        conversation.clear_messages()
        logger.info(f"Cleared history for conversation: {session_id}")

    def list_conversations(
        self,
        page: int = 1,
        page_size: int = 10,
    ) -> tuple[list[Conversation], int]:
        """
        List all conversations with pagination.

        Args:
            page: Page number (1-indexed).
            page_size: Number of items per page.

        Returns:
            Tuple of (conversations list, total count).
        """
        conversations = list(self._conversations.values())
        conversations.sort(key=lambda c: c.updated_at, reverse=True)

        total = len(conversations)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size

        return conversations[start_idx:end_idx], total

    def get_statistics(self) -> dict[str, Any]:
        """
        Get conversation service statistics.

        Returns:
            Dictionary with service stats.
        """
        total_messages = sum(
            len(c.messages) for c in self._conversations.values()
        )
        return {
            "total_conversations": len(self._conversations),
            "total_messages": total_messages,
            "max_history_length": self.max_history_length,
            "memory_window_size": self.memory_window_size,
        }


# Singleton instance
_conversation_service: ConversationService | None = None


def get_conversation_service() -> ConversationService:
    """Get or create the conversation service instance."""
    global _conversation_service
    if _conversation_service is None:
        _conversation_service = ConversationService()
    return _conversation_service


def reset_conversation_service() -> None:
    """Reset the conversation service singleton (useful for testing)."""
    global _conversation_service
    _conversation_service = None
