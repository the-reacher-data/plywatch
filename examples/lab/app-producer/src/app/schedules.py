"""Shared schedule metadata helpers for the lab producer."""

from __future__ import annotations

from dataclasses import dataclass


SCHEDULE_MARKER_KEY = "__plywatch_schedule"


@dataclass(frozen=True)
class ScheduleStamp:
    """Normalized schedule metadata stamped into Celery task kwargs."""

    schedule_id: str
    schedule_name: str
    schedule_pattern: str

    def as_kwargs_value(self) -> dict[str, str]:
        return {
            "id": self.schedule_id,
            "name": self.schedule_name,
            "pattern": self.schedule_pattern,
        }


def build_schedule_stamp(message: str, delay_seconds: int) -> ScheduleStamp:
    """Build a deterministic schedule stamp from a lab message."""

    normalized = "-".join(message.lower().split())
    return ScheduleStamp(
        schedule_id=f"schedule:{normalized}",
        schedule_name=f"Schedule {message}",
        schedule_pattern=f"every {delay_seconds}s",
    )
