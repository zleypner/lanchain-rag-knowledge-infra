# Observability Guide

This document explains the comprehensive observability infrastructure implemented in the RAG API, including structured logging, metrics collection, distributed tracing, and monitoring dashboards.

## Table of Contents

- [Overview](#overview)
- [Structured Logging](#structured-logging)
- [Metrics Collection](#metrics-collection)
- [Distributed Tracing](#distributed-tracing)
- [Monitoring Dashboard](#monitoring-dashboard)
- [Configuration](#configuration)
- [Best Practices](#best-practices)

---

## Overview

The RAG API implements a complete observability stack with three pillars:

1. **Structured Logging** - Contextual, machine-readable logs using structlog
2. **Metrics** - Prometheus metrics for performance and usage tracking
3. **Tracing** - OpenTelemetry distributed tracing for request flows

### Architecture

```
┌─────────────┐
│  RAG API    │
│             │
│  ┌───────┐  │     ┌─────────────┐
│  │Logger │──┼────>│  Log Output │
│  └───────┘  │     └─────────────┘
│             │
│  ┌───────┐  │     ┌─────────────┐     ┌──────────┐
│  │Metrics│──┼────>│ Prometheus  │────>│ Grafana  │
│  └───────┘  │     └─────────────┘     └──────────┘
│             │
│  ┌───────┐  │     ┌─────────────┐
│  │Tracer │──┼────>│   OTLP      │
│  └───────┘  │     │  Collector  │
└─────────────┘     └─────────────┘
```

---

## Structured Logging

### Features

- **JSON output** in production for log aggregation
- **Human-readable** colored output in development
- **Request ID** tracking across all logs
- **Context variables** for enriched logging
- **Application context** (app name, environment) automatically added

### Usage

#### Basic Logging

```python
from app.observability import get_logger

logger = get_logger(__name__)

# Simple log
logger.info("user_login", user_id=123, method="oauth")

# With error tracking
try:
    process_document()
except Exception as e:
    logger.error("document_processing_failed",
                 error=str(e),
                 document_id=doc_id,
                 exc_info=True)
```

#### Using Log Context

```python
from app.observability.logger import log_context

# Add temporary context
with log_context(user_id=123, session_id="abc"):
    logger.info("processing_request")  # Automatically includes user_id and session_id
    do_work()
```

#### Request ID Tracking

Request IDs are automatically:
- Generated for each HTTP request
- Added to all logs within that request
- Returned in `X-Request-ID` response header
- Available via `get_request_id()` function

### Log Format

**Development:**
```
2024-04-05 10:23:45 [info     ] user_login                     app=rag-api environment=development user_id=123 method=oauth
```

**Production (JSON):**
```json
{
  "event": "user_login",
  "timestamp": "2024-04-05T10:23:45.123456Z",
  "level": "info",
  "logger": "app.services.auth",
  "app": "rag-api",
  "environment": "production",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": 123,
  "method": "oauth"
}
```

---

## Metrics Collection

### Available Metrics

#### HTTP Metrics
- `http_requests_total` - Total HTTP requests by method, endpoint, status
- `http_request_duration_seconds` - Request latency histogram

#### RAG Pipeline Metrics
- `rag_queries_total` - Total RAG queries by status
- `rag_query_duration_seconds` - End-to-end query latency
- `rag_retrieval_duration_seconds` - Document retrieval latency
- `rag_generation_duration_seconds` - LLM generation latency
- `rag_documents_retrieved` - Number of documents per query

#### Document Processing Metrics
- `documents_uploaded_total` - Total documents uploaded
- `document_processing_duration_seconds` - Processing time
- `document_chunks_created` - Chunks created per document

#### Vector Store Metrics
- `vector_store_operations_total` - Vector store operations
- `vector_store_size` - Total vectors in the store

#### LLM Metrics
- `llm_requests_total` - LLM requests by provider and model
- `llm_tokens_total` - Token consumption (prompt/completion)
- `llm_request_duration_seconds` - LLM API latency

#### System Metrics
- `active_conversations` - Active conversation sessions
- `error_total` - Errors by type and component
- `embeddings_created_total` - Total embeddings created
- `embedding_duration_seconds` - Embedding creation time

### Recording Metrics

```python
from app.observability import get_metrics

metrics = get_metrics()

# Record RAG query
metrics.record_rag_query(
    duration=2.5,
    status="success",
    retrieval_time=0.3,
    generation_time=2.0,
    documents_retrieved=4
)

# Record LLM request
metrics.record_llm_request(
    provider="openai",
    model="gpt-4o-mini",
    duration=1.8,
    prompt_tokens=150,
    completion_tokens=200
)

# Record error
metrics.record_error(
    error_type="ValidationError",
    component="document_service"
)
```

### Accessing Metrics

#### Prometheus Format
```bash
curl http://localhost:8000/api/v1/monitoring/metrics
```

#### JSON Summary
```bash
curl http://localhost:8000/api/v1/monitoring/metrics/summary
```

Response:
```json
{
  "rag_queries_total": 1234,
  "documents_uploaded_total": 56,
  "vector_store_size": 450,
  "active_conversations": 12,
  "llm_requests_total": 980,
  "embeddings_created_total": 2340
}
```

---

## Distributed Tracing

### Features

- **OpenTelemetry** standard traces
- **Automatic instrumentation** for HTTP requests
- **Manual spans** for RAG pipeline stages
- **Context propagation** across services
- **Error tracking** with stack traces

### RAG Pipeline Tracing

Each RAG query automatically creates a trace with nested spans:

```
rag.query (2.5s)
├── rag.retrieval (0.3s)
│   ├── vector_search (0.2s)
│   └── format_context (0.1s)
└── rag.generation (2.0s)
    ├── prepare_prompt (0.1s)
    └── llm_request (1.9s)
```

### Usage

#### Automatic Tracing (RAG Chain)

The RAG chain automatically traces all operations:

```python
# Automatically traced
rag_chain = get_rag_chain()
response = await rag_chain.query("What is the capital of France?")
```

#### Manual Tracing

```python
from app.observability import trace_span, get_tracer

# Using context manager
with trace_span("document_processing", {"doc_id": 123}):
    process_document()

# Using decorator
from app.observability.tracer import trace_function

@trace_function(attributes={"component": "parser"})
async def parse_pdf(file_path: str) -> str:
    return extract_text(file_path)
```

#### RAG Tracer

High-level tracer for RAG operations:

```python
from app.observability.tracer import get_rag_tracer

tracer = get_rag_tracer()

with tracer.trace_query(query="What is AI?", session_id="abc") as span:
    # Retrieval phase
    with tracer.trace_retrieval(k=4) as retrieval_span:
        documents = retrieve_documents()
        retrieval_span.set_attribute("documents_found", len(documents))

    # Generation phase
    with tracer.trace_generation(model="gpt-4", provider="openai") as gen_span:
        answer = generate_answer()
        gen_span.set_attribute("answer_length", len(answer))
```

### Viewing Traces

**Development:** Traces are output to console

**Production:** Export to OTLP collector (Jaeger, Grafana Tempo, etc.)

Configure via environment:
```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
```

---

## Monitoring Dashboard

### Starting the Stack

```bash
# Start with monitoring profile
docker-compose --profile monitoring up -d

# Access services:
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3001 (admin/admin)
```

### Grafana Dashboard

The pre-configured dashboard includes:

#### Overview Panels
- HTTP request rate and latency
- RAG query rate and status
- Active conversations

#### Performance Metrics
- RAG query latency percentiles (p50, p95, p99)
- Pipeline stage latencies (retrieval vs generation)
- Average documents retrieved

#### Resource Usage
- Vector store size
- LLM token consumption rate
- Document upload rate

#### Error Tracking
- Error rate by type and component
- Failed request trends

### Dashboard Location

Pre-configured dashboard: `/docker/grafana/dashboards/rag-api-dashboard.json`

Access in Grafana at: **Dashboards → RAG API Monitoring Dashboard**

---

## Configuration

### Environment Variables

```bash
# Logging
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
ENVIRONMENT=production            # development, staging, production

# Tracing
OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
OTEL_TRACES_EXPORTER=otlp        # otlp, console, none

# Monitoring
PROMETHEUS_PORT=9090
GRAFANA_PORT=3001
GRAFANA_USER=admin
GRAFANA_PASSWORD=admin
```

### Prometheus Configuration

Edit `/docker/prometheus.yml`:

```yaml
scrape_configs:
  - job_name: 'rag-api'
    metrics_path: '/api/v1/monitoring/metrics'
    static_configs:
      - targets: ['backend:8000']
    scrape_interval: 10s
```

### Disabling Observability

```python
# In config.py
LOG_LEVEL = "ERROR"              # Reduce log verbosity
OTEL_TRACES_EXPORTER = "none"    # Disable tracing
```

---

## Best Practices

### Logging

✅ **DO:**
- Use structured logging with key-value pairs
- Include relevant context (IDs, timestamps)
- Use appropriate log levels
- Log at service boundaries

❌ **DON'T:**
- Log sensitive data (passwords, tokens, PII)
- Use string formatting in log messages
- Log inside tight loops
- Mix print() with structured logs

```python
# Good
logger.info("document_uploaded",
            document_id=doc.id,
            size_bytes=doc.size,
            user_id=user.id)

# Bad
logger.info(f"User {user.email} uploaded {doc.filename}")  # PII leaked
print("Processing...")  # Use logger instead
```

### Metrics

✅ **DO:**
- Record metrics at the end of operations
- Use histograms for latency measurements
- Include status labels (success/error)
- Keep cardinality low

❌ **DON'T:**
- Create metrics with high-cardinality labels (user IDs, UUIDs)
- Record metrics in tight loops
- Use metrics for debugging (use logs)

```python
# Good
metrics.record_rag_query(duration=2.5, status="success")

# Bad
metrics.record_rag_query(duration=2.5, user_id=123)  # High cardinality!
```

### Tracing

✅ **DO:**
- Trace significant operations
- Add relevant attributes
- Propagate context across services
- Record exceptions

❌ **DON'T:**
- Trace trivial operations (getters/setters)
- Add too many spans (keep hierarchy meaningful)
- Store sensitive data in span attributes

```python
# Good
with trace_span("document_chunking", {"doc_id": 123, "chunks": 10}):
    chunks = split_document()

# Bad
with trace_span("get_title"):  # Too trivial
    return doc.title
```

### Performance Impact

Observability overhead is minimal:
- **Logging:** ~0.1-1ms per log
- **Metrics:** ~0.01-0.1ms per metric
- **Tracing:** ~0.1-0.5ms per span

Total overhead: <1% for typical workloads

---

## Troubleshooting

### No Metrics in Prometheus

1. Check Prometheus scrape targets: http://localhost:9090/targets
2. Verify backend metrics endpoint: `curl http://localhost:8000/api/v1/monitoring/metrics`
3. Check docker network connectivity

### Logs Not Structured in Production

Ensure `ENVIRONMENT=production` is set. In development, logs are human-readable by design.

### Traces Not Appearing

1. Verify OTLP exporter is configured
2. Check trace collector is running
3. In development, traces output to console

### High Memory Usage

If metrics cause memory issues:
- Reduce scrape frequency in prometheus.yml
- Lower histogram bucket counts in metrics.py
- Archive old Prometheus data

---

## Example Queries

### Prometheus Queries

```promql
# Request rate
rate(http_requests_total[5m])

# P95 latency
histogram_quantile(0.95, rate(rag_query_duration_seconds_bucket[5m]))

# Error rate
rate(error_total[5m])

# Token consumption per minute
rate(llm_tokens_total[1m]) * 60
```

### Grafana Alerts

Set up alerts for:
- High error rate: `rate(error_total[5m]) > 0.1`
- Slow queries: `histogram_quantile(0.95, rate(rag_query_duration_seconds_bucket[5m])) > 5`
- Low vector store size: `vector_store_size < 100`

---

## Additional Resources

- [Structured Logging Guide](https://www.structlog.org/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [Grafana Dashboard Guide](https://grafana.com/docs/grafana/latest/dashboards/)

---

## Summary

The observability stack provides:

✅ Complete visibility into RAG pipeline performance
✅ Structured, searchable logs with request correlation
✅ Real-time metrics and alerting via Prometheus/Grafana
✅ Distributed tracing for debugging complex flows
✅ Production-ready monitoring with minimal overhead

For questions or issues, refer to the main [README.md](../README.md) or open an issue.
