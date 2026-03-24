"""Shared worker-domain constants and enums."""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal, TypeAlias


class WorkerState(StrEnum):
    ONLINE = "online"
    STALE = "stale"
    OFFLINE = "offline"


class WorkerEvent(StrEnum):
    ONLINE = "worker-online"
    HEARTBEAT = "worker-heartbeat"
    OFFLINE = "worker-offline"


WORKER_EVENT_PREFIX: Final = "worker-"

WORKER_STATE_ONLINE: Final = WorkerState.ONLINE.value
WORKER_STATE_STALE: Final = WorkerState.STALE.value
WORKER_STATE_OFFLINE: Final = WorkerState.OFFLINE.value

WorkerStateName: TypeAlias = Literal["online", "stale", "offline"]
WORKER_STATES: Final[tuple[WorkerStateName, ...]] = (
    WORKER_STATE_ONLINE,
    WORKER_STATE_STALE,
    WORKER_STATE_OFFLINE,
)

WORKER_EVENT_ONLINE: Final = WorkerEvent.ONLINE.value
WORKER_EVENT_HEARTBEAT: Final = WorkerEvent.HEARTBEAT.value
WORKER_EVENT_OFFLINE: Final = WorkerEvent.OFFLINE.value

WorkerEventType: TypeAlias = Literal["worker-online", "worker-heartbeat", "worker-offline"]
WORKER_EVENT_TYPES: Final[frozenset[WorkerEventType]] = frozenset(
    {
        WORKER_EVENT_ONLINE,
        WORKER_EVENT_HEARTBEAT,
        WORKER_EVENT_OFFLINE,
    }
)
