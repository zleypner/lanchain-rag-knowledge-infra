"""Health check endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter

from app import __version__
from app.api.deps import SettingsDep
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("", response_model=HealthResponse)
async def health_check(settings: SettingsDep) -> HealthResponse:
    """
    Health check endpoint.

    Returns the current status of the API including version and environment.
    """
    return HealthResponse(
        status="healthy",
        version=__version__,
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc),
    )


@router.get("/ready")
async def readiness_check() -> dict[str, str]:
    """
    Readiness check for container orchestration.

    Checks if the application is ready to serve traffic.
    Future: Add database and vector store connectivity checks.
    """
    # TODO: Add checks for:
    # - Database connection
    # - Vector store connection
    # - LLM API availability
    return {"status": "ready"}


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """
    Liveness check for container orchestration.

    Simple check that the process is alive.
    """
    return {"status": "alive"}
