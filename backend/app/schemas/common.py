"""Common schemas used across the application."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response schema for health check endpoint."""

    status: Literal["healthy", "unhealthy"] = Field(
        description="Current health status of the API"
    )
    version: str = Field(description="API version")
    environment: str = Field(description="Current environment")
    timestamp: datetime = Field(description="Current server timestamp")


class ErrorResponse(BaseModel):
    """Standard error response schema."""

    error: str = Field(description="Error type")
    message: str = Field(description="Human-readable error message")
    details: dict[str, Any] | None = Field(
        default=None, description="Additional error details"
    )


class SuccessResponse(BaseModel):
    """Generic success response schema."""

    success: bool = True
    message: str = Field(description="Success message")


class PaginatedResponse(BaseModel):
    """Base schema for paginated responses."""

    total: int = Field(description="Total number of items")
    page: int = Field(description="Current page number")
    page_size: int = Field(description="Items per page")
    pages: int = Field(description="Total number of pages")
