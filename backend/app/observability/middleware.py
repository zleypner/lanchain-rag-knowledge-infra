"""Middleware for observability: logging, metrics, and tracing."""

import time
import uuid
from contextvars import ContextVar
from typing import Callable

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.observability.metrics import get_metrics
from app.observability.tracer import get_tracer

# Context variable for request ID
request_id_var: ContextVar[str] = ContextVar("request_id", default="")

# Logger
logger = structlog.get_logger(__name__)


class ObservabilityMiddleware(BaseHTTPMiddleware):
    """Middleware that adds logging, metrics, and tracing to all requests."""

    def __init__(self, app: ASGIApp) -> None:
        """Initialize the middleware."""
        super().__init__(app)
        self.metrics = get_metrics()
        self.tracer = get_tracer("http-middleware")

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response],
    ) -> Response:
        """Process the request with observability."""

        # Generate request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(request_id)

        # Extract request info
        method = request.method
        path = request.url.path
        client_host = request.client.host if request.client else "unknown"

        # Start tracing
        with self.tracer.start_as_current_span(
            f"{method} {path}",
            attributes={
                "http.method": method,
                "http.path": path,
                "http.client_host": client_host,
                "http.request_id": request_id,
            },
        ) as span:
            # Log request start
            logger.info(
                "request_started",
                method=method,
                path=path,
                request_id=request_id,
                client_host=client_host,
            )

            # Record start time
            start_time = time.time()

            try:
                # Process request
                response = await call_next(request)

                # Calculate duration
                duration = time.time() - start_time

                # Add response info to span
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("http.duration_ms", duration * 1000)

                # Record metrics
                self.metrics.record_http_request(
                    method=method,
                    endpoint=self._normalize_endpoint(path),
                    status=response.status_code,
                    duration=duration,
                )

                # Log request completion
                logger.info(
                    "request_completed",
                    method=method,
                    path=path,
                    request_id=request_id,
                    status_code=response.status_code,
                    duration_ms=round(duration * 1000, 2),
                )

                # Add request ID to response headers
                response.headers["X-Request-ID"] = request_id

                return response

            except Exception as e:
                # Calculate duration even for errors
                duration = time.time() - start_time

                # Record error metrics
                self.metrics.record_http_request(
                    method=method,
                    endpoint=self._normalize_endpoint(path),
                    status=500,
                    duration=duration,
                )

                self.metrics.record_error(
                    error_type=type(e).__name__,
                    component="http_middleware",
                )

                # Log error
                logger.error(
                    "request_failed",
                    method=method,
                    path=path,
                    request_id=request_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    duration_ms=round(duration * 1000, 2),
                    exc_info=True,
                )

                # Re-raise exception
                raise

    def _normalize_endpoint(self, path: str) -> str:
        """
        Normalize endpoint path for metrics to avoid high cardinality.

        Args:
            path: Request path.

        Returns:
            Normalized path with IDs replaced.
        """
        # Replace UUIDs and numeric IDs with placeholders
        parts = path.split("/")
        normalized = []

        for part in parts:
            # Check if part looks like a UUID
            if len(part) == 36 and part.count("-") == 4:
                normalized.append("{id}")
            # Check if part is numeric
            elif part.isdigit():
                normalized.append("{id}")
            else:
                normalized.append(part)

        return "/".join(normalized)


def get_request_id() -> str:
    """
    Get the current request ID from context.

    Returns:
        Request ID or empty string if not set.
    """
    return request_id_var.get()
