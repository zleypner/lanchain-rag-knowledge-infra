# LangChain RAG Knowledge Infrastructure - Architecture

## Overview

This document describes the technical architecture of a production-ready Retrieval-Augmented Generation (RAG) system built with LangChain. The system enables intelligent querying over unstructured documents by combining semantic search with large language model capabilities.

---

## Technology Stack

### Backend
| Component | Technology | Rationale |
|-----------|------------|-----------|
| Language | Python 3.11+ | LangChain's Python library is more mature, better ML ecosystem |
| Framework | FastAPI | Async support, automatic OpenAPI docs, high performance |
| RAG Framework | LangChain | Industry standard for LLM applications, modular architecture |
| Vector Store | PGVector (primary), FAISS (dev) | PostgreSQL-based for production, FAISS for local development |
| LLM Provider | OpenAI API / Ollama | OpenAI for production, Ollama for local cost-free development |
| Document Parsing | PyPDF2, python-docx | Reliable document text extraction |
| Task Queue | Celery + Redis (optional) | Async document processing for large files |

### Frontend
| Component | Technology | Rationale |
|-----------|------------|-----------|
| Framework | Next.js 14+ | App Router, Server Components, modern React |
| Language | TypeScript | Type safety, better DX |
| Styling | Tailwind CSS | Rapid UI development, utility-first |
| State | React Query / SWR | Server state management |

### Infrastructure
| Component | Technology | Rationale |
|-----------|------------|-----------|
| Containerization | Docker + Docker Compose | Consistent environments, easy deployment |
| Database | PostgreSQL + PGVector | Production-grade vector storage |
| Caching | Redis | Session storage, caching, task queue |

---

## High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                 FRONTEND                                     │
│                           (Next.js + TypeScript)                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  Document   │  │   Chat      │  │  Knowledge  │  │   Admin     │        │
│  │   Upload    │  │  Interface  │  │    Base     │  │  Dashboard  │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
└─────────┼────────────────┼────────────────┼────────────────┼────────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API GATEWAY                                     │
│                         (FastAPI REST + SSE)                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │  /upload    │  │  /chat      │  │  /documents │  │  /health    │        │
│  │  /ingest    │  │  /query     │  │  /search    │  │  /metrics   │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
└─────────┼────────────────┼────────────────┼────────────────┼────────────────┘
          │                │                │                │
          ▼                ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SERVICE LAYER                                      │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │  Document        │  │  RAG             │  │  Conversation    │          │
│  │  Ingestion       │  │  Pipeline        │  │  Manager         │          │
│  │  Service         │  │  Service         │  │  Service         │          │
│  └────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘          │
│           │                     │                     │                     │
│  ┌────────▼─────────┐  ┌────────▼─────────┐  ┌────────▼─────────┐          │
│  │ • Parse docs     │  │ • Embed query    │  │ • Chat history   │          │
│  │ • Chunk text     │  │ • Retrieve ctx   │  │ • Context window │          │
│  │ • Generate embeds│  │ • Generate resp  │  │ • Session mgmt   │          │
│  │ • Store vectors  │  │ • Stream output  │  │ • Memory buffer  │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          LANGCHAIN CORE                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Document    │  │  Text        │  │  Embedding   │  │  Retriever   │    │
│  │  Loaders     │  │  Splitters   │  │  Models      │  │  Chains      │    │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤  ├──────────────┤    │
│  │ PyPDFLoader  │  │ Recursive    │  │ OpenAI       │  │ Vector Store │    │
│  │ TextLoader   │  │ Character    │  │ Ollama       │  │ Retriever    │    │
│  │ Unstructured │  │ Splitter     │  │ HuggingFace  │  │ Multi-Query  │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │  LLM         │  │  Memory      │  │  Output      │                      │
│  │  Interface   │  │  Management  │  │  Parsers     │                      │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤                      │
│  │ ChatOpenAI   │  │ Buffer       │  │ StrOutput    │                      │
│  │ Ollama       │  │ Summary      │  │ JSON Parser  │                      │
│  │ Anthropic    │  │ Conversation │  │ Pydantic     │                      │
│  └──────────────┘  └──────────────┘  └──────────────┘                      │
└─────────────────────────────────────────────────────────────────────────────┘
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA LAYER                                         │
│  ┌────────────────────────┐  ┌────────────────────────┐                    │
│  │      PostgreSQL        │  │        Redis           │                    │
│  │      + PGVector        │  │       (Cache)          │                    │
│  ├────────────────────────┤  ├────────────────────────┤                    │
│  │ • Document metadata    │  │ • Session data         │                    │
│  │ • Vector embeddings    │  │ • Query cache          │                    │
│  │ • User data            │  │ • Rate limiting        │                    │
│  │ • Conversation history │  │ • Task queue           │                    │
│  └────────────────────────┘  └────────────────────────┘                    │
│                                                                             │
│  ┌────────────────────────┐                                                │
│  │     File Storage       │                                                │
│  ├────────────────────────┤                                                │
│  │ • Original documents   │                                                │
│  │ • Processed chunks     │                                                │
│  └────────────────────────┘                                                │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Responsibilities

### 1. Document Ingestion Service
**Purpose:** Handle document upload, parsing, and preprocessing

**Responsibilities:**
- Accept file uploads (PDF, TXT, DOCX)
- Validate file types and sizes
- Extract text content from documents
- Store original files with metadata
- Trigger processing pipeline

**LangChain Components:**
- `PyPDFLoader` - PDF extraction
- `TextLoader` - Plain text files
- `UnstructuredFileLoader` - Generic file handling

### 2. Text Processing Pipeline
**Purpose:** Transform raw text into vector-ready chunks

**Responsibilities:**
- Clean and normalize text
- Split text into optimal chunks
- Maintain chunk metadata (source, page, position)
- Handle overlap for context preservation

**LangChain Components:**
- `RecursiveCharacterTextSplitter` - Smart text chunking
- `Document` - Chunk representation with metadata

**Configuration:**
```python
chunk_size: 1000  # characters per chunk
chunk_overlap: 200  # overlap between chunks
separators: ["\n\n", "\n", " ", ""]  # split hierarchy
```

### 3. Embedding Service
**Purpose:** Generate vector representations of text

**Responsibilities:**
- Generate embeddings for document chunks
- Generate embeddings for user queries
- Support multiple embedding providers
- Handle batch processing efficiently

**LangChain Components:**
- `OpenAIEmbeddings` - OpenAI's text-embedding models
- `OllamaEmbeddings` - Local embedding generation
- `HuggingFaceEmbeddings` - Open source alternative

**Embedding Model:** `text-embedding-3-small` (1536 dimensions)

### 4. Vector Store Service
**Purpose:** Store and retrieve vector embeddings

**Responsibilities:**
- Persist document embeddings
- Perform similarity search
- Filter by metadata
- Manage document collections

**LangChain Components:**
- `PGVector` - PostgreSQL vector store
- `FAISS` - In-memory vector store (development)

**Schema:**
```sql
CREATE TABLE document_embeddings (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id),
    content TEXT,
    embedding VECTOR(1536),
    metadata JSONB,
    created_at TIMESTAMP
);
```

### 5. RAG Pipeline Service
**Purpose:** Orchestrate retrieval and generation

**Responsibilities:**
- Receive user queries
- Retrieve relevant context
- Construct prompts with context
- Generate LLM responses
- Stream responses to client

**LangChain Components:**
- `RetrievalQA` - Question answering chain
- `ConversationalRetrievalChain` - With chat history
- `LCEL` - LangChain Expression Language for custom chains

**RAG Flow:**
```
Query → Embed → Retrieve(k=4) → Rerank → Construct Prompt → LLM → Response
```

### 6. Conversation Manager
**Purpose:** Handle multi-turn conversations

**Responsibilities:**
- Maintain conversation history
- Manage context window
- Store/retrieve sessions
- Apply memory strategies

**LangChain Components:**
- `ConversationBufferMemory` - Full history
- `ConversationSummaryMemory` - Summarized history
- `ConversationBufferWindowMemory` - Sliding window

### 7. API Layer
**Purpose:** Expose services to frontend

**Endpoints:**
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/documents/upload` | Upload document |
| POST | `/api/v1/documents/ingest` | Process document |
| GET | `/api/v1/documents` | List documents |
| DELETE | `/api/v1/documents/{id}` | Delete document |
| POST | `/api/v1/chat` | Send message |
| GET | `/api/v1/chat/stream` | SSE streaming |
| GET | `/api/v1/chat/history/{session_id}` | Get history |
| GET | `/api/v1/health` | Health check |

---

## Data Flow

### Document Ingestion Flow
```
1. User uploads PDF/TXT via frontend
2. API receives file, validates, stores to disk
3. Document record created in PostgreSQL
4. Ingestion Service triggered:
   a. Load document with appropriate loader
   b. Extract text content
   c. Split into chunks (1000 chars, 200 overlap)
   d. Generate embeddings for each chunk
   e. Store vectors in PGVector with metadata
5. Document marked as "indexed"
6. Frontend notified of completion
```

### Query Flow
```
1. User sends question via chat interface
2. API receives query + session_id
3. RAG Pipeline activated:
   a. Load conversation history for session
   b. Generate embedding for query
   c. Retrieve top-k relevant chunks (k=4)
   d. Construct prompt with:
      - System instructions
      - Retrieved context
      - Conversation history
      - User question
   e. Send to LLM
   f. Stream response tokens via SSE
4. Store Q&A pair in conversation history
5. Return complete response with sources
```

---

## Folder Structure

```
langchain-rag-knowledge-infra/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI application entry
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py             # Dependency injection
│   │   │   └── routes/
│   │   │       ├── __init__.py
│   │   │       ├── documents.py    # Document endpoints
│   │   │       ├── chat.py         # Chat endpoints
│   │   │       └── health.py       # Health checks
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py           # Settings management
│   │   │   ├── security.py         # Auth utilities
│   │   │   └── exceptions.py       # Custom exceptions
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── document_service.py # Document operations
│   │   │   ├── ingestion_service.py# Parsing & chunking
│   │   │   ├── embedding_service.py# Vector generation
│   │   │   ├── retrieval_service.py# Context retrieval
│   │   │   ├── llm_service.py      # LLM interactions
│   │   │   └── chat_service.py     # Conversation handling
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── document.py         # Document ORM model
│   │   │   ├── conversation.py     # Conversation model
│   │   │   └── user.py             # User model (optional)
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── document.py         # Document Pydantic schemas
│   │   │   ├── chat.py             # Chat schemas
│   │   │   └── common.py           # Shared schemas
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── file_handler.py     # File operations
│   │       └── text_processing.py  # Text utilities
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py             # Test fixtures
│   │   ├── test_documents.py
│   │   ├── test_chat.py
│   │   └── test_services.py
│   ├── alembic/                    # Database migrations
│   │   ├── versions/
│   │   └── env.py
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   ├── chat/
│   │   │   │   └── page.tsx
│   │   │   └── documents/
│   │   │       └── page.tsx
│   │   ├── components/
│   │   │   ├── ChatInterface.tsx
│   │   │   ├── DocumentUpload.tsx
│   │   │   ├── DocumentList.tsx
│   │   │   └── MessageBubble.tsx
│   │   ├── lib/
│   │   │   ├── api.ts              # API client
│   │   │   └── utils.ts
│   │   └── types/
│   │       └── index.ts            # TypeScript types
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.js
│   └── next.config.js
├── docker/
│   ├── Dockerfile.backend
│   ├── Dockerfile.frontend
│   └── docker-compose.yml
├── scripts/
│   ├── setup.sh                    # Initial setup
│   ├── seed_data.sh                # Sample data
│   └── run_dev.sh                  # Development runner
├── data/
│   ├── uploads/                    # Original files
│   └── processed/                  # Processed data
├── docs/
│   ├── ARCHITECTURE.md             # This file
│   ├── PROJECT_CHECKLIST.md        # Implementation checklist
│   ├── PROJECT_CONTINUITY.md       # Session continuity
│   └── API.md                      # API documentation
├── .env.example
├── .gitignore
└── README.md
```

---

## Key Technical Decisions

### 1. Python over JavaScript for Backend
**Decision:** Use Python with FastAPI instead of Node.js
**Rationale:**
- LangChain Python is more mature and feature-complete
- Better ML/AI library ecosystem (numpy, pandas, etc.)
- More examples and community support
- FastAPI provides excellent async performance

### 2. PGVector over Pinecone/Weaviate
**Decision:** Use PostgreSQL with PGVector extension
**Rationale:**
- Self-hosted, no vendor lock-in
- Combines relational data with vectors
- Simpler deployment (one database)
- Cost-effective for portfolio project
- Production-proven technology

### 3. LCEL over Legacy Chains
**Decision:** Use LangChain Expression Language for new chains
**Rationale:**
- More flexible composition
- Better streaming support
- Type hints and IDE support
- Future-proof (LangChain's direction)

### 4. Chunk Size: 1000 characters
**Decision:** Use 1000 char chunks with 200 char overlap
**Rationale:**
- Balances context completeness vs retrieval precision
- Works well with most embedding models
- Industry-standard starting point
- Can be tuned per document type

### 5. Embedding Model: text-embedding-3-small
**Decision:** Use OpenAI's text-embedding-3-small
**Rationale:**
- Good balance of quality and cost
- 1536 dimensions (standard)
- Fast inference
- Supports Ollama fallback for development

---

## Security Considerations

1. **File Upload Validation**
   - Whitelist allowed file types
   - Enforce size limits (default: 10MB)
   - Scan for malicious content

2. **API Security**
   - Rate limiting on all endpoints
   - Input validation with Pydantic
   - CORS configuration

3. **Data Isolation** (optional)
   - User-level document isolation
   - Metadata-based filtering in vector search

4. **Secrets Management**
   - Environment variables for API keys
   - Never commit secrets to repository

---

## Scalability Path

### Phase 1: Single Instance (Current)
- SQLite/PostgreSQL local
- FAISS in-memory vectors
- Single FastAPI process

### Phase 2: Production Ready
- PGVector on managed PostgreSQL
- Redis for caching
- Multiple API workers (Gunicorn)
- Docker deployment

### Phase 3: Scale Out
- Kubernetes deployment
- Separate ingestion workers
- CDN for static assets
- Monitoring and observability

---

## References

- [LangChain Documentation](https://python.langchain.com/docs/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [PGVector GitHub](https://github.com/pgvector/pgvector)
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
