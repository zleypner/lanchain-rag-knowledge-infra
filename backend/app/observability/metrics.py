"""Prometheus metrics for RAG application."""

from typing import Any

from prometheus_client import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    Summary,
    generate_latest,
)

from app.core.config import settings


class MetricsService:
    """Service for tracking application metrics."""

    def __init__(self) -> None:
        """Initialize Prometheus metrics."""

        # HTTP Request Metrics
        self.http_requests_total = Counter(
            "http_requests_total",
            "Total HTTP requests",
            ["method", "endpoint", "status"],
        )

        self.http_request_duration_seconds = Histogram(
            "http_request_duration_seconds",
            "HTTP request duration in seconds",
            ["method", "endpoint"],
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
        )

        # RAG Pipeline Metrics
        self.rag_queries_total = Counter(
            "rag_queries_total",
            "Total RAG queries processed",
            ["status"],
        )

        self.rag_query_duration_seconds = Histogram(
            "rag_query_duration_seconds",
            "RAG query duration in seconds",
            buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
        )

        self.rag_retrieval_duration_seconds = Histogram(
            "rag_retrieval_duration_seconds",
            "Document retrieval duration in seconds",
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0),
        )

        self.rag_generation_duration_seconds = Histogram(
            "rag_generation_duration_seconds",
            "LLM generation duration in seconds",
            buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 30.0),
        )

        self.rag_documents_retrieved = Histogram(
            "rag_documents_retrieved",
            "Number of documents retrieved per query",
            buckets=(0, 1, 2, 4, 8, 16, 32),
        )

        # Embedding Metrics
        self.embeddings_created_total = Counter(
            "embeddings_created_total",
            "Total embeddings created",
        )

        self.embedding_duration_seconds = Histogram(
            "embedding_duration_seconds",
            "Embedding creation duration in seconds",
            buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.0),
        )

        # Document Processing Metrics
        self.documents_uploaded_total = Counter(
            "documents_uploaded_total",
            "Total documents uploaded",
            ["status"],
        )

        self.document_processing_duration_seconds = Histogram(
            "document_processing_duration_seconds",
            "Document processing duration in seconds",
            buckets=(0.5, 1.0, 5.0, 10.0, 30.0, 60.0),
        )

        self.document_chunks_created = Histogram(
            "document_chunks_created",
            "Number of chunks created per document",
            buckets=(1, 5, 10, 25, 50, 100, 200),
        )

        # Vector Store Metrics
        self.vector_store_operations_total = Counter(
            "vector_store_operations_total",
            "Total vector store operations",
            ["operation", "status"],
        )

        self.vector_store_size = Gauge(
            "vector_store_size",
            "Total number of vectors in the store",
        )

        # LLM Metrics
        self.llm_requests_total = Counter(
            "llm_requests_total",
            "Total LLM requests",
            ["provider", "model"],
        )

        self.llm_tokens_total = Counter(
            "llm_tokens_total",
            "Total tokens consumed",
            ["provider", "model", "type"],  # type: prompt or completion
        )

        self.llm_request_duration_seconds = Histogram(
            "llm_request_duration_seconds",
            "LLM request duration in seconds",
            ["provider", "model"],
            buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 20.0),
        )

        # Cache Metrics (if caching is implemented)
        self.cache_hits_total = Counter(
            "cache_hits_total",
            "Total cache hits",
            ["cache_type"],
        )

        self.cache_misses_total = Counter(
            "cache_misses_total",
            "Total cache misses",
            ["cache_type"],
        )

        # System Metrics
        self.active_conversations = Gauge(
            "active_conversations",
            "Number of active conversations",
        )

        self.error_total = Counter(
            "error_total",
            "Total errors by type",
            ["error_type", "component"],
        )

    def record_http_request(
        self,
        method: str,
        endpoint: str,
        status: int,
        duration: float,
    ) -> None:
        """Record HTTP request metrics."""
        self.http_requests_total.labels(
            method=method,
            endpoint=endpoint,
            status=status,
        ).inc()
        self.http_request_duration_seconds.labels(
            method=method,
            endpoint=endpoint,
        ).observe(duration)

    def record_rag_query(
        self,
        duration: float,
        status: str = "success",
        retrieval_time: float | None = None,
        generation_time: float | None = None,
        documents_retrieved: int | None = None,
    ) -> None:
        """Record RAG query metrics."""
        self.rag_queries_total.labels(status=status).inc()
        self.rag_query_duration_seconds.observe(duration)

        if retrieval_time is not None:
            self.rag_retrieval_duration_seconds.observe(retrieval_time)

        if generation_time is not None:
            self.rag_generation_duration_seconds.observe(generation_time)

        if documents_retrieved is not None:
            self.rag_documents_retrieved.observe(documents_retrieved)

    def record_embedding(self, duration: float, count: int = 1) -> None:
        """Record embedding creation metrics."""
        self.embeddings_created_total.inc(count)
        self.embedding_duration_seconds.observe(duration)

    def record_document_upload(
        self,
        status: str,
        processing_time: float | None = None,
        chunks_created: int | None = None,
    ) -> None:
        """Record document upload metrics."""
        self.documents_uploaded_total.labels(status=status).inc()

        if processing_time is not None:
            self.document_processing_duration_seconds.observe(processing_time)

        if chunks_created is not None:
            self.document_chunks_created.observe(chunks_created)

    def record_vector_store_operation(
        self,
        operation: str,
        status: str = "success",
    ) -> None:
        """Record vector store operation."""
        self.vector_store_operations_total.labels(
            operation=operation,
            status=status,
        ).inc()

    def update_vector_store_size(self, size: int) -> None:
        """Update vector store size gauge."""
        self.vector_store_size.set(size)

    def record_llm_request(
        self,
        provider: str,
        model: str,
        duration: float,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
    ) -> None:
        """Record LLM request metrics."""
        self.llm_requests_total.labels(provider=provider, model=model).inc()
        self.llm_request_duration_seconds.labels(
            provider=provider,
            model=model,
        ).observe(duration)

        if prompt_tokens is not None:
            self.llm_tokens_total.labels(
                provider=provider,
                model=model,
                type="prompt",
            ).inc(prompt_tokens)

        if completion_tokens is not None:
            self.llm_tokens_total.labels(
                provider=provider,
                model=model,
                type="completion",
            ).inc(completion_tokens)

    def record_cache_hit(self, cache_type: str = "default") -> None:
        """Record cache hit."""
        self.cache_hits_total.labels(cache_type=cache_type).inc()

    def record_cache_miss(self, cache_type: str = "default") -> None:
        """Record cache miss."""
        self.cache_misses_total.labels(cache_type=cache_type).inc()

    def update_active_conversations(self, count: int) -> None:
        """Update active conversations gauge."""
        self.active_conversations.set(count)

    def record_error(self, error_type: str, component: str) -> None:
        """Record error occurrence."""
        self.error_total.labels(error_type=error_type, component=component).inc()

    def get_metrics_text(self) -> bytes:
        """
        Get all metrics in Prometheus text format.

        Returns:
            Metrics data in Prometheus exposition format.
        """
        return generate_latest(REGISTRY)

    def get_metrics_summary(self) -> dict[str, Any]:
        """
        Get a summary of key metrics.

        Returns:
            Dictionary with current metric values.
        """
        return {
            "rag_queries_total": self._get_counter_value(self.rag_queries_total),
            "documents_uploaded_total": self._get_counter_value(
                self.documents_uploaded_total
            ),
            "vector_store_size": self._get_gauge_value(self.vector_store_size),
            "active_conversations": self._get_gauge_value(self.active_conversations),
            "llm_requests_total": self._get_counter_value(self.llm_requests_total),
            "embeddings_created_total": self._get_counter_value(
                self.embeddings_created_total
            ),
        }

    def _get_counter_value(self, counter: Counter) -> float:
        """Get total value from a counter metric."""
        try:
            return sum(sample.value for sample in counter.collect()[0].samples)
        except (IndexError, AttributeError):
            return 0.0

    def _get_gauge_value(self, gauge: Gauge) -> float:
        """Get current value from a gauge metric."""
        try:
            return gauge.collect()[0].samples[0].value
        except (IndexError, AttributeError):
            return 0.0


# Singleton instance
_metrics_service: MetricsService | None = None


def get_metrics() -> MetricsService:
    """Get or create the metrics service instance."""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService()
    return _metrics_service
