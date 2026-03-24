from __future__ import annotations

import pytest

from plywatch.main import _is_reserved_operational_path


@pytest.mark.parametrize(
    ("path", "metrics_path", "expected"),
    (
        ("metrics", "/metrics", True),
        ("metrics/sub", "/metrics", True),
        ("api", "/metrics", True),
        ("api/tasks", "/metrics", True),
        ("health", "/metrics", True),
        ("docs", "/metrics", True),
        ("redoc", "/metrics", True),
        ("openapi.json", "/metrics", True),
        ("tasks", "/metrics", False),
        ("workers", "/metrics", False),
        ("events/live", "/metrics", False),
        ("internal/metrics", "/internal/metrics", True),
        ("internal/metrics/scrape", "/internal/metrics", True),
        ("metrics", "/internal/metrics", False),
    ),
)
def test_is_reserved_operational_path(path: str, metrics_path: str, expected: bool) -> None:
    assert _is_reserved_operational_path(path, metrics_path=metrics_path) is expected
