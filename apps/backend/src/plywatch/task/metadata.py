"""Metadata extraction helpers for task lifecycle events."""

from __future__ import annotations

import ast
from typing import Final, TypedDict

from plywatch.shared.raw_events import JsonValue
from plywatch.task.constants import CANVAS_MARKER_KEY, SCHEDULE_MARKER_KEY
from plywatch.task.models import CanvasKind, CanvasRole

_CANVAS_KIND_BY_VALUE: Final[dict[str, CanvasKind]] = {
    "chain": "chain",
    "group": "group",
    "chord": "chord",
}
_CANVAS_ROLE_BY_VALUE: Final[dict[str, CanvasRole]] = {
    "head": "head",
    "tail": "tail",
    "member": "member",
    "header": "header",
    "body": "body",
}


class CanvasMetadata(TypedDict):
    kind: CanvasKind
    id: str
    role: CanvasRole | None


def extract_canvas_metadata(payload: dict[str, JsonValue]) -> CanvasMetadata | None:
    """Extract stamped canvas metadata from a Celery event payload."""

    parsed = parse_kwargs_mapping(payload)
    if parsed is None:
        return None
    canvas_value = parsed.get(CANVAS_MARKER_KEY)
    if not isinstance(canvas_value, dict):
        return None

    kind = _canvas_kind(canvas_value.get("kind"))
    canvas_id = canvas_value.get("id")
    role = _canvas_role(canvas_value.get("role"))
    if kind is None or not isinstance(canvas_id, str):
        return None

    normalized: CanvasMetadata = {
        "kind": kind,
        "id": canvas_id,
        "role": role,
    }
    return normalized


def extract_schedule_metadata(payload: dict[str, JsonValue]) -> dict[str, str] | None:
    """Extract stamped schedule metadata from task kwargs."""

    parsed = parse_kwargs_mapping(payload)
    if parsed is None:
        return None
    schedule_value = parsed.get(SCHEDULE_MARKER_KEY)
    if not isinstance(schedule_value, dict):
        return None

    schedule_id = schedule_value.get("id")
    schedule_name = schedule_value.get("name")
    schedule_pattern = schedule_value.get("pattern")
    if not isinstance(schedule_id, str) or not isinstance(schedule_name, str):
        return None

    normalized: dict[str, str] = {"id": schedule_id, "name": schedule_name}
    if isinstance(schedule_pattern, str):
        normalized["pattern"] = schedule_pattern
    return normalized


def extract_eta(payload: dict[str, JsonValue]) -> str | None:
    """Extract the Celery ETA string when present."""

    eta_value = payload.get("eta")
    return eta_value if isinstance(eta_value, str) else None


def parse_kwargs_mapping(payload: dict[str, JsonValue]) -> dict[str, JsonValue] | None:
    """Parse the stringified Celery kwargs mapping when present."""

    kwargs_value = payload.get("kwargs")
    if not isinstance(kwargs_value, str):
        return None
    try:
        parsed = ast.literal_eval(kwargs_value)
    except (SyntaxError, ValueError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _canvas_kind(value: object) -> CanvasKind | None:
    return _CANVAS_KIND_BY_VALUE.get(value) if isinstance(value, str) else None


def _canvas_role(value: object) -> CanvasRole | None:
    return _CANVAS_ROLE_BY_VALUE.get(value) if isinstance(value, str) else None
