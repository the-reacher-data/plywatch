# Plywatch Loom Reuse Analysis

## Goal

Build `plywatch` as a Loom-native monitoring product without forcing the SQLAlchemy repository stack where it does not fit the problem.

## What We Reuse From `loom-py`

- `UseCase`
- `RestInterface`
- `Response` for public API outputs
- `Command` for future API inputs
- DI container and `Scope.APPLICATION`
- `create_kernel(...)`
- `create_fastapi_app(...)`
- YAML-based configuration loading
- logging, tracing, metrics middleware
- Celery config creation

## What We Do Not Force

- `BaseModel` as the main shape of task snapshots
- `RepoFor[Model]`
- SQLAlchemy repositories
- Unit of Work for monitor reads
- autocrud

Reason:

`plywatch` is not a CRUD app over persisted domain entities. It is an event-driven projection service that materializes transient task state from Celery events.

## Current Recommended Architecture

### Infrastructure

- `CeleryEventConsumer`
- `RawEventStore`
- `TaskProjector`

### Application

- `GetOverviewUseCase`
- `ListRawEventsUseCase`
- `ListTasksUseCase`
- `GetTaskUseCase`
- `GetTaskTimelineUseCase`

### REST

- `MonitorRestInterface`
- `TaskRestInterface`

### Repository Layer

- `TaskSnapshotRepository` as a custom read repository contract
- initial implementation: `InMemoryTaskSnapshotRepository`

This repository is registered in Loom DI as an application singleton.

## Why Not Use SQLAlchemy Repositories Now

The SQLAlchemy repository stack in Loom is strong when the application owns persisted `BaseModel` entities and wants:

- `RepoFor[Model]`
- `LoadById`
- query specs
- UoW transactions
- autocrud

`plywatch` currently wants:

- ephemeral state
- derived projections
- graph relationships from event metadata
- single-pod operation
- optional future `aiocache` / Redis backend

That makes a custom repository contract the right fit.

## How To Evolve Later

Keep the contract stable:

- `TaskSnapshotRepository`

Add implementations later:

- `InMemoryTaskSnapshotRepository`
- `AiocacheTaskSnapshotRepository`
- `RedisTaskSnapshotRepository`
- `SqlAlchemyTaskSnapshotRepository` if persistence becomes a product requirement

This lets `plywatch` stay Loom-native at the application/API layer while keeping storage flexible.

## Decision

Use Loom for:

- API contracts
- use cases
- interfaces
- DI
- bootstrap

Use custom monitor infrastructure for:

- event ingestion
- projection
- ephemeral snapshot storage

This is the cleanest integration point with `loom-py` for `plywatch`.
