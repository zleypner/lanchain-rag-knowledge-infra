"""Vector store service using FAISS for document storage and retrieval."""

import logging
import pickle
import uuid
from pathlib import Path
from typing import Any

from langchain_core.documents import Document

from app.core.config import settings
from app.core.exceptions import VectorStoreException

logger = logging.getLogger(__name__)


class VectorStoreService:
    """Service for managing document vectors using FAISS."""

    def __init__(
        self,
        index_path: Path | str | None = None,
        embedding_dimension: int = 1536,  # Default for text-embedding-3-small
    ) -> None:
        """
        Initialize the vector store service.

        Args:
            index_path: Path to store/load the FAISS index.
                       Defaults to settings.faiss_index_path.
            embedding_dimension: Dimension of the embedding vectors.
                                Defaults to 1536 (OpenAI text-embedding-3-small).
        """
        self.index_path = Path(index_path) if index_path else settings.faiss_index_path
        self.embedding_dimension = embedding_dimension

        self._index: Any = None  # FAISS index
        self._documents: dict[str, Document] = {}  # doc_id -> Document mapping
        self._id_to_index: dict[str, int] = {}  # doc_id -> FAISS index position
        self._index_to_id: dict[int, str] = {}  # FAISS index position -> doc_id

        self._faiss_available = self._check_faiss_support()

        # Ensure index directory exists
        self.index_path.mkdir(parents=True, exist_ok=True)

        # Try to load existing index
        self._load_index()

    def _check_faiss_support(self) -> bool:
        """Check if FAISS is available."""
        try:
            import faiss  # noqa: F401

            return True
        except ImportError:
            logger.warning(
                "FAISS not installed. Vector store operations will not be available. "
                "Install with: pip install faiss-cpu"
            )
            return False

    def _ensure_faiss_available(self) -> None:
        """Ensure FAISS is available or raise an exception."""
        if not self._faiss_available:
            raise VectorStoreException(
                message="FAISS is not available. Install with: pip install faiss-cpu",
                details={"index_path": str(self.index_path)},
            )

    def _create_index(self) -> None:
        """Create a new FAISS index."""
        self._ensure_faiss_available()
        import faiss

        # Use IndexFlatL2 for simplicity and accuracy
        # For large-scale, consider IndexIVFFlat or IndexHNSW
        self._index = faiss.IndexFlatL2(self.embedding_dimension)
        self._documents = {}
        self._id_to_index = {}
        self._index_to_id = {}

        logger.info(
            f"Created new FAISS index with dimension {self.embedding_dimension}"
        )

    def _load_index(self) -> bool:
        """
        Load the FAISS index from disk.

        Returns:
            True if index was loaded successfully, False otherwise.
        """
        if not self._faiss_available:
            return False

        import faiss

        index_file = self.index_path / "index.faiss"
        metadata_file = self.index_path / "metadata.pkl"

        if not index_file.exists() or not metadata_file.exists():
            logger.info("No existing FAISS index found. Will create new on first add.")
            return False

        try:
            # Load FAISS index
            self._index = faiss.read_index(str(index_file))

            # Load metadata
            with open(metadata_file, "rb") as f:
                metadata = pickle.load(f)
                self._documents = metadata.get("documents", {})
                self._id_to_index = metadata.get("id_to_index", {})
                self._index_to_id = metadata.get("index_to_id", {})
                self.embedding_dimension = metadata.get(
                    "embedding_dimension", self.embedding_dimension
                )

            logger.info(
                f"Loaded FAISS index with {self._index.ntotal} vectors "
                f"and {len(self._documents)} documents"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to load FAISS index: {e}")
            self._create_index()
            return False

    def save_index(self) -> None:
        """
        Save the FAISS index to disk.

        Raises:
            VectorStoreException: If saving fails.
        """
        self._ensure_faiss_available()

        if self._index is None:
            logger.warning("No index to save")
            return

        import faiss

        try:
            index_file = self.index_path / "index.faiss"
            metadata_file = self.index_path / "metadata.pkl"

            # Ensure directory exists
            self.index_path.mkdir(parents=True, exist_ok=True)

            # Save FAISS index
            faiss.write_index(self._index, str(index_file))

            # Save metadata
            metadata = {
                "documents": self._documents,
                "id_to_index": self._id_to_index,
                "index_to_id": self._index_to_id,
                "embedding_dimension": self.embedding_dimension,
            }
            with open(metadata_file, "wb") as f:
                pickle.dump(metadata, f)

            logger.info(
                f"Saved FAISS index with {self._index.ntotal} vectors to {self.index_path}"
            )

        except Exception as e:
            logger.exception(f"Failed to save FAISS index: {e}")
            raise VectorStoreException(
                message=f"Failed to save FAISS index: {str(e)}",
                details={"index_path": str(self.index_path)},
            ) from e

    def add_documents(
        self,
        documents: list[Document],
        embeddings: list[list[float]],
        doc_ids: list[str] | None = None,
    ) -> list[str]:
        """
        Add documents and their embeddings to the vector store.

        Args:
            documents: List of LangChain Document objects.
            embeddings: List of embedding vectors corresponding to documents.
            doc_ids: Optional list of document IDs. If not provided, UUIDs are generated.

        Returns:
            List of document IDs for the added documents.

        Raises:
            VectorStoreException: If adding documents fails.
        """
        self._ensure_faiss_available()

        if len(documents) != len(embeddings):
            raise VectorStoreException(
                message="Number of documents and embeddings must match",
                details={
                    "num_documents": len(documents),
                    "num_embeddings": len(embeddings),
                },
            )

        if not documents:
            return []

        import numpy as np

        # Create index if it doesn't exist
        if self._index is None:
            # Infer embedding dimension from first embedding
            self.embedding_dimension = len(embeddings[0])
            self._create_index()

        # Generate document IDs if not provided
        if doc_ids is None:
            doc_ids = [str(uuid.uuid4()) for _ in documents]

        if len(doc_ids) != len(documents):
            raise VectorStoreException(
                message="Number of document IDs must match number of documents",
                details={
                    "num_documents": len(documents),
                    "num_doc_ids": len(doc_ids),
                },
            )

        try:
            # Convert embeddings to numpy array
            embedding_array = np.array(embeddings, dtype=np.float32)

            # Verify embedding dimensions
            if embedding_array.shape[1] != self.embedding_dimension:
                raise VectorStoreException(
                    message="Embedding dimension mismatch",
                    details={
                        "expected": self.embedding_dimension,
                        "got": embedding_array.shape[1],
                    },
                )

            # Get current index size (starting position for new vectors)
            start_idx = self._index.ntotal

            # Add vectors to FAISS index
            self._index.add(embedding_array)

            # Store document metadata
            for i, (doc_id, doc) in enumerate(zip(doc_ids, documents)):
                faiss_idx = start_idx + i

                # Add doc_id to document metadata
                doc.metadata["doc_id"] = doc_id

                self._documents[doc_id] = doc
                self._id_to_index[doc_id] = faiss_idx
                self._index_to_id[faiss_idx] = doc_id

            logger.info(f"Added {len(documents)} documents to vector store")

            # Auto-save after adding documents
            self.save_index()

            return doc_ids

        except VectorStoreException:
            raise
        except Exception as e:
            logger.exception(f"Failed to add documents: {e}")
            raise VectorStoreException(
                message=f"Failed to add documents to vector store: {str(e)}",
                details={"num_documents": len(documents)},
            ) from e

    def similarity_search(
        self,
        query_embedding: list[float],
        k: int | None = None,
    ) -> list[Document]:
        """
        Search for similar documents using a query embedding.

        Args:
            query_embedding: The embedding vector for the query.
            k: Number of results to return. Defaults to settings.retrieval_k.

        Returns:
            List of Document objects most similar to the query.

        Raises:
            VectorStoreException: If search fails.
        """
        self._ensure_faiss_available()

        if self._index is None or self._index.ntotal == 0:
            logger.warning("Vector store is empty")
            return []

        k = k or settings.retrieval_k

        # Don't request more results than we have
        k = min(k, self._index.ntotal)

        import numpy as np

        try:
            # Convert query to numpy array
            query_array = np.array([query_embedding], dtype=np.float32)

            # Search FAISS index
            distances, indices = self._index.search(query_array, k)

            # Retrieve documents
            results: list[Document] = []
            for idx, distance in zip(indices[0], distances[0]):
                if idx == -1:  # FAISS returns -1 for missing results
                    continue

                doc_id = self._index_to_id.get(int(idx))
                if doc_id and doc_id in self._documents:
                    doc = self._documents[doc_id]
                    # Add similarity score to metadata
                    doc_copy = Document(
                        page_content=doc.page_content,
                        metadata={
                            **doc.metadata,
                            "similarity_score": float(distance),
                        },
                    )
                    results.append(doc_copy)

            logger.debug(f"Found {len(results)} similar documents")
            return results

        except Exception as e:
            logger.exception(f"Failed to perform similarity search: {e}")
            raise VectorStoreException(
                message=f"Failed to perform similarity search: {str(e)}",
                details={"k": k},
            ) from e

    def similarity_search_with_scores(
        self,
        query_embedding: list[float],
        k: int | None = None,
    ) -> list[tuple[Document, float]]:
        """
        Search for similar documents and return with similarity scores.

        Args:
            query_embedding: The embedding vector for the query.
            k: Number of results to return.

        Returns:
            List of (Document, score) tuples.
        """
        documents = self.similarity_search(query_embedding, k)
        return [
            (doc, doc.metadata.get("similarity_score", 0.0))
            for doc in documents
        ]

    def delete_documents(self, doc_ids: list[str]) -> int:
        """
        Delete documents from the vector store.

        Note: FAISS doesn't support direct deletion, so this marks documents
        as deleted and rebuilds the index on save.

        Args:
            doc_ids: List of document IDs to delete.

        Returns:
            Number of documents actually deleted.

        Raises:
            VectorStoreException: If deletion fails.
        """
        self._ensure_faiss_available()

        if self._index is None:
            return 0

        deleted_count = 0

        try:
            for doc_id in doc_ids:
                if doc_id in self._documents:
                    del self._documents[doc_id]

                    # Remove from mappings
                    if doc_id in self._id_to_index:
                        faiss_idx = self._id_to_index[doc_id]
                        del self._id_to_index[doc_id]
                        if faiss_idx in self._index_to_id:
                            del self._index_to_id[faiss_idx]

                    deleted_count += 1

            if deleted_count > 0:
                # Rebuild index without deleted documents
                self._rebuild_index()
                logger.info(f"Deleted {deleted_count} documents from vector store")

            return deleted_count

        except Exception as e:
            logger.exception(f"Failed to delete documents: {e}")
            raise VectorStoreException(
                message=f"Failed to delete documents: {str(e)}",
                details={"doc_ids": doc_ids},
            ) from e

    def _rebuild_index(self) -> None:
        """Rebuild the FAISS index after deletions."""
        self._ensure_faiss_available()

        if not self._documents:
            self._create_index()
            self.save_index()
            return

        # Note: This requires re-embedding, which is expensive
        # For production, consider using IndexIDMap or keeping embeddings
        # For now, we just clear the index - embeddings need to be re-added

        logger.warning(
            "Index rebuild required after deletion. "
            "Documents need to be re-embedded and re-added."
        )

        # Reset index but keep document metadata for reference
        self._create_index()
        self.save_index()

    def get_document(self, doc_id: str) -> Document | None:
        """
        Get a document by its ID.

        Args:
            doc_id: The document ID.

        Returns:
            The Document if found, None otherwise.
        """
        return self._documents.get(doc_id)

    def get_all_documents(self) -> list[Document]:
        """
        Get all documents in the vector store.

        Returns:
            List of all Document objects.
        """
        return list(self._documents.values())

    def get_document_count(self) -> int:
        """
        Get the number of documents in the vector store.

        Returns:
            Number of documents.
        """
        return len(self._documents)

    def get_vector_count(self) -> int:
        """
        Get the number of vectors in the FAISS index.

        Returns:
            Number of vectors.
        """
        if self._index is None:
            return 0
        return self._index.ntotal

    def clear(self) -> None:
        """Clear all documents and vectors from the store."""
        self._create_index()
        self.save_index()
        logger.info("Cleared vector store")

    def get_statistics(self) -> dict[str, Any]:
        """
        Get statistics about the vector store.

        Returns:
            Dictionary with store statistics.
        """
        return {
            "document_count": self.get_document_count(),
            "vector_count": self.get_vector_count(),
            "embedding_dimension": self.embedding_dimension,
            "index_path": str(self.index_path),
            "faiss_available": self._faiss_available,
        }


# Singleton instance for dependency injection
_vector_store_service: VectorStoreService | None = None


def get_vector_store_service() -> VectorStoreService:
    """Get or create the vector store service instance."""
    global _vector_store_service
    if _vector_store_service is None:
        _vector_store_service = VectorStoreService()
    return _vector_store_service


def reset_vector_store_service() -> None:
    """Reset the vector store service singleton (useful for testing)."""
    global _vector_store_service
    _vector_store_service = None
