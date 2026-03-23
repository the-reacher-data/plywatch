"""Loom jobs used by the producer lab app."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any

from loom.core.command import Command
from loom.core.job.job import Job
from loom.core.use_case import Input


_RETRY_SUCCESS_ATTEMPTS: dict[str, int] = defaultdict(int)


class HelloJobCommand(Command, frozen=True):
    """Command payload accepted by the lab jobs."""

    scenario: str = "success"
    count: int = 1
    with_callbacks: bool = True
    delay_seconds: int = 60
    message: str = "hello from plywatch lab"


class HelloSuccessJob(Job[dict[str, Any]]):
    """Emit a successful task result."""

    __queue__ = "default"

    async def execute(self, cmd: HelloJobCommand = Input()) -> dict[str, Any]:
        return {"scenario": "success", "message": cmd.message}


class HelloFailureJob(Job[None]):
    """Emit a failed task."""

    __queue__ = "default"

    async def execute(self, cmd: HelloJobCommand = Input()) -> None:
        raise RuntimeError(f"lab failure: {cmd.message}")


class HelloRetryJob(Job[None]):
    """Emit a task that retries and finally exhausts retries."""

    __queue__ = "default"
    __retries__ = 2
    __countdown__ = 10

    async def execute(self, cmd: HelloJobCommand = Input()) -> None:
        raise RuntimeError(f"lab retry: {cmd.message}")


class HelloRetrySuccessJob(Job[dict[str, Any]]):
    """Emit a task that retries first and eventually succeeds."""

    __queue__ = "default"
    __retries__ = 2
    __countdown__ = 2

    async def execute(self, cmd: HelloJobCommand = Input()) -> dict[str, Any]:
        _RETRY_SUCCESS_ATTEMPTS[cmd.message] += 1
        attempt = _RETRY_SUCCESS_ATTEMPTS[cmd.message]
        if attempt <= self.__retries__:
            raise RuntimeError(f"lab retry-before-success attempt {attempt}: {cmd.message}")

        await asyncio.sleep(max(cmd.delay_seconds, 1))
        _RETRY_SUCCESS_ATTEMPTS.pop(cmd.message, None)
        return {
            "scenario": "retry_success",
            "attempts": attempt,
            "delay_seconds": cmd.delay_seconds,
            "message": cmd.message,
        }


class HelloSlowJob(Job[dict[str, Any]]):
    """Emit a slow successful task."""

    __queue__ = "slow"

    async def execute(self, cmd: HelloJobCommand = Input()) -> dict[str, Any]:
        await asyncio.sleep(max(cmd.delay_seconds, 1))
        return {"scenario": "slow", "delay_seconds": cmd.delay_seconds}
