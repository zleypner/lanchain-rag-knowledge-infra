"""File storage utilities for document management."""

import logging
import os
from pathlib import Path
from uuid import uuid4

import aiofiles
from fastapi import UploadFile

from app.core.config import settings
from app.core.exceptions import (
    DocumentUploadError,
    FileSizeLimitError,
    InvalidFileTypeError,
)

logger = logging.getLogger(__name__)


def validate_file_type(filename: str) -> str:
    """
    Validate that the file type is allowed.

    Args:
        filename: Original filename to validate.

    Returns:
        The file extension if valid.

    Raises:
        InvalidFileTypeError: If the file type is not allowed.
    """
    file_ext = Path(filename).suffix.lower()

    if file_ext not in settings.allowed_extensions:
        raise InvalidFileTypeError(
            file_type=file_ext,
            allowed_types=settings.allowed_extensions,
        )

    return file_ext


def get_file_path(filename: str) -> Path:
    """
    Get the full file path for a document.

    Args:
        filename: The stored filename.

    Returns:
        Full path to the file in the upload directory.
    """
    return settings.upload_dir / filename


async def save_upload_file(file: UploadFile) -> tuple[str, str, int]:
    """
    Save an uploaded file to the storage directory.

    Args:
        file: The uploaded file from FastAPI.

    Returns:
        Tuple of (stored_filename, file_extension, file_size).

    Raises:
        InvalidFileTypeError: If the file type is not allowed.
        FileSizeLimitError: If the file size exceeds the limit.
        DocumentUploadError: If there's an error saving the file.
    """
    if not file.filename:
        raise DocumentUploadError(
            message="No filename provided",
            details={"error": "filename_missing"},
        )

    # Validate file type
    file_ext = validate_file_type(file.filename)

    # Generate unique filename
    unique_id = str(uuid4())
    stored_filename = f"{unique_id}{file_ext}"
    file_path = get_file_path(stored_filename)

    # Ensure upload directory exists
    settings.upload_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Read file content to check size
        content = await file.read()
        file_size = len(content)

        # Check file size
        if file_size > settings.max_upload_size_bytes:
            size_mb = file_size / (1024 * 1024)
            raise FileSizeLimitError(
                size_mb=size_mb,
                max_size_mb=settings.max_upload_size_mb,
            )

        # Save file asynchronously
        async with aiofiles.open(file_path, "wb") as out_file:
            await out_file.write(content)

        logger.info(f"Saved file: {stored_filename} ({file_size} bytes)")
        return stored_filename, file_ext, file_size

    except (InvalidFileTypeError, FileSizeLimitError):
        raise
    except Exception as e:
        logger.error(f"Error saving file: {e}")
        # Clean up partial file if exists
        if file_path.exists():
            file_path.unlink()
        raise DocumentUploadError(
            message="Failed to save uploaded file",
            details={"error": str(e)},
        )


async def delete_file(filename: str) -> bool:
    """
    Delete a file from storage.

    Args:
        filename: The stored filename to delete.

    Returns:
        True if file was deleted, False if file didn't exist.
    """
    file_path = get_file_path(filename)

    try:
        if file_path.exists():
            os.remove(file_path)
            logger.info(f"Deleted file: {filename}")
            return True
        else:
            logger.warning(f"File not found for deletion: {filename}")
            return False
    except Exception as e:
        logger.error(f"Error deleting file {filename}: {e}")
        raise DocumentUploadError(
            message=f"Failed to delete file: {filename}",
            details={"error": str(e)},
        )
