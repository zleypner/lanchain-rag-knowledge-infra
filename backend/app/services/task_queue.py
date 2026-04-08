"""Async task queue for background document processing."""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from app.core.config import settings
from app.services.redis_cache import get_redis_cache

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Task:
    """Background task representation."""

    task_id: str
    task_type: str
    status: TaskStatus
    data: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "status": self.status.value,
            "data": self.data,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Task":
        """Create task from dictionary."""
        return cls(
            task_id=data["task_id"],
            task_type=data["task_type"],
            status=TaskStatus(data["status"]),
            data=data.get("data", {}),
            result=data.get("result"),
            error=data.get("error"),
            created_at=(
                datetime.fromisoformat(data["created_at"])
                if data.get("created_at")
                else datetime.utcnow()
            ),
            started_at=(
                datetime.fromisoformat(data["started_at"])
                if data.get("started_at")
                else None
            ),
            completed_at=(
                datetime.fromisoformat(data["completed_at"])
                if data.get("completed_at")
                else None
            ),
        )


class TaskQueue:
    """Simple async task queue using Redis as backend."""

    def __init__(self) -> None:
        """Initialize task queue."""
        self.cache = get_redis_cache()
        self._processing_tasks: dict[str, asyncio.Task] = {}
        logger.info("Task queue initialized")

    def create_task(
        self,
        task_type: str,
        data: dict[str, Any],
    ) -> Task:
        """
        Create a new background task.

        Args:
            task_type: Type of task (e.g., 'ingest_document').
            data: Task data (e.g., {'document_id': '123'}).

        Returns:
            Created Task object.
        """
        task = Task(
            task_id=str(uuid.uuid4()),
            task_type=task_type,
            status=TaskStatus.PENDING,
            data=data,
        )

        # Store task in cache
        self._save_task(task)

        logger.info(f"Created task: {task.task_id} ({task_type})")
        return task

    def get_task(self, task_id: str) -> Task | None:
        """
        Get task by ID.

        Args:
            task_id: Task ID.

        Returns:
            Task object or None if not found.
        """
        if not self.cache.is_available:
            # Fall back to in-memory tracking
            return None

        task_data = self.cache.get("task", task_id)
        if task_data:
            return Task.from_dict(task_data)
        return None

    def update_task(
        self,
        task_id: str,
        status: TaskStatus | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> bool:
        """
        Update task status and results.

        Args:
            task_id: Task ID.
            status: New status.
            result: Task result.
            error: Error message if failed.

        Returns:
            True if updated successfully.
        """
        task = self.get_task(task_id)
        if not task:
            logger.warning(f"Task not found: {task_id}")
            return False

        # Update fields
        if status:
            task.status = status
            if status == TaskStatus.PROCESSING:
                task.started_at = datetime.utcnow()
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                task.completed_at = datetime.utcnow()

        if result:
            task.result = result
        if error:
            task.error = error

        self._save_task(task)
        logger.debug(f"Updated task: {task_id} -> {status}")
        return True

    def _save_task(self, task: Task) -> None:
        """Save task to cache."""
        if self.cache.is_available:
            # Store tasks for 24 hours
            self.cache.set("task", task.task_id, task.to_dict(), ttl=86400)

    async def enqueue(
        self,
        task_type: str,
        data: dict[str, Any],
        handler: Any,
    ) -> Task:
        """
        Enqueue a task for background processing.

        Args:
            task_type: Type of task.
            data: Task data.
            handler: Async function to execute.

        Returns:
            Task object.
        """
        task = self.create_task(task_type, data)

        # Start processing in background
        asyncio_task = asyncio.create_task(self._process_task(task, handler))
        self._processing_tasks[task.task_id] = asyncio_task

        return task

    async def _process_task(self, task: Task, handler: Any) -> None:
        """
        Process a background task.

        Args:
            task: Task to process.
            handler: Async function to execute.
        """
        try:
            logger.info(f"Processing task: {task.task_id} ({task.task_type})")
            self.update_task(task.task_id, status=TaskStatus.PROCESSING)

            # Execute the handler
            result = await handler(**task.data)

            # Mark as completed
            self.update_task(
                task.task_id,
                status=TaskStatus.COMPLETED,
                result=result if isinstance(result, dict) else {"result": str(result)},
            )
            logger.info(f"Task completed: {task.task_id}")

        except Exception as e:
            logger.exception(f"Task failed: {task.task_id}")
            self.update_task(
                task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
            )

        finally:
            # Clean up
            if task.task_id in self._processing_tasks:
                del self._processing_tasks[task.task_id]

    def list_tasks(
        self,
        task_type: str | None = None,
        status: TaskStatus | None = None,
    ) -> list[Task]:
        """
        List tasks with optional filters.

        Args:
            task_type: Filter by task type.
            status: Filter by status.

        Returns:
            List of Task objects.
        """
        # This is a simplified implementation
        # In production, you'd want to use Redis sorted sets or lists
        # for better querying capabilities
        tasks = []

        if not self.cache.is_available:
            return tasks

        # For now, we just track active processing tasks
        for task_id in list(self._processing_tasks.keys()):
            task = self.get_task(task_id)
            if task:
                if task_type and task.task_type != task_type:
                    continue
                if status and task.status != status:
                    continue
                tasks.append(task)

        return tasks

    def get_statistics(self) -> dict[str, Any]:
        """
        Get task queue statistics.

        Returns:
            Dictionary with statistics.
        """
        return {
            "active_tasks": len(self._processing_tasks),
            "cache_available": self.cache.is_available,
        }


# Singleton instance
_task_queue: TaskQueue | None = None


def get_task_queue() -> TaskQueue:
    """Get or create the task queue instance."""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue()
    return _task_queue


def reset_task_queue() -> None:
    """Reset the task queue singleton (useful for testing)."""
    global _task_queue
    _task_queue = None
