# LangChain RAG Knowledge Infrastructure

A production-ready Retrieval-Augmented Generation (RAG) system built with LangChain, enabling intelligent querying over unstructured documents.

## Overview

This system allows you to:
- **Ingest documents** (PDF, TXT, MD, DOCX) and automatically process them
- **Query your knowledge base** using natural language
- **Get accurate answers** with source attribution
- **Maintain conversations** with context awareness

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    Frontend     │────▶│   FastAPI       │────▶│   LangChain     │
│   (Next.js)     │     │   Backend       │     │   RAG Pipeline  │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                        ┌───────────────────────────────┼───────────┐
                        ▼                               ▼           ▼
                 ┌─────────────┐              ┌─────────────┐ ┌─────────┐
                 │  PGVector   │              │   OpenAI    │ │  Ollama │
                 │  (Vectors)  │              │   (LLM)     │ │  (Local)│
                 └─────────────┘              └─────────────┘ └─────────┘
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11+, FastAPI |
| RAG Framework | LangChain |
| Vector Store | PGVector (prod), FAISS (dev) |
| LLM | OpenAI API / Ollama |
| Frontend | Next.js 16, TypeScript, Tailwind CSS |
| Database | PostgreSQL with pgvector |
| Containerization | Docker, Docker Compose |

## Quick Start

### Option 1: Docker (Recommended)

The fastest way to get started is using Docker Compose:

```bash
# Clone the repository
git clone https://github.com/yourusername/lanchain-rag-knowledge-infra.git
cd lanchain-rag-knowledge-infra

# Copy environment file and configure
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY

# Start all services
docker compose up --build

# Services will be available at:
# - Frontend: http://localhost:3000
# - Backend API: http://localhost:8000
# - API Docs: http://localhost:8000/docs (dev mode only)
```

**Optional: Enable PgAdmin for database management**
```bash
docker compose --profile admin up
# PgAdmin: http://localhost:5050
```

### Option 2: Local Development

#### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL with pgvector extension (or use Docker for DB only)
- OpenAI API key (or Ollama for local development)

#### Backend Setup

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp ../.env.example ../.env
# Edit .env with your configuration

# Start PostgreSQL (if using Docker)
docker compose up postgres -d

# Run database migrations
alembic upgrade head

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Setup

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Create environment file
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

# Run development server
npm run dev
```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for embeddings and LLM | `sk-...` |

### Database Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Async PostgreSQL connection URL | `postgresql+asyncpg://postgres:postgres@localhost:5432/rag_knowledge` |
| `POSTGRES_USER` | PostgreSQL username | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL password | `postgres` |
| `POSTGRES_DB` | PostgreSQL database name | `rag_knowledge` |

### Application Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Environment mode | `development` |
| `DEBUG` | Enable debug mode | `true` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:3000` |

### RAG Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `VECTOR_STORE_TYPE` | Vector store backend | `faiss` (dev) / `pgvector` (prod) |
| `CHUNK_SIZE` | Text chunk size | `1000` |
| `CHUNK_OVERLAP` | Chunk overlap | `200` |
| `RETRIEVAL_K` | Number of chunks to retrieve | `4` |

### Rate Limiting

| Variable | Description | Default |
|----------|-------------|---------|
| `RATE_LIMIT_PER_MINUTE` | Requests per minute per IP | `60` |
| `RATE_LIMIT_BURST` | Burst limit | `10` |

See `.env.example` for all configuration options or `.env.production.example` for production settings.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/health/ready` | Readiness check (with DB) |
| `GET` | `/api/v1/health/live` | Liveness check |
| `POST` | `/api/v1/documents/upload` | Upload a document |
| `POST` | `/api/v1/documents/{id}/ingest` | Process uploaded document |
| `GET` | `/api/v1/documents` | List all documents |
| `GET` | `/api/v1/documents/{id}` | Get document details |
| `DELETE` | `/api/v1/documents/{id}` | Delete a document |
| `POST` | `/api/v1/chat` | Send a chat message |
| `POST` | `/api/v1/chat/stream` | Stream chat response (SSE) |
| `GET` | `/api/v1/conversations` | List conversations |
| `DELETE` | `/api/v1/conversations/{id}` | Delete conversation |

### Example: Upload and Query a Document

```bash
# Upload a document
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -F "file=@document.pdf"

# Ingest the document (process and index)
curl -X POST http://localhost:8000/api/v1/documents/{document_id}/ingest

# Query the document
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is this document about?", "include_sources": true}'
```

## Project Structure

```
lanchain-rag-knowledge-infra/
├── backend/                 # Python FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes and dependencies
│   │   ├── core/           # Config, security, exceptions
│   │   ├── db/             # Database models and session
│   │   ├── services/       # Business logic services
│   │   ├── models/         # SQLAlchemy models
│   │   └── schemas/        # Pydantic schemas
│   ├── alembic/            # Database migrations
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # Next.js frontend
│   ├── src/
│   │   ├── app/           # Next.js app router
│   │   ├── components/    # React components
│   │   ├── lib/           # Utilities and API client
│   │   └── types/         # TypeScript types
│   └── Dockerfile
├── docker/                 # Docker configurations
│   └── init-db.sql        # Database initialization
├── docs/                   # Documentation
│   ├── ARCHITECTURE.md    # Technical architecture
│   ├── PROJECT_CHECKLIST.md
│   └── PROJECT_CONTINUITY.md
├── docker-compose.yml
├── .env.example
└── .env.production.example
```

## Development

### Running Tests

```bash
cd backend
pytest
```

### Code Quality

```bash
# Linting
ruff check .

# Type checking
mypy app/

# Frontend linting
cd frontend && npm run lint
```

### Database Migrations

```bash
cd backend

# Create a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Production Deployment

1. Copy `.env.production.example` to `.env` and configure all variables
2. Use strong passwords for database credentials
3. Set `ENVIRONMENT=production` and `DEBUG=false`
4. Configure `CORS_ORIGINS` with your production domains
5. Run with `docker compose up -d`

### Health Checks

The application provides three health endpoints for container orchestration:

- `/api/v1/health` - Basic health check with version info
- `/api/v1/health/ready` - Readiness check (verifies DB connectivity)
- `/api/v1/health/live` - Liveness check (simple alive check)

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - Technical design and data flow
- [Checklist](docs/PROJECT_CHECKLIST.md) - Implementation progress
- [Continuity](docs/PROJECT_CONTINUITY.md) - Session state

## License

MIT

## Contributing

This is a portfolio project. Contributions, issues, and feature requests are welcome.
