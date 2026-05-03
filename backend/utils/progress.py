import asyncio
import json
from contextvars import ContextVar
from typing import Literal

from pydantic import BaseModel

EventType = Literal["status", "node_start", "node_complete", "artifact", "error", "done"]

progress_queue: ContextVar[asyncio.Queue] = ContextVar("progress_queue", default=None)


class ProgressEvent(BaseModel):
    type: EventType
    node: str | None = None
    message: str | None = None
    data: dict | None = None
    progress: int | None = None  # 0-100, only set on download progress updates

    def to_sse(self) -> str:
        return f"data: {self.model_dump_json(exclude_none=True)}\n\n"


async def emit(event: ProgressEvent) -> None:
    queue = progress_queue.get(None)
    if queue:
        await queue.put(event)
