# Configuration

`plywatch` loads configuration from YAML files in `apps/backend/config/` and every YAML value can be overridden with environment variables.

Security scope: this monitor is intended for internal/trusted environments. Expose it through an authenticated reverse proxy, not directly to the public internet.

Load order:

1. `api.yaml`
2. included layers: `base.yaml`, `cache.yaml`, `celery.yaml`
3. `oc.env` / `oc.decode` resolution from environment variables

## Common setup (production-safe baseline)

```bash
export PLYWATCH_CELERY_BROKER_URL=redis://redis:6379/0
export PLYWATCH_CELERY_RESULT_BACKEND=redis://redis:6379/1
export PLYWATCH_METRICS_ENABLED=true
export PLYWATCH_TRACE_ENABLED=true
export PLYWATCH_MAX_TASKS=5000
export PLYWATCH_MAX_COMPLETED_TASKS=50000
```

## Complex values format

Use JSON-like strings for list and null values because those keys use `oc.decode`.

```bash
# list
export PLYWATCH_RAW_EVENT_BUFFER_EXCLUDED_TYPES='["worker-heartbeat","task-sent"]'
export PLYWATCH_METRICS_ADAPTERS='["prometheus"]'

# null
export PLYWATCH_REST_DOCS_URL=null
export PLYWATCH_REST_REDOC_URL=null
```

## YAML keys and env variables

### `base.yaml` (`app`, `logger`)

| YAML key | Environment variable | Default |
|---|---|---|
| `app.name` | `PLYWATCH_APP_NAME` | `plywatch` |
| `app.code_path` | `PLYWATCH_CODE_PATH` | `../src` |
| `app.discovery.mode` | `PLYWATCH_DISCOVERY_MODE` | `manifest` |
| `app.discovery.manifest.module` | `PLYWATCH_DISCOVERY_MANIFEST_MODULE` | `app.manifest` |
| `app.rest.backend` | `PLYWATCH_REST_BACKEND` | `fastapi` |
| `app.rest.title` | `PLYWATCH_REST_TITLE` | `Plywatch API` |
| `app.rest.version` | `PLYWATCH_REST_VERSION` | `0.1.0` |
| `app.rest.docs_url` | `PLYWATCH_REST_DOCS_URL` | `"/docs"` |
| `app.rest.redoc_url` | `PLYWATCH_REST_REDOC_URL` | `"/redoc"` |
| `logger.name` | `PLYWATCH_LOGGER_NAME` | `plywatch` |
| `logger.environment` | `PLYWATCH_ENVIRONMENT` | `dev` |
| `logger.renderer` | `PLYWATCH_LOG_RENDERER` (fallback: `LOG_RENDERER`) | `console` |
| `logger.colors` | `PLYWATCH_LOG_COLORS` (fallback: `LOG_COLORS`) | `true` |
| `logger.level` | `PLYWATCH_LOG_LEVEL` (fallback: `LOG_LEVEL`) | `INFO` |
| `logger.named_levels.celery` | `PLYWATCH_LOG_LEVEL_CELERY` | `WARNING` |
| `logger.named_levels.kombu` | `PLYWATCH_LOG_LEVEL_KOMBU` | `WARNING` |
| `logger.named_levels.amqp` | `PLYWATCH_LOG_LEVEL_AMQP` | `WARNING` |
| `logger.named_levels.redis` | `PLYWATCH_LOG_LEVEL_REDIS` | `WARNING` |

### `api.yaml` (`trace`, `metrics`, `monitor`)

| YAML key | Environment variable | Default |
|---|---|---|
| `trace.enabled` | `PLYWATCH_TRACE_ENABLED` (fallback: `TRACE_ENABLED`) | `true` |
| `trace.header` | `PLYWATCH_TRACE_HEADER` | `x-request-id` |
| `metrics.enabled` | `PLYWATCH_METRICS_ENABLED` (fallback: `METRICS_ENABLED`) | `true` |
| `metrics.path` | `PLYWATCH_METRICS_PATH` (fallback: `METRICS_PATH`) | `/metrics` |
| `metrics.adapters` | `PLYWATCH_METRICS_ADAPTERS` | `["prometheus"]` |
| `monitor.raw_event_limit` | `PLYWATCH_RAW_EVENT_LIMIT` | `500` |
| `monitor.raw_event_buffer_excluded_types` | `PLYWATCH_RAW_EVENT_BUFFER_EXCLUDED_TYPES` | `["worker-heartbeat"]` |
| `monitor.max_tasks` | `PLYWATCH_MAX_TASKS` | `2000` |
| `monitor.max_completed_tasks` | `PLYWATCH_MAX_COMPLETED_TASKS` | `20000` |
| `monitor.max_schedule_runs` | `PLYWATCH_MAX_SCHEDULE_RUNS` | `5000` |
| `monitor.max_age_seconds` | `PLYWATCH_MAX_AGE_SECONDS` | `21600` |
| `monitor.worker_stale_after_seconds` | `PLYWATCH_WORKER_STALE_AFTER_SECONDS` | `15` |
| `monitor.task_lost_after_seconds` | `PLYWATCH_TASK_LOST_AFTER_SECONDS` | `1800` |
| `monitor.task_liveness_reconcile_interval_seconds` | `PLYWATCH_TASK_LIVENESS_RECONCILE_INTERVAL_SECONDS` | `30` |

### `celery.yaml` (`celery`)

| YAML key | Environment variable | Default |
|---|---|---|
| `celery.broker_url` | `PLYWATCH_CELERY_BROKER_URL` | `redis://redis:6379/0` |
| `celery.result_backend` | `PLYWATCH_CELERY_RESULT_BACKEND` | `redis://redis:6379/1` |
| `celery.worker_concurrency` | `PLYWATCH_CELERY_WORKER_CONCURRENCY` | `2` |
| `celery.worker_prefetch_multiplier` | `PLYWATCH_CELERY_PREFETCH_MULTIPLIER` | `1` |
| `celery.worker_max_tasks_per_child` | `PLYWATCH_CELERY_MAX_TASKS_PER_CHILD` | `100` |
| `celery.task_always_eager` | `PLYWATCH_CELERY_TASK_ALWAYS_EAGER` | `false` |
| `celery.timezone` | `PLYWATCH_CELERY_TIMEZONE` | `UTC` |
| `celery.enable_utc` | `PLYWATCH_CELERY_ENABLE_UTC` | `true` |
| `celery.task_serializer` | `PLYWATCH_CELERY_TASK_SERIALIZER` | `json` |
| `celery.result_serializer` | `PLYWATCH_CELERY_RESULT_SERIALIZER` | `json` |
| `celery.accept_content` | `PLYWATCH_CELERY_ACCEPT_CONTENT` | `["json"]` |

### `cache.yaml` (`cache`)

| YAML key | Environment variable | Default |
|---|---|---|
| `cache.enabled` | `PLYWATCH_CACHE_ENABLED` | `true` |
| `cache.aiocache_alias` | `PLYWATCH_CACHE_AIOCACHE_ALIAS` | `default` |
| `cache.counter_alias` | `PLYWATCH_CACHE_COUNTER_ALIAS` | `counters` |
| `cache.default_ttl` | `PLYWATCH_MAX_AGE_SECONDS` | `21600` |
| `cache.default_list_ttl` | `PLYWATCH_MAX_AGE_SECONDS` | `21600` |
| `cache.aiocache.default.cache` | `PLYWATCH_CACHE_DEFAULT_BACKEND` | `aiocache.SimpleMemoryCache` |
| `cache.aiocache.default.serializer.class` | `PLYWATCH_CACHE_DEFAULT_SERIALIZER` | `loom.core.cache.serializer.MsgspecSerializer` |
| `cache.aiocache.counters.cache` | `PLYWATCH_CACHE_COUNTER_BACKEND` | `aiocache.SimpleMemoryCache` |

## RabbitMQ note

RabbitMQ works as a Celery broker for Plywatch monitoring. Some Celery canvas patterns depend on the selected result backend. For example, `rpc://` does not support chords.

## Deeper references

- Celery configuration: <https://docs.celeryq.dev/en/stable/userguide/configuration.html>
- Celery canvas: <https://docs.celeryq.dev/en/stable/userguide/canvas.html>
