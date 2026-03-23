# Celery Observed Events

Observed on 2026-03-12 in the local `plywatch` lab stack.

## Setup

- Broker: `redis://redis:6379/0`
- Result backend: `redis://redis:6379/1`
- Monitor API: `http://127.0.0.1:8080`
- Producer API: `http://127.0.0.1:8090`
- Worker task events: enabled

## Scenarios Emitted

- `success`
- `failure`
- `retry`
- `parallel`
- callbacks enabled for `success`, `failure`, `retry`

## Observed Event Types

- `worker-heartbeat`
- `task-sent`
- `task-received`
- `task-started`
- `task-succeeded`
- `task-failed`
- `task-retried`

Current sample counts from the retained raw buffer:

- `worker-heartbeat`: 460
- `task-sent`: 10
- `task-received`: 10
- `task-started`: 10
- `task-succeeded`: 6
- `task-failed`: 2
- `task-retried`: 2

## Important Findings

- Callback execution appears as independent Celery tasks:
  - `loom.callback.RecordSuccessCallback`
  - `loom.callback_error.RecordFailureCallback`
- Job execution appears with names like:
  - `loom.job.HelloSuccessJob`
  - `loom.job.HelloFailureJob`
  - `loom.job.HelloRetryJob`
- `task-sent` and `task-received` include the task `name`.
- `task-started`, `task-succeeded`, `task-failed`, and `task-retried` do not reliably include the task `name`.
- For monitoring, task identity must therefore be correlated by `uuid`, using earlier `task-sent` or `task-received` events.
- Retry attempts reuse the same task `uuid`.
- Retry scheduling is visible in `task-sent` via `eta`.
- Callback tasks inherit `root_id` and `parent_id` from the source job, which is useful for timeline grouping.

## Useful Fields By Event Type

### `worker-heartbeat`

Useful fields:

- `hostname`
- `pid`
- `clock`
- `freq`
- `active`
- `processed`
- `loadavg`
- `sw_ident`
- `sw_ver`
- `sw_sys`

Example:

```json
{"captured_at":"2026-03-12T12:41:16.877476+00:00","event_type":"worker-heartbeat","uuid":null,"hostname":"celery@b3d5810e88a8","payload":{"hostname":"celery@b3d5810e88a8","utcoffset":0,"pid":1,"clock":1357,"freq":5,"sw_ident":"py-celery","sw_ver":"5.6.2","sw_sys":"Linux","timestamp":1773319276.8766975,"type":"worker-heartbeat","local_received":1773319276.877462}}
```

### `task-sent`

Useful fields:

- `uuid`
- `name`
- `root_id`
- `parent_id`
- `queue`
- `routing_key`
- `retries`
- `eta`
- `kwargs`

Example:

```json
{"captured_at":"2026-03-12T12:38:55.212243+00:00","event_type":"task-sent","uuid":"9a21b4d7-ed57-47ab-b9f8-d3a9197c64ee","hostname":"gen10@b3d5810e88a8","payload":{"hostname":"gen10@b3d5810e88a8","utcoffset":0,"pid":10,"clock":8663,"uuid":"9a21b4d7-ed57-47ab-b9f8-d3a9197c64ee","root_id":"9a21b4d7-ed57-47ab-b9f8-d3a9197c64ee","parent_id":"9a21b4d7-ed57-47ab-b9f8-d3a9197c64ee","name":"loom.job.HelloRetryJob","args":"()","kwargs":"{'payload': {'scenario': 'retry', 'count': 1, 'with_callbacks': True, 'delay_seconds': 2, 'message': 'second retry'}, 'params': None, 'trace_id': None}","retries":2,"eta":"2026-03-12T12:38:57.209763+00:00","expires":null,"queue":"default","exchange":"","routing_key":"default","timestamp":1773319135.2114224,"type":"task-sent","local_received":1773319135.2122357}}
```

### `task-received`

Useful fields:

- `uuid`
- `name`
- `root_id`
- `parent_id`
- `retries`
- `eta`
- `kwargs`

Example:

```json
{"captured_at":"2026-03-12T12:38:55.213189+00:00","event_type":"task-received","uuid":"9a21b4d7-ed57-47ab-b9f8-d3a9197c64ee","hostname":"celery@b3d5810e88a8","payload":{"hostname":"celery@b3d5810e88a8","utcoffset":0,"pid":1,"clock":997,"uuid":"9a21b4d7-ed57-47ab-b9f8-d3a9197c64ee","name":"loom.job.HelloRetryJob","args":"()","kwargs":"{'payload': {'scenario': 'retry', 'count': 1, 'with_callbacks': True, 'delay_seconds': 2, 'message': 'second retry'}, 'params': None, 'trace_id': None}","root_id":"9a21b4d7-ed57-47ab-b9f8-d3a9197c64ee","parent_id":"9a21b4d7-ed57-47ab-b9f8-d3a9197c64ee","retries":2,"eta":"2026-03-12T12:38:57.209763+00:00","expires":null,"timestamp":1773319135.2123497,"type":"task-received","local_received":1773319135.2131822}}
```

### `task-started`

Useful fields:

- `uuid`
- `hostname`
- `timestamp`

Missing in this sample:

- task `name`
- queue

Example:

```json
{"captured_at":"2026-03-12T12:38:57.220540+00:00","event_type":"task-started","uuid":"9a21b4d7-ed57-47ab-b9f8-d3a9197c64ee","hostname":"celery@b3d5810e88a8","payload":{"hostname":"celery@b3d5810e88a8","utcoffset":0,"pid":1,"clock":1004,"uuid":"9a21b4d7-ed57-47ab-b9f8-d3a9197c64ee","timestamp":1773319137.219105,"type":"task-started","local_received":1773319137.2205176}}
```

### `task-succeeded`

Useful fields:

- `uuid`
- `result`
- `runtime`

Missing in this sample:

- task `name`

Example:

```json
{"captured_at":"2026-03-12T12:38:54.219508+00:00","event_type":"task-succeeded","uuid":"f49a9e8a-47a6-4276-aa51-fcaf18354021","hostname":"celery@b3d5810e88a8","payload":{"hostname":"celery@b3d5810e88a8","utcoffset":0,"pid":1,"clock":995,"uuid":"f49a9e8a-47a6-4276-aa51-fcaf18354021","result":"{'scenario': 'success', 'message': 'second parallel #0'}","runtime":0.0008559160050936043,"timestamp":1773319134.2193074,"type":"task-succeeded","local_received":1773319134.219507}}
```

### `task-failed`

Useful fields:

- `uuid`
- `exception`
- `traceback`

Missing in this sample:

- task `name`

Example:

```json
{"captured_at":"2026-03-12T12:38:54.206817+00:00","event_type":"task-failed","uuid":"08aecfe3-2dc1-4b57-866f-7a1fc8e92b9d","hostname":"celery@b3d5810e88a8","payload":{"hostname":"celery@b3d5810e88a8","utcoffset":0,"pid":1,"clock":984,"uuid":"08aecfe3-2dc1-4b57-866f-7a1fc8e92b9d","exception":"RuntimeError('lab failure: second failure')","traceback":"Traceback (most recent call last):\n  File \"/usr/local/lib/python3.11/site-packages/celery/app/trace.py\", line 479, in trace_task\n    R = retval = fun(*args, **kwargs)\n                 ^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.11/site-packages/celery/app/trace.py\", line 779, in __protected_call__\n    return self.run(*args, **kwargs)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.11/site-packages/loom/celery/runner.py\", line 224, in _job_task\n    result = _run_corout","timestamp":1773319134.2061815,"type":"task-failed","local_received":1773319134.206814}}
```

### `task-retried`

Useful fields:

- `uuid`
- `exception`
- `traceback`

Missing in this sample:

- task `name`
- next ETA

Example:

```json
{"captured_at":"2026-03-12T12:38:55.220849+00:00","event_type":"task-retried","uuid":"9a21b4d7-ed57-47ab-b9f8-d3a9197c64ee","hostname":"celery@b3d5810e88a8","payload":{"hostname":"celery@b3d5810e88a8","utcoffset":0,"pid":1,"clock":998,"uuid":"9a21b4d7-ed57-47ab-b9f8-d3a9197c64ee","exception":"RuntimeError('lab retry: second retry')","traceback":"Traceback (most recent call last):\n  File \"/usr/local/lib/python3.11/site-packages/loom/celery/runner.py\", line 224, in _job_task\n    result = _run_coroutine(\n             ^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.11/site-packages/loom/celery/runner.py\", line 104, in _run_coroutine\n    return WorkerEventLoop.run(coro, timeout=timeout)\n           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.11/site-packages/loom/celery/event_loop.py\", line 127, in run\n    return ","timestamp":1773319135.2200992,"type":"task-retried","local_received":1773319135.220843}}
```

## Suggested First Data Model Implications

- Keep one append-only raw event stream for debugging.
- Build a `TaskIndex` keyed by `uuid`.
- Hydrate stable fields like `name`, `queue`, `root_id`, `parent_id` from `task-sent` and `task-received`.
- Hydrate lifecycle timestamps from:
  - `task-sent`
  - `task-received`
  - `task-started`
  - terminal events: `task-succeeded`, `task-failed`
- Track retry count from repeated `task-retried` for the same `uuid`.
- Treat callbacks as first-class tasks, but expose a flag derived from name prefix:
  - `loom.callback.`
  - `loom.callback_error.`
