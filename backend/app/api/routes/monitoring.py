"""Monitoring and observability endpoints."""

from fastapi import APIRouter, Response

from app.observability.metrics import get_metrics

router = APIRouter()


@router.get("/metrics")
async def prometheus_metrics() -> Response:
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus exposition format.
    This endpoint should be scraped by Prometheus or compatible monitoring systems.

    Returns:
        Response with metrics in text format.
    """
    metrics_service = get_metrics()
    metrics_data = metrics_service.get_metrics_text()

    return Response(
        content=metrics_data,
        media_type="text/plain; version=0.0.4",
    )


@router.get("/metrics/summary")
async def metrics_summary() -> dict:
    """
    Get a summary of key metrics in JSON format.

    Useful for quick checks and dashboards that don't use Prometheus.

    Returns:
        Dictionary with key metric values.
    """
    metrics_service = get_metrics()
    return metrics_service.get_metrics_summary()


@router.get("/health/detailed")
async def detailed_health() -> dict:
    """
    Detailed health check with metrics summary.

    Returns:
        Comprehensive health status with system metrics.
    """
    metrics_service = get_metrics()

    return {
        "status": "healthy",
        "metrics": metrics_service.get_metrics_summary(),
    }
