"""Internal event dispatcher for routing raw Celery events to projectors."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Protocol

from plywatch.shared.raw_events import RawCeleryEvent


class EventHandler(Protocol):
    """Projection handler able to consume one raw event."""

    handled_event_types: frozenset[str]

    def apply(self, event: RawCeleryEvent) -> None:
        """Consume one routed raw event."""


class EventDispatcher:
    """Dispatch raw events to registered handlers by event type."""

    def __init__(self) -> None:
        self._routes: dict[str, tuple[EventHandler, ...]] = {}

    def register_many(self, handlers: Iterable[EventHandler]) -> None:
        """Register a set of handlers against their declared event types."""
        grouped: dict[str, list[EventHandler]] = defaultdict(list)
        for handler in handlers:
            for event_type in handler.handled_event_types:
                grouped[event_type].append(handler)

        self._routes = {
            event_type: (*self._routes.get(event_type, ()), *registered)
            for event_type, registered in grouped.items()
        } | {
            event_type: handlers_tuple
            for event_type, handlers_tuple in self._routes.items()
            if event_type not in grouped
        }

    def dispatch(self, event: RawCeleryEvent) -> None:
        """Dispatch one raw event to all interested handlers."""
        for handler in self._routes.get(event.event_type, ()):
            handler.apply(event)
