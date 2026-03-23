"""Config path helpers for the producer lab app."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    """Return producer project root."""
    return Path(__file__).resolve().parents[2]


def resolve_config_path(relative_path: str) -> str:
    """Resolve a config path relative to the project root."""
    return str(project_root() / relative_path)


API_CONFIG_PATHS: tuple[str, ...] = (resolve_config_path("config/api.yaml"),)
WORKER_CONFIG_PATHS: tuple[str, ...] = (resolve_config_path("config/worker.yaml"),)
