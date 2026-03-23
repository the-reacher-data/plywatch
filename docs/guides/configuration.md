# Configuration

`plywatch` is configured through YAML files in `apps/backend/config/` plus environment variables.

## Main runtime variables

- `PLYWATCH_CELERY_BROKER_URL`
- `PLYWATCH_CELERY_RESULT_BACKEND`
- `PLYWATCH_CACHE_BACKEND`
- `PLYWATCH_RAW_EVENT_LIMIT`
- `PLYWATCH_MAX_TASKS`
- `PLYWATCH_MAX_COMPLETED_TASKS`
- `PLYWATCH_MAX_AGE_SECONDS`

## Common setup

```bash
export PLYWATCH_CELERY_BROKER_URL=redis://redis:6379/0
export PLYWATCH_CELERY_RESULT_BACKEND=redis://redis:6379/1
```

## RabbitMQ note

RabbitMQ works as a Celery broker for Plywatch monitoring. Some Celery canvas
patterns depend on the selected result backend. For example, `rpc://` does not
support chords.

That is a Celery limitation, not a Plywatch limitation.

## Deeper references

- Celery configuration: <https://docs.celeryq.dev/en/stable/userguide/configuration.html>
- Celery canvas: <https://docs.celeryq.dev/en/stable/userguide/canvas.html>
