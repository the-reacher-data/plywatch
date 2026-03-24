"""Request models for the producer lab app."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class EmitRequest(BaseModel):
    """Request payload for emitting lab task scenarios."""

    scenario: Literal[
        "success",
        "failure",
        "retry",
        "retry_success",
        "slow",
        "scheduled",
        "parallel",
        "native_success",
        "native_chain",
        "native_group",
        "native_chord",
    ] = "success"
    count: int = Field(default=1, ge=1, le=50)
    with_callbacks: bool = True
    delay_seconds: int = Field(default=60, ge=1, le=120)
    message: str = "hello from plywatch lab"


class EmitSuiteRequest(BaseModel):
    """Request payload for emitting a predefined lab scenario suite."""

    suite: Literal[
        "loom_long",
        "native_graphs",
        "observe_all",
    ] = "observe_all"
    message: str = "hello from plywatch lab"
    delay_seconds: int = Field(default=45, ge=5, le=300)
