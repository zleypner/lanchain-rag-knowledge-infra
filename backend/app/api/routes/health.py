"""Health check endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from app import __version__
from app.api.deps import SessionDep, SettingsDep
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
async def readiness_check(
    session: SessionDep,
    settings: SettingsDep,
) -> dict[str, str | dict[str, str]]:
    """
    Readiness check for container orchestration.

    Checks if the application is ready to serve traffic by verifying:
    - Database connectivity
    - Vector store availability (if using pgvector)
    """
    checks: dict[str, str] = {}

    # Check database connection
    try:
        await session.execute(text("SELECT 1"))
        checks["database"] = "connected"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})

    # Check pgvector extension if using pgvector
    if settings.vector_store_type == "pgvector":
        try:
            result = await session.execute(
                text("SELECT extname FROM pg_extension WHERE extname = 'vector'")
            )
            if result.fetchone():
                checks["pgvector"] = "enabled"
            else:
                checks["pgvector"] = "not_installed"
        except Exception as e:
            checks["pgvector"] = f"error: {str(e)}"

    return {"status": "ready", "checks": checks}


@router.get("/live")
async def liveness_check() -> dict[str, str]:
    """
    Liveness check for container orchestration.

    Simple check that the process is alive.
    """
    return {"status": "alive"}
