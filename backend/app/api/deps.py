"""API dependencies for dependency injection."""

from typing import Annotated

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.services.document_service import DocumentService, get_document_service
from app.services.ingestion_service import IngestionService, get_ingestion_service
from app.services.rag_chain import RAGChain, get_rag_chain


# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]

# Document service dependency
DocumentServiceDep = Annotated[DocumentService, Depends(get_document_service)]

# Ingestion service dependency
IngestionServiceDep = Annotated[IngestionService, Depends(get_ingestion_service)]

# RAG chain dependency
RAGChainDep = Annotated[RAGChain, Depends(get_rag_chain)]
