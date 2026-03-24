"""Raw Celery event models and in-memory storage."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from datetime import UTC, datetime
from threading import Lock
from typing import Final, cast

import msgspec
from loom.core.model import LoomStruct

JsonScalar = str | int | float | bool | None
JsonValue = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]

_MAX_STRING_LENGTH: Final[int] = 500


class RawCeleryEvent(LoomStruct, kw_only=True):
    """Normalized raw Celery event captured by the monitor.

    Attributes:
        captured_at: UTC timestamp when the monitor received the event.
        event_type: Celery event type such as ``task-sent``.
        uuid: Task UUID if present.
        hostname: Worker hostname if present.
        payload: Safe JSON-like representation of the original event payload.
    """

    captured_at: str
    event_type: str
    uuid: str | None
    hostname: str | None
    payload: dict[str, JsonValue]

    def to_dict(self) -> dict[str, JsonValue]:
        """Return a JSON-like dict for API responses."""
        return cast(dict[str, JsonValue], msgspec.to_builtins(self))


class RawEventStore:
    """Bounded in-memory store for recent raw Celery events."""

    def __init__(self, max_events: int) -> None:
        self._events: deque[RawCeleryEvent] = deque(maxlen=max_events)
        self._lock = Lock()

    def append(self, event: RawCeleryEvent) -> None:
        """Append one event to the store."""
        with self._lock:
            self._events.append(event)

    def list_recent(self, limit: int) -> list[RawCeleryEvent]:
        """Return the most recent events, newest first."""
        with self._lock:
            items = list(self._events)
        items.reverse()
        return items[:limit]

    def count(self) -> int:
        """Return the current number of retained events."""
        with self._lock:
            return len(self._events)

    def clear(self) -> int:
        """Remove all retained raw events and return the removed count."""
        with self._lock:
            removed = len(self._events)
            self._events.clear()
        return removed


class EventCounterStore:
    """Independent counters for observed Celery events.

    This store tracks all observed events since the monitor startup, regardless
    of whether an event is retained in the raw inspection buffer.
    """

    def __init__(self) -> None:
        self._total_count = 0
        self._counts_by_type: dict[str, int] = {}
        self._lock = Lock()

    def observe(self, event: RawCeleryEvent) -> None:
        """Record one observed event."""
        with self._lock:
            self._total_count += 1
            self._counts_by_type[event.event_type] = (
                self._counts_by_type.get(event.event_type, 0) + 1
            )

    def total_count(self) -> int:
        """Return the number of observed events since startup."""
        with self._lock:
            return self._total_count

    def count_for(self, event_type: str) -> int:
        """Return the observed count for one event type."""
        with self._lock:
            return self._counts_by_type.get(event_type, 0)


def build_raw_event(event: Mapping[str, object]) -> RawCeleryEvent:
    """Normalize a Celery event mapping into a safe raw event object."""
    event_type_obj = event.get("type")
    uuid_obj = event.get("uuid")
    hostname_obj = event.get("hostname")
    return RawCeleryEvent(
        captured_at=datetime.now(UTC).isoformat(),
        event_type=str(event_type_obj) if event_type_obj is not None else "unknown",
        uuid=str(uuid_obj) if uuid_obj is not None else None,
        hostname=str(hostname_obj) if hostname_obj is not None else None,
        payload=_normalize_mapping(event),
    )


def _normalize_mapping(data: Mapping[str, object]) -> dict[str, JsonValue]:
    normalized: dict[str, JsonValue] = {}
    for key, value in data.items():
        normalized[str(key)] = _normalize_value(value)
    return normalized


def _normalize_value(value: object) -> JsonValue:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return value[:_MAX_STRING_LENGTH]
    if isinstance(value, Mapping):
        return _normalize_mapping(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_normalize_value(item) for item in value]
    return repr(value)[:_MAX_STRING_LENGTH]
