# Architecture

`plywatch` is a monitor application built on top of `loom-kernel`.

## High-level shape

- FastAPI backend
- embedded static frontend
- Celery event consumer
- in-memory projections for tasks, workers, queues, and schedules
- optional ephemeral cache backend

## What Plywatch does not try to be

- it is not a workflow engine
- it is not a persistent business database
- it does not replace Celery broker semantics

## Internal model conventions

- default: internal DTOs and projection/value models use `LoomStruct`
- justified exceptions:
  - wiring-only runtime containers (`MonitorRuntime`, `RuntimeRepositories`)
  - mutable local repository bookkeeping state (`_TrackedTask`)

## Related references

- repository overview in [docs overview](../README.md)
- loom-py architecture docs: <https://loom-py.readthedocs.io/en/latest/architecture/overview.html>
- Celery monitoring guide: <https://docs.celeryq.dev/en/stable/userguide/monitoring.html>
