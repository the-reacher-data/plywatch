# App Producer Lab

Minimal Celery producer app for exercising Plywatch.

This lab provides:

- one FastAPI endpoint to emit different task scenarios
- one Celery worker using Loom jobs
- native Celery tasks for `chain`, `group`, and `chord` inspection
- success and failure callbacks
- parallel dispatch via `dispatch_parallel()`
- a standalone traffic loop CLI for sustained real activity

Main endpoint:

- `POST /lab/emit`
- `POST /lab/emit-suite`

Useful suites:

- `loom_long`
  - mixed Loom traffic with several long-running `slow` jobs
- `native_graphs`
  - native Celery `success`, `chain`, `group`, and `chord`
- `observe_all`
  - mixed Loom and native traffic for full-screen inspection

Example:

```bash
curl -X POST http://127.0.0.1:8090/lab/emit-suite \
  -H 'content-type: application/json' \
  -d '{"suite":"observe_all","delay_seconds":60,"message":"full monitor pass"}'
```

Sustained 30-minute loop:

```bash
cd examples/lab/app-producer
python -m app.traffic_loop --duration-minutes 30 --interval-seconds 45 --message "30m review"
```

The loop alternates real traffic waves across:

- `success`
- `retry_success`
- `native_chord`
- `slow`
- `parallel`
- `native_group`

This keeps traffic in both `default` and `slow` without introducing control-wrapper tasks.
