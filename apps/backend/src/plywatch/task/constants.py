"""Shared task-domain constants to avoid stringly-typed branching."""

from __future__ import annotations

from enum import StrEnum
from typing import Final, Literal, TypeAlias


class TaskEvent(StrEnum):
    SENT = "task-sent"
    RECEIVED = "task-received"
    STARTED = "task-started"
    RETRIED = "task-retried"
    SUCCEEDED = "task-succeeded"
    FAILED = "task-failed"


class TaskState(StrEnum):
    SENT = "sent"
    RECEIVED = "received"
    STARTED = "started"
    RETRYING = "retrying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    LOST = "lost"


class TaskSection(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TaskKind(StrEnum):
    JOB = "job"
    CALLBACK = "callback"
    CALLBACK_ERROR = "callback_error"
    UNKNOWN = "unknown"


class TaskRelation(StrEnum):
    CHILD = "child"
    CALLBACK = "callback"
    CALLBACK_ERROR = "callback_error"


class CanvasKind(StrEnum):
    CHAIN = "chain"
    GROUP = "group"
    CHORD = "chord"


class CanvasRole(StrEnum):
    HEAD = "head"
    TAIL = "tail"
    MEMBER = "member"
    HEADER = "header"
    BODY = "body"


TASK_EVENT_PREFIX: Final = "task-"
TASK_EVENT_SENT: Final = TaskEvent.SENT.value
TASK_EVENT_RECEIVED: Final = TaskEvent.RECEIVED.value
TASK_EVENT_STARTED: Final = TaskEvent.STARTED.value
TASK_EVENT_RETRIED: Final = TaskEvent.RETRIED.value
TASK_EVENT_SUCCEEDED: Final = TaskEvent.SUCCEEDED.value
TASK_EVENT_FAILED: Final = TaskEvent.FAILED.value
TASK_EVENT_LOST: Final = "task-lost"

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
TASK_TERMINAL_EVENTS: Final[frozenset[str]] = frozenset(
    {
        TASK_EVENT_SUCCEEDED,
        TASK_EVENT_FAILED,
        TASK_EVENT_RETRIED,
        TASK_EVENT_LOST,
    }
)

TASK_STATE_SENT: Final = TaskState.SENT.value
TASK_STATE_RECEIVED: Final = TaskState.RECEIVED.value
TASK_STATE_STARTED: Final = TaskState.STARTED.value
TASK_STATE_RETRYING: Final = TaskState.RETRYING.value
TASK_STATE_SUCCEEDED: Final = TaskState.SUCCEEDED.value
TASK_STATE_FAILED: Final = TaskState.FAILED.value
TASK_STATE_LOST: Final = TaskState.LOST.value

TaskStateName: TypeAlias = Literal[
    "sent",
    "received",
    "started",
    "retrying",
    "succeeded",
    "failed",
    "lost",
]

TASK_SECTION_QUEUED: Final = TaskSection.QUEUED.value
TASK_SECTION_RUNNING: Final = TaskSection.RUNNING.value
TASK_SECTION_SUCCEEDED: Final = TaskSection.SUCCEEDED.value
TASK_SECTION_FAILED: Final = TaskSection.FAILED.value

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
ACTIVE_TASK_STATES: Final[frozenset[TaskStateName]] = frozenset(
    {
        TASK_STATE_RECEIVED,
        TASK_STATE_STARTED,
        TASK_STATE_RETRYING,
    }
)
FAILED_TASK_STATES: Final[frozenset[TaskStateName]] = frozenset(
    {
        TASK_STATE_FAILED,
        TASK_STATE_LOST,
    }
)
LOST_CANDIDATE_STATES: Final[frozenset[TaskStateName]] = frozenset(
    {
        TASK_STATE_RECEIVED,
        TASK_STATE_STARTED,
    }
)

TASK_KIND_JOB: Final = TaskKind.JOB.value
TASK_KIND_CALLBACK: Final = TaskKind.CALLBACK.value
TASK_KIND_CALLBACK_ERROR: Final = TaskKind.CALLBACK_ERROR.value
TASK_KIND_UNKNOWN: Final = TaskKind.UNKNOWN.value

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

TASK_RELATION_CHILD: Final = TaskRelation.CHILD.value
TASK_RELATION_CALLBACK: Final = TaskRelation.CALLBACK.value
TASK_RELATION_CALLBACK_ERROR: Final = TaskRelation.CALLBACK_ERROR.value

TASK_KIND_PREFIX_CALLBACK_ERROR: Final = "loom.callback_error."
TASK_KIND_PREFIX_CALLBACK: Final = "loom.callback."
TASK_KIND_PREFIX_JOB: Final = "loom.job."

CANVAS_KIND_CHAIN: Final = CanvasKind.CHAIN.value
CANVAS_KIND_GROUP: Final = CanvasKind.GROUP.value
CANVAS_KIND_CHORD: Final = CanvasKind.CHORD.value
CANVAS_KINDS: Final[frozenset[str]] = frozenset({CANVAS_KIND_CHAIN, CANVAS_KIND_GROUP, CANVAS_KIND_CHORD})

CANVAS_ROLE_HEAD: Final = CanvasRole.HEAD.value
CANVAS_ROLE_TAIL: Final = CanvasRole.TAIL.value
CANVAS_ROLE_MEMBER: Final = CanvasRole.MEMBER.value
CANVAS_ROLE_HEADER: Final = CanvasRole.HEADER.value
CANVAS_ROLE_BODY: Final = CanvasRole.BODY.value

CANVAS_MARKER_KEY: Final = "__plywatch_canvas"
SCHEDULE_MARKER_KEY: Final = "__plywatch_schedule"
CANVAS_ROOT_PREFIX: Final = "canvas:"
