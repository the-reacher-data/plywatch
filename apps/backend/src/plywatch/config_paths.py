"""Configuration path helpers for the Plywatch backend."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Return the backend project root directory."""
    return Path(__file__).resolve().parents[2]


API_CONFIG_PATHS: tuple[str, ...] = (str(project_root() / "config" / "api.yaml"),)
