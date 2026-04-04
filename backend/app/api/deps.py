"""API dependencies for dependency injection."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.models import UserModel
from app.db.session import get_async_session
from app.repositories.conversation_repository import (
    ConversationRepository,
    get_conversation_repository,
)
from app.repositories.document_repository import (
    DocumentRepository,
    get_document_repository,
)
from app.services.auth_service import decode_token, get_user_by_id
from app.services.document_service import DocumentService, get_document_service
from app.services.ingestion_service import IngestionService, get_ingestion_service
from app.services.pgvector_store_service import (
    PGVectorStoreService,
    get_pgvector_store_service,
)
from app.services.rag_chain import RAGChain, get_rag_chain


# Security scheme
security = HTTPBearer(auto_error=False)

# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Database session dependency
AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]
SessionDep = AsyncSessionDep  # Alias for consistency


async def get_current_user(
    session: AsyncSessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> UserModel:
    """Get current authenticated user from JWT token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = decode_token(credentials.credentials)
    if not token_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await get_user_by_id(session, token_data.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


async def get_current_user_optional(
    session: AsyncSessionDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> UserModel | None:
    """Get current user if authenticated, otherwise return None."""
    if not credentials:
        return None

    token_data = decode_token(credentials.credentials)
    if not token_data:
        return None

    user = await get_user_by_id(session, token_data.sub)
    if not user or not user.is_active:
        return None

    return user


# Current user dependencies
CurrentUserDep = Annotated[UserModel, Depends(get_current_user)]
CurrentUserOptionalDep = Annotated[UserModel | None, Depends(get_current_user_optional)]

# Repository dependencies
DocumentRepositoryDep = Annotated[DocumentRepository, Depends(get_document_repository)]
ConversationRepositoryDep = Annotated[
    ConversationRepository, Depends(get_conversation_repository)
]

# PGVector store dependency
PGVectorStoreDep = Annotated[PGVectorStoreService, Depends(get_pgvector_store_service)]

# Document service dependency
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]

# Ingestion service dependency
IngestionServiceDep = Annotated[IngestionService, Depends(get_ingestion_service)]

# RAG chain dependency
RAGChainDep = Annotated[RAGChain, Depends(get_rag_chain)]
