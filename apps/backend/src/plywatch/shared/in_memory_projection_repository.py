"""Shared in-memory base for bounded projection repositories."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Generic, TypeVar

TKey = TypeVar("TKey")
TProjection = TypeVar("TProjection")


class InMemoryProjectionRepository(Generic[TKey, TProjection]):
    """Thread-safe base for bounded in-memory projection repositories.

    This base intentionally stays small: it owns the storage dictionary, the
    application lock, and age-based pruning hooks. Concrete repositories keep
    their own domain-specific indexing and query logic on top.
    """

    def __init__(
        self,
        *,
        max_age_seconds: int,
        get_last_seen_at: Callable[[TProjection], str],
    ) -> None:
        self._items: dict[TKey, TProjection] = {}
        self._max_age_seconds = max_age_seconds
        self._get_last_seen_at = get_last_seen_at
        self._lock = Lock()

    def count(self) -> int:
        """Return the number of tracked projections."""
        with self._lock:
            self._prune_locked()
            return len(self._items)

    def max_age_seconds(self) -> int:
        """Return the configured retention age in seconds."""
        return self._max_age_seconds

    def _get_locked(self, key: TKey) -> TProjection | None:
        return self._items.get(key)

    def _upsert_locked(self, key: TKey, value: TProjection) -> None:
        self._items[key] = value

    def _list_locked(self) -> list[TProjection]:
        self._prune_locked()
        return list(self._items.values())

    def _prune_locked(self) -> None:
        if self._max_age_seconds <= 0:
            return
        cutoff = datetime.now(UTC) - timedelta(seconds=self._max_age_seconds)
        expired = [
            key
            for key, item in self._items.items()
            if _parse_iso8601(self._get_last_seen_at(item)) < cutoff
        ]
        for key in expired:
            removed = self._items.pop(key, None)
            if removed is not None:
                self._on_remove_locked(key, removed)

    def _on_remove_locked(self, key: TKey, value: TProjection) -> None:
        """Hook for subclasses to clean domain-specific indexes on removal."""
        pass


def _parse_iso8601(value: str) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=UTC)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
