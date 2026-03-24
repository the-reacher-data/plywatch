"""Standalone traffic loop for generating sustained lab activity."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from itertools import cycle
from time import monotonic

from app.schemas import EmitRequest
from app.service import emit_scenario


@dataclass(frozen=True)
class ScenarioStep:
    """One traffic step in the sustained loop."""

    scenario: str
    count: int
    delay_seconds: int
    message_suffix: str


_DEFAULT_PLAN: tuple[ScenarioStep, ...] = (
    ScenarioStep("success", 2, 15, "success-default"),
    ScenarioStep("retry_success", 1, 12, "retry-success-default"),
    ScenarioStep("native_chord", 4, 15, "native-chord-default"),
    ScenarioStep("slow", 2, 75, "slow-queue"),
    ScenarioStep("parallel", 3, 15, "parallel-default"),
    ScenarioStep("native_group", 4, 15, "native-group-default"),
)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser for the sustained lab traffic loop."""
    parser = argparse.ArgumentParser(
        prog="plywatch-lab-traffic-loop",
        description="Emit sustained mixed traffic into the Plywatch lab.",
    )
    parser.add_argument("--duration-minutes", type=int, default=30)
    parser.add_argument("--interval-seconds", type=int, default=45)
    parser.add_argument("--message", default="30m traffic loop")
    return parser


async def run_traffic_loop(
    *,
    duration_minutes: int,
    interval_seconds: int,
    message: str,
) -> None:
    """Emit real lab traffic for a bounded period.

    Args:
        duration_minutes: Total duration of the loop.
        interval_seconds: Delay between wave dispatches.
        message: Prefix added to each dispatched scenario message.
    """
    deadline = monotonic() + max(duration_minutes, 1) * 60
    plan = cycle(_DEFAULT_PLAN)
    wave_index = 1

    while monotonic() < deadline:
        step = next(plan)
        request = EmitRequest(
            scenario=step.scenario,
            count=step.count,
            delay_seconds=step.delay_seconds,
            message=f"{message} / wave-{wave_index:02d} / {step.message_suffix}",
        )
        result = await emit_scenario(request)
        print(
            "lab.traffic_loop.dispatch",
            {
                "wave": wave_index,
                "scenario": step.scenario,
                "count": step.count,
                "delay_seconds": step.delay_seconds,
                "result": result,
            },
        )
        wave_index += 1
        remaining = deadline - monotonic()
        if remaining <= 0:
            break
        await asyncio.sleep(min(interval_seconds, remaining))


def main() -> None:
    """Run the sustained lab traffic loop CLI."""
    args = build_parser().parse_args()
    asyncio.run(
        run_traffic_loop(
            duration_minutes=args.duration_minutes,
            interval_seconds=args.interval_seconds,
            message=args.message,
        )
    )


if __name__ == "__main__":
    main()
