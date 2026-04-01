"""Application configuration using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -----------------
    # Application
    # -----------------
    environment: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_v1_prefix: str = "/api/v1"

    # -----------------
    # CORS
    # -----------------
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list[str]) -> list[str]:
        """Parse CORS origins from comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    # -----------------
    # OpenAI
    # -----------------
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # -----------------
    # Ollama (Local LLM)
    # -----------------
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_embedding_model: str = "nomic-embed-text"

    # -----------------
    # File Upload
    # -----------------
    upload_dir: Path = Path("./data/uploads")
    max_upload_size_mb: int = 10
    allowed_extensions: list[str] = Field(default=[".pdf", ".txt", ".md", ".docx"])

    @field_validator("allowed_extensions", mode="before")
    @classmethod
    def parse_extensions(cls, v: str | list[str]) -> list[str]:
        """Parse allowed extensions from comma-separated string or list."""
        if isinstance(v, str):
            return [ext.strip() for ext in v.split(",")]
        return v

    @property
    def max_upload_size_bytes(self) -> int:
        """Return max upload size in bytes."""
        return self.max_upload_size_mb * 1024 * 1024

    # -----------------
    # Vector Store
    # -----------------
    vector_store_type: Literal["faiss", "pgvector"] = "faiss"
    faiss_index_path: Path = Path("./data/faiss_index")

    # -----------------
    # Database (Phase 5)
    # -----------------
    database_url: str = ""
    pgvector_collection: str = "document_embeddings"

    # -----------------
    # RAG Configuration
    # -----------------
    retrieval_k: int = 4
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # -----------------
    # Logging
    # -----------------
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment == "development"

    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
