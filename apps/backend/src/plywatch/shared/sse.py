"""Server-sent events fanout for live frontend updates."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator


class SseFanout:
    """In-process SSE broadcaster safe to publish from background threads."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue[str]] = set()

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Attach the running event loop used to fan out messages."""
        self._loop = loop

    def publish(self, event: dict[str, object]) -> None:
        """Publish one JSON event to all active subscribers."""
        if self._loop is None:
            return
        payload = self._encode_sse(event)
        self._loop.call_soon_threadsafe(self._publish_in_loop, payload)

    async def subscribe(self) -> AsyncIterator[str]:
        """Yield SSE payloads for one subscriber."""
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        try:
            yield self._encode_sse({"type": "stream.ready"})
            while True:
                message = await queue.get()
                yield message
        finally:
            self._subscribers.discard(queue)

    def _publish_in_loop(self, payload: str) -> None:
        for queue in tuple(self._subscribers):
            if queue.full():
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            queue.put_nowait(payload)

    def _encode_sse(self, event: dict[str, object]) -> str:
        event_name = str(event.get("type", "message"))
        data = json.dumps(event, separators=(",", ":"))
        return f"event: {event_name}\ndata: {data}\n\n"
