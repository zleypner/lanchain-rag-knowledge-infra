"""OpenTelemetry distributed tracing configuration."""

import functools
import time
from contextlib import contextmanager
from typing import Any, Callable, Generator, ParamSpec, TypeVar

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.trace import Status, StatusCode

from app.core.config import settings

# Type variables for decorator
P = ParamSpec("P")
T = TypeVar("T")


def setup_tracing() -> None:
    """Configure OpenTelemetry tracing."""

    # Create resource with service name
    resource = Resource(attributes={
        SERVICE_NAME: "rag-api",
        "environment": settings.environment,
        "version": "1.0.0",
    })

    # Create tracer provider
    provider = TracerProvider(resource=resource)

    # Add exporters based on environment
    if settings.is_development:
        # Console exporter for development
        console_exporter = ConsoleSpanExporter()
        provider.add_span_processor(BatchSpanProcessor(console_exporter))
    else:
        # OTLP exporter for production (to Jaeger, Grafana Tempo, etc.)
        # Configure OTLP_ENDPOINT via environment variable if needed
        try:
            otlp_exporter = OTLPSpanExporter(
                # endpoint="http://localhost:4317",  # Default OTLP gRPC endpoint
                # insecure=True,
            )
            provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        except Exception:
            # Fallback to console if OTLP is not available
            console_exporter = ConsoleSpanExporter()
            provider.add_span_processor(BatchSpanProcessor(console_exporter))

    # Set as global tracer provider
    trace.set_tracer_provider(provider)


def get_tracer(name: str = "rag-api") -> trace.Tracer:
    """
    Get a tracer instance.

    Args:
        name: Tracer name (typically module or component name).

    Returns:
        OpenTelemetry tracer.
    """
    return trace.get_tracer(name)


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    tracer: trace.Tracer | None = None,
) -> Generator[trace.Span, None, None]:
    """
    Context manager for creating a traced span.

    Args:
        name: Span name.
        attributes: Optional attributes to add to the span.
        tracer: Optional tracer instance (creates one if not provided).

    Yields:
        The created span.

    Example:
        >>> with trace_span("document_processing", {"doc_id": 123}):
        ...     process_document()
    """
    if tracer is None:
        tracer = get_tracer()

    with tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)

        try:
            yield span
        except Exception as e:
            span.set_status(Status(StatusCode.ERROR, str(e)))
            span.record_exception(e)
            raise


def trace_function(
    name: str | None = None,
    attributes: dict[str, Any] | None = None,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator to automatically trace a function.

    Args:
        name: Optional span name (defaults to function name).
        attributes: Optional attributes to add to the span.

    Returns:
        Decorated function.

    Example:
        >>> @trace_function(attributes={"component": "rag"})
        ... def process_query(query: str) -> str:
        ...     return generate_answer(query)
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        span_name = name or func.__name__
        tracer = get_tracer()

        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            with tracer.start_as_current_span(span_name) as span:
                # Add attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                # Add function info
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                try:
                    result = func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            with tracer.start_as_current_span(span_name) as span:
                # Add attributes
                if attributes:
                    for key, value in attributes.items():
                        span.set_attribute(key, value)

                # Add function info
                span.set_attribute("function.name", func.__name__)
                span.set_attribute("function.module", func.__module__)

                try:
                    result = await func(*args, **kwargs)
                    span.set_status(Status(StatusCode.OK))
                    return result
                except Exception as e:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    span.record_exception(e)
                    raise

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


class RAGTracer:
    """High-level tracer for RAG pipeline operations."""

    def __init__(self) -> None:
        """Initialize RAG tracer."""
        self.tracer = get_tracer("rag-pipeline")

    @contextmanager
    def trace_query(
        self,
        query: str,
        session_id: str | None = None,
    ) -> Generator[trace.Span, None, None]:
        """
        Trace a complete RAG query.

        Args:
            query: The user's query.
            session_id: Optional session ID.

        Yields:
            The query span.
        """
        with self.tracer.start_as_current_span("rag.query") as span:
            span.set_attribute("query.text", query[:100])  # Truncate for privacy
            span.set_attribute("query.length", len(query))
            if session_id:
                span.set_attribute("session.id", session_id)

            start_time = time.time()
            try:
                yield span
                duration = time.time() - start_time
                span.set_attribute("query.duration_ms", duration * 1000)
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    @contextmanager
    def trace_retrieval(
        self,
        k: int | None = None,
    ) -> Generator[trace.Span, None, None]:
        """
        Trace document retrieval phase.

        Args:
            k: Number of documents to retrieve.

        Yields:
            The retrieval span.
        """
        with self.tracer.start_as_current_span("rag.retrieval") as span:
            if k:
                span.set_attribute("retrieval.k", k)

            start_time = time.time()
            try:
                yield span
                duration = time.time() - start_time
                span.set_attribute("retrieval.duration_ms", duration * 1000)
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    @contextmanager
    def trace_generation(
        self,
        model: str | None = None,
        provider: str | None = None,
    ) -> Generator[trace.Span, None, None]:
        """
        Trace LLM generation phase.

        Args:
            model: LLM model name.
            provider: LLM provider name.

        Yields:
            The generation span.
        """
        with self.tracer.start_as_current_span("rag.generation") as span:
            if model:
                span.set_attribute("llm.model", model)
            if provider:
                span.set_attribute("llm.provider", provider)

            start_time = time.time()
            try:
                yield span
                duration = time.time() - start_time
                span.set_attribute("generation.duration_ms", duration * 1000)
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    @contextmanager
    def trace_embedding(
        self,
        text_length: int | None = None,
    ) -> Generator[trace.Span, None, None]:
        """
        Trace embedding creation.

        Args:
            text_length: Length of text being embedded.

        Yields:
            The embedding span.
        """
        with self.tracer.start_as_current_span("rag.embedding") as span:
            if text_length:
                span.set_attribute("embedding.text_length", text_length)

            start_time = time.time()
            try:
                yield span
                duration = time.time() - start_time
                span.set_attribute("embedding.duration_ms", duration * 1000)
                span.set_status(Status(StatusCode.OK))
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise


# Singleton instance
_rag_tracer: RAGTracer | None = None


def get_rag_tracer() -> RAGTracer:
    """Get or create the RAG tracer instance."""
    global _rag_tracer
    if _rag_tracer is None:
        _rag_tracer = RAGTracer()
    return _rag_tracer
