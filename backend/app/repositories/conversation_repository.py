"""Repository for conversation database operations."""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import ConversationModel, MessageModel
from app.models.conversation import Conversation as ConversationDataclass
from app.models.conversation import Message as MessageDataclass
from app.models.conversation import MessageRole

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Repository for conversation and message CRUD operations."""

    async def create(
        self,
        session: AsyncSession,
        conversation_id: str | None = None,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ConversationModel:
        """
        Create a new conversation.

        Args:
            session: Database session.
            conversation_id: Optional custom ID. Generated if not provided.
            title: Optional conversation title.
            metadata: Optional metadata dictionary.

        Returns:
            Created ConversationModel instance.
        """
        conversation = ConversationModel(
            id=conversation_id or str(uuid4()),
            title=title,
            metadata_=metadata or {},
        )

        session.add(conversation)
        await session.flush()

        logger.info(f"Created conversation: {conversation.id}")
        return conversation

    async def get_by_id(
        self,
        session: AsyncSession,
        conversation_id: str,
        include_messages: bool = True,
    ) -> ConversationModel | None:
        """
        Get a conversation by its ID.

        Args:
            session: Database session.
            conversation_id: The conversation ID.
            include_messages: Whether to load messages.

        Returns:
            ConversationModel if found, None otherwise.
        """
        query = select(ConversationModel).where(
            ConversationModel.id == conversation_id
        )

        if include_messages:
            query = query.options(selectinload(ConversationModel.messages))

        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        session: AsyncSession,
        conversation_id: str,
    ) -> ConversationModel:
        """
        Get an existing conversation or create a new one.

        Args:
            session: Database session.
            conversation_id: The conversation ID.

        Returns:
            ConversationModel instance.
        """
        conversation = await self.get_by_id(session, conversation_id)
        if conversation is None:
            conversation = await self.create(session, conversation_id=conversation_id)
        return conversation

    async def list_conversations(
        self,
        session: AsyncSession,
        skip: int = 0,
        limit: int = 10,
    ) -> tuple[list[ConversationModel], int]:
        """
        List conversations with pagination.

        Args:
            session: Database session.
            skip: Number of records to skip.
            limit: Maximum number of records to return.

        Returns:
            Tuple of (conversations list, total count).
        """
        # Get total count
        total_result = await session.execute(
            select(func.count(ConversationModel.id))
        )
        total = total_result.scalar() or 0

        # Get paginated results
        query = (
            select(ConversationModel)
            .options(selectinload(ConversationModel.messages))
            .order_by(ConversationModel.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await session.execute(query)
        conversations = list(result.scalars().all())

        return conversations, total

    async def add_message(
        self,
        session: AsyncSession,
        conversation_id: str,
        role: MessageRole,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> MessageModel:
        """
        Add a message to a conversation.

        Args:
            session: Database session.
            conversation_id: The conversation ID.
            role: Message role (user/assistant/system).
            content: Message content.
            metadata: Optional message metadata.

        Returns:
            Created MessageModel instance.
        """
        # Ensure conversation exists
        await self.get_or_create(session, conversation_id)

        message = MessageModel(
            id=str(uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc),
            metadata_=metadata or {},
        )

        session.add(message)
        await session.flush()

        logger.debug(f"Added {role.value} message to conversation {conversation_id}")
        return message

    async def add_exchange(
        self,
        session: AsyncSession,
        conversation_id: str,
        user_message: str,
        assistant_message: str,
        sources: list[dict[str, Any]] | None = None,
    ) -> tuple[MessageModel, MessageModel]:
        """
        Add a user/assistant message pair.

        Args:
            session: Database session.
            conversation_id: The conversation ID.
            user_message: User's message content.
            assistant_message: Assistant's response content.
            sources: Optional source documents for the response.

        Returns:
            Tuple of (user_message, assistant_message) models.
        """
        user_msg = await self.add_message(
            session, conversation_id, MessageRole.USER, user_message
        )

        assistant_metadata = {}
        if sources:
            assistant_metadata["sources"] = sources

        assistant_msg = await self.add_message(
            session,
            conversation_id,
            MessageRole.ASSISTANT,
            assistant_message,
            metadata=assistant_metadata,
        )

        return user_msg, assistant_msg

    async def get_messages(
        self,
        session: AsyncSession,
        conversation_id: str,
        limit: int | None = None,
        exclude_system: bool = False,
    ) -> list[MessageModel]:
        """
        Get messages for a conversation.

        Args:
            session: Database session.
            conversation_id: The conversation ID.
            limit: Maximum number of messages (from most recent).
            exclude_system: Whether to exclude system messages.

        Returns:
            List of MessageModel instances.
        """
        query = (
            select(MessageModel)
            .where(MessageModel.conversation_id == conversation_id)
            .order_by(MessageModel.created_at.asc())
        )

        if exclude_system:
            query = query.where(MessageModel.role != MessageRole.SYSTEM)

        result = await session.execute(query)
        messages = list(result.scalars().all())

        # Apply limit from the end (most recent)
        if limit is not None and limit > 0:
            messages = messages[-limit:]

        return messages

    async def get_langchain_history(
        self,
        session: AsyncSession,
        conversation_id: str,
        limit: int | None = None,
    ) -> list[BaseMessage]:
        """
        Get conversation history as LangChain messages.

        Args:
            session: Database session.
            conversation_id: The conversation ID.
            limit: Maximum number of messages.

        Returns:
            List of LangChain BaseMessage instances.
        """
        messages = await self.get_messages(session, conversation_id, limit=limit)

        langchain_messages: list[BaseMessage] = []
        for msg in messages:
            if msg.role == MessageRole.USER:
                langchain_messages.append(HumanMessage(content=msg.content))
            elif msg.role == MessageRole.ASSISTANT:
                langchain_messages.append(AIMessage(content=msg.content))
            elif msg.role == MessageRole.SYSTEM:
                langchain_messages.append(SystemMessage(content=msg.content))

        return langchain_messages

    async def clear_messages(
        self,
        session: AsyncSession,
        conversation_id: str,
    ) -> int:
        """
        Clear all messages from a conversation.

        Args:
            session: Database session.
            conversation_id: The conversation ID.

        Returns:
            Number of messages deleted.
        """
        result = await session.execute(
            delete(MessageModel).where(MessageModel.conversation_id == conversation_id)
        )
        deleted = result.rowcount

        logger.info(f"Cleared {deleted} messages from conversation {conversation_id}")
        return deleted

    async def delete(
        self,
        session: AsyncSession,
        conversation_id: str,
    ) -> bool:
        """
        Delete a conversation and all its messages.

        Args:
            session: Database session.
            conversation_id: The conversation ID.

        Returns:
            True if conversation was deleted, False if not found.
        """
        # Messages will be cascade deleted
        result = await session.execute(
            delete(ConversationModel).where(ConversationModel.id == conversation_id)
        )

        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Deleted conversation: {conversation_id}")

        return deleted

    async def get_statistics(
        self,
        session: AsyncSession,
    ) -> dict[str, Any]:
        """
        Get conversation statistics.

        Args:
            session: Database session.

        Returns:
            Dictionary with conversation statistics.
        """
        # Total conversations
        conv_result = await session.execute(
            select(func.count(ConversationModel.id))
        )
        total_conversations = conv_result.scalar() or 0

        # Total messages
        msg_result = await session.execute(select(func.count(MessageModel.id)))
        total_messages = msg_result.scalar() or 0

        # Messages by role
        role_counts = {}
        for role in MessageRole:
            count_result = await session.execute(
                select(func.count(MessageModel.id)).where(MessageModel.role == role)
            )
            role_counts[role.value] = count_result.scalar() or 0

        # Average messages per conversation
        avg_messages = (
            total_messages / total_conversations if total_conversations > 0 else 0
        )

        return {
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "messages_by_role": role_counts,
            "average_messages_per_conversation": round(avg_messages, 2),
        }

    def model_to_dataclass(
        self,
        model: ConversationModel,
    ) -> ConversationDataclass:
        """
        Convert a ConversationModel to a Conversation dataclass.

        Args:
            model: The ConversationModel instance.

        Returns:
            Conversation dataclass instance.
        """
        messages = [
            MessageDataclass(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                timestamp=msg.created_at,
                metadata=msg.metadata_,
            )
            for msg in model.messages
        ]

        return ConversationDataclass(
            id=model.id,
            messages=messages,
            created_at=model.created_at,
            updated_at=model.updated_at,
            metadata=model.metadata_,
        )


# Singleton instance
_conversation_repository: ConversationRepository | None = None


def get_conversation_repository() -> ConversationRepository:
    """Get or create the conversation repository instance."""
    global _conversation_repository
    if _conversation_repository is None:
        _conversation_repository = ConversationRepository()
    return _conversation_repository
