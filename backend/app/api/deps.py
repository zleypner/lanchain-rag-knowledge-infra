"""API dependencies for dependency injection."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_async_session
from app.repositories.conversation_repository import (
    ConversationRepository,
    get_conversation_repository,
)
from app.repositories.document_repository import (
    DocumentRepository,
    get_document_repository,
)
from app.services.document_service import DocumentService, get_document_service
from app.services.ingestion_service import IngestionService, get_ingestion_service
from app.services.pgvector_store_service import (
    PGVectorStoreService,
    get_pgvector_store_service,
)
from app.services.rag_chain import RAGChain, get_rag_chain


# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Database session dependency
AsyncSessionDep = Annotated[AsyncSession, Depends(get_async_session)]

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
