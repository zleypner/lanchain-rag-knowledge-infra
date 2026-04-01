"""API routes module."""

from fastapi import APIRouter

from app.api.routes import documents, health

# Main API router
api_router = APIRouter()

# Include route modules
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])

# Future routes will be added here:
# api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
