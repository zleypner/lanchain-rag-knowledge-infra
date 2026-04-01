# LangChain RAG Knowledge Infrastructure

A production-ready Retrieval-Augmented Generation (RAG) system built with LangChain, enabling intelligent querying over unstructured documents.

## Overview

This system allows you to:
- **Ingest documents** (PDF, TXT) and automatically process them
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
| Frontend | Next.js, TypeScript, Tailwind |
| Database | PostgreSQL |
| Containerization | Docker |

## Project Structure

```
langchain-rag-knowledge-infra/
├── backend/                 # Python FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes
│   │   ├── core/           # Config, security
│   │   ├── services/       # Business logic
│   │   ├── models/         # Database models
│   │   └── schemas/        # Pydantic schemas
│   └── tests/
├── frontend/               # Next.js frontend
│   └── src/
├── docker/                 # Docker configurations
├── docs/                   # Documentation
│   ├── ARCHITECTURE.md     # Technical architecture
│   ├── PROJECT_CHECKLIST.md
│   └── PROJECT_CONTINUITY.md
└── data/                   # Data storage
    ├── uploads/            # Uploaded documents
    └── processed/          # Processed data
```

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- OpenAI API key (or Ollama for local development)

### Backend Setup

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
# Edit .env with your API keys

# Run development server
uvicorn app.main:app --reload
```

### Frontend Setup (Phase 6)

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### Docker Setup (Phase 7)

```bash
# Build and run all services
docker-compose up --build
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/documents/upload` | Upload a document |
| `POST` | `/api/v1/documents/ingest` | Process uploaded document |
| `GET` | `/api/v1/documents` | List all documents |
| `DELETE` | `/api/v1/documents/{id}` | Delete a document |
| `POST` | `/api/v1/chat` | Send a chat message |
| `GET` | `/api/v1/chat/stream` | Stream chat response (SSE) |
| `GET` | `/api/v1/health` | Health check |

## Configuration

Key environment variables:

```env
# Required
OPENAI_API_KEY=sk-...

# Optional - for local development
OLLAMA_BASE_URL=http://localhost:11434

# RAG settings
CHUNK_SIZE=1000
CHUNK_OVERLAP=200
RETRIEVAL_K=4
```

See `.env.example` for all configuration options.

## Documentation

- [Architecture](docs/ARCHITECTURE.md) - Technical design and data flow
- [Checklist](docs/PROJECT_CHECKLIST.md) - Implementation progress
- [Continuity](docs/PROJECT_CONTINUITY.md) - Session state

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
```

## License

MIT

## Contributing

This is a portfolio project. Contributions, issues, and feature requests are welcome.
