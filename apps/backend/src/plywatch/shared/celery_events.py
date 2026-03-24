"""Background Celery event consumer for Plywatch."""

from __future__ import annotations

import logging
import socket
from threading import Event, Thread
from typing import Callable, cast

from celery import Celery
from celery.events import EventReceiver  # type: ignore[import-untyped]

from plywatch.shared.raw_events import (
    EventCounterStore,
    RawCeleryEvent,
    RawEventStore,
    build_raw_event,
)


class CeleryEventConsumer:
    """Consume raw Celery events in a background thread."""

    def __init__(
        self,
        celery_app: Celery,
        store: RawEventStore,
        counter_store: EventCounterStore,
        *,
        buffer_excluded_event_types: tuple[str, ...] = (),
        on_event: Callable[[RawCeleryEvent], None] | None = None,
    ) -> None:
        self._app = celery_app
        self._store = store
        self._counter_store = counter_store
        self._buffer_excluded_event_types = frozenset(buffer_excluded_event_types)
        self._on_event = on_event
        self._logger = logging.getLogger("plywatch.celery_events")
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        """Start the background consumer thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run, name="plywatch-celery-events", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Request shutdown and wait briefly for the thread to exit."""
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=3.0)

    def _run(self) -> None:
        self._logger.info("Starting Celery event consumer")
        while not self._stop_event.is_set():
            try:
                with self._app.connection_for_read() as connection:
                    receiver = EventReceiver(
                        connection,
                        handlers={"*": self._handle_event},
                        app=self._app,
                    )
                    receiver.capture(limit=None, timeout=1.0, wakeup=True)
            except socket.timeout:
                continue
            except Exception as exc:
                self._logger.exception("Celery event consumer loop failed: %s", exc)

    def _handle_event(self, event: object) -> None:
        event_mapping = cast(dict[str, object], event)
        raw_event = build_raw_event(event_mapping)
        self._counter_store.observe(raw_event)
        if raw_event.event_type not in self._buffer_excluded_event_types:
            self._store.append(raw_event)
        if self._on_event is not None:
            self._on_event(raw_event)
