"""FastAPI entrypoint for the lab producer app."""

from __future__ import annotations

from fastapi import FastAPI

from app.schemas import EmitRequest, EmitSuiteRequest
from app.service import emit_scenario, emit_suite

app = FastAPI(title="Plywatch Lab Producer", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    """Health probe."""
    return {"status": "ok"}


@app.post("/lab/emit")
async def emit(request: EmitRequest) -> dict[str, object]:
    """Emit one task scenario for monitor testing."""
    return await emit_scenario(request)


@app.post("/lab/emit-suite")
async def emit_lab_suite(request: EmitSuiteRequest) -> dict[str, object]:
    """Emit one predefined scenario suite for richer inspection."""
    return await emit_suite(request)
