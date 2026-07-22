from __future__ import annotations

import threading
import time
import uuid
from typing import Any


class TaskStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tasks: dict[str, dict[str, Any]] = {}

    def create(self, prompt_id: str, client_id: str, meta: dict | None = None) -> str:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        with self._lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "prompt_id": prompt_id,
                "client_id": client_id,
                "status": "queued",
                "created_at": time.time(),
                "updated_at": time.time(),
                "meta": meta or {},
                "media": [],
                "error": None,
                "progress": {"value": 0, "max": 0},
                "queue_pos": 0,
            }
        return task_id

    def get(self, task_id: str) -> dict | None:
        with self._lock:
            task = self._tasks.get(task_id)
            return dict(task) if task else None

    def update(self, task_id: str, **fields: Any) -> dict | None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return None
            task.update(fields)
            task["updated_at"] = time.time()
            return dict(task)

    def find_by_prompt(self, prompt_id: str) -> dict | None:
        with self._lock:
            for task in self._tasks.values():
                if task.get("prompt_id") == prompt_id:
                    return dict(task)
        return None


task_store = TaskStore()
