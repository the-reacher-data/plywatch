"""Shared task-domain constants to avoid stringly-typed branching."""

from __future__ import annotations

from typing import Final, Literal, TypeAlias

TASK_EVENT_SENT: Final = "task-sent"
TASK_EVENT_RECEIVED: Final = "task-received"
TASK_EVENT_STARTED: Final = "task-started"
TASK_EVENT_RETRIED: Final = "task-retried"
TASK_EVENT_SUCCEEDED: Final = "task-succeeded"
TASK_EVENT_FAILED: Final = "task-failed"

TaskEventType: TypeAlias = Literal[
    "task-sent",
    "task-received",
    "task-started",
    "task-retried",
    "task-succeeded",
    "task-failed",
]

TASK_EVENTS: Final[frozenset[TaskEventType]] = frozenset(
    {
        TASK_EVENT_SENT,
        TASK_EVENT_RECEIVED,
        TASK_EVENT_STARTED,
        TASK_EVENT_RETRIED,
        TASK_EVENT_SUCCEEDED,
        TASK_EVENT_FAILED,
    }
)

TASK_STATE_SENT: Final = "sent"
TASK_STATE_RECEIVED: Final = "received"
TASK_STATE_STARTED: Final = "started"
TASK_STATE_RETRYING: Final = "retrying"
TASK_STATE_SUCCEEDED: Final = "succeeded"
TASK_STATE_FAILED: Final = "failed"
TASK_STATE_LOST: Final = "lost"

TaskStateName: TypeAlias = Literal[
    "sent",
    "received",
    "started",
    "retrying",
    "succeeded",
    "failed",
    "lost",
]

TASK_SECTION_QUEUED: Final = "queued"
TASK_SECTION_RUNNING: Final = "running"
TASK_SECTION_SUCCEEDED: Final = "succeeded"
TASK_SECTION_FAILED: Final = "failed"

TaskSectionName: TypeAlias = Literal[
    "queued",
    "running",
    "succeeded",
    "failed",
]

RUNNING_TASK_STATES: Final[frozenset[TaskStateName]] = frozenset(
    {
        TASK_STATE_SENT,
        TASK_STATE_RECEIVED,
        TASK_STATE_STARTED,
        TASK_STATE_RETRYING,
    }
)
QUEUED_TASK_STATES: Final[frozenset[TaskStateName]] = frozenset(
    {
        TASK_STATE_SENT,
        TASK_STATE_RECEIVED,
    }
)
COMPLETED_TASK_STATES: Final[frozenset[TaskStateName]] = frozenset(
    {
        TASK_STATE_SUCCEEDED,
        TASK_STATE_FAILED,
        TASK_STATE_LOST,
    }
)

TASK_KIND_JOB: Final = "job"
TASK_KIND_CALLBACK: Final = "callback"
TASK_KIND_CALLBACK_ERROR: Final = "callback_error"
TASK_KIND_UNKNOWN: Final = "unknown"

VISIBLE_ROOT_TASK_KINDS: Final[frozenset[str]] = frozenset(
    {
        TASK_KIND_JOB,
        TASK_KIND_UNKNOWN,
    }
)
HIDDEN_ROOT_TASK_KINDS: Final[frozenset[str]] = frozenset(
    {
        TASK_KIND_CALLBACK,
        TASK_KIND_CALLBACK_ERROR,
    }
)

TASK_RELATION_CHILD: Final = "child"
TASK_RELATION_CALLBACK: Final = "callback"
TASK_RELATION_CALLBACK_ERROR: Final = "callback_error"

TASK_KIND_PREFIX_CALLBACK_ERROR: Final = "loom.callback_error."
TASK_KIND_PREFIX_CALLBACK: Final = "loom.callback."
TASK_KIND_PREFIX_JOB: Final = "loom.job."

CANVAS_MARKER_KEY: Final = "__plywatch_canvas"
SCHEDULE_MARKER_KEY: Final = "__plywatch_schedule"
CANVAS_ROOT_PREFIX: Final = "canvas:"
