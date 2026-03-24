# Backend

Backend service for Plywatch.

Responsibilities:

- ingest Celery events
- keep ephemeral task, worker and queue state
- expose read-only APIs
- expose SSE updates
- prepare the surface for future operator actions

Operational direction:

- one FastAPI backend app
- YAML config inspired by `dummy-loom`
- no worker bootstrap in this repository root
- monitor Celery, do not behave like the monitored app
