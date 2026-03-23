# Celery Worker Observed Events

Observed on 2026-03-12 in the local `plywatch` lab stack.

## Scenarios Forced

- restart of the worker service
- scale up from 1 worker to 2 workers
- scale down back to 1 worker
- explicit stop of the extra worker container

## Confirmed Worker Event Types

- `worker-online`
- `worker-heartbeat`
- `worker-offline`

## Important Findings

- A normal worker restart produced the expected sequence:
  - `worker-heartbeat`
  - `worker-offline`
  - `worker-online`
  - `worker-heartbeat`
- Scaling from 1 to 2 workers produced:
  - `worker-online` for the new hostname
  - interleaved `worker-heartbeat` events for both hostnames
- Scaling down or explicitly stopping the extra worker did not reliably leave a visible `worker-offline` event in the retained raw buffer.
- Because of that, `WorkerSnapshot` must not rely only on `worker-offline`.
- We need a derived worker state based on heartbeat timeout:
  - `online`
  - `stale`
  - `offline`

## Model Implications

- Use `hostname` as the stable worker id.
- Persist `last_seen_at` from every heartbeat.
- Persist first `online_at` when `worker-online` appears.
- Track runtime stats from heartbeat payload:
  - `pid`
  - `freq`
  - `active`
  - `processed`
  - `loadavg`
  - `sw_ident`
  - `sw_ver`
  - `sw_sys`
- Mark a worker `stale` when heartbeat timeout is exceeded.
- Treat `worker-offline` as a strong signal when present, but not as a guaranteed signal.

## Representative Samples

### `worker-offline`

```json
{
  "capturedAt": "2026-03-12T16:15:08.271263+00:00",
  "eventType": "worker-offline",
  "payload": {
    "hostname": "celery@1b584e48cbea",
    "utcoffset": 0,
    "pid": 1,
    "clock": 8008,
    "freq": 2.0,
    "active": 0,
    "processed": 2,
    "loadavg": [1.14, 0.7, 0.71],
    "sw_ident": "py-celery",
    "sw_ver": "5.6.2",
    "sw_sys": "Linux",
    "timestamp": 1773332108.2702785,
    "type": "worker-offline",
    "local_received": 1773332108.27125
  },
  "hostname": "celery@1b584e48cbea"
}
```

### `worker-online`

```json
{
  "capturedAt": "2026-03-12T16:15:10.667447+00:00",
  "eventType": "worker-online",
  "payload": {
    "hostname": "celery@1b584e48cbea",
    "utcoffset": 0,
    "pid": 1,
    "clock": 1,
    "freq": 2.0,
    "active": 0,
    "processed": 0,
    "loadavg": [1.14, 0.7, 0.71],
    "sw_ident": "py-celery",
    "sw_ver": "5.6.2",
    "sw_sys": "Linux",
    "timestamp": 1773332110.665815,
    "type": "worker-online",
    "local_received": 1773332110.6674337
  },
  "hostname": "celery@1b584e48cbea"
}
```

### `worker-online` for second replica

```json
{
  "capturedAt": "2026-03-12T16:15:31.866365+00:00",
  "eventType": "worker-online",
  "payload": {
    "hostname": "celery@dd95b6468af4",
    "utcoffset": 0,
    "pid": 1,
    "clock": 55,
    "freq": 2.0,
    "active": 0,
    "processed": 0,
    "loadavg": [0.84, 0.66, 0.69],
    "sw_ident": "py-celery",
    "sw_ver": "5.6.2",
    "sw_sys": "Linux",
    "timestamp": 1773332131.8650248,
    "type": "worker-online",
    "local_received": 1773332131.8663585
  },
  "hostname": "celery@dd95b6468af4"
}
```

### Parallel `worker-heartbeat` from two workers

```json
[
  {
    "capturedAt": "2026-03-12T16:15:35.737366+00:00",
    "eventType": "worker-heartbeat",
    "payload": {
      "hostname": "celery@1b584e48cbea",
      "pid": 1,
      "clock": 69,
      "freq": 5,
      "sw_ident": "py-celery",
      "sw_ver": "5.6.2",
      "sw_sys": "Linux",
      "type": "worker-heartbeat"
    },
    "hostname": "celery@1b584e48cbea"
  },
  {
    "capturedAt": "2026-03-12T16:15:35.737213+00:00",
    "eventType": "worker-heartbeat",
    "payload": {
      "hostname": "celery@dd95b6468af4",
      "pid": 1,
      "clock": 69,
      "freq": 5,
      "sw_ident": "py-celery",
      "sw_ver": "5.6.2",
      "sw_sys": "Linux",
      "type": "worker-heartbeat"
    },
    "hostname": "celery@dd95b6468af4"
  }
]
```
