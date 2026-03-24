# Quickstart

`plywatch` monitors Celery activity without requiring a persistent application database.

## Security notice

Use Plywatch as an internal app.

- Do not publish the service directly on the public internet.
- Deploy behind an ingress/reverse proxy with authentication and TLS.
- Restrict access to trusted operator networks.

## What it is for

- live task monitoring
- worker visibility
- queue visibility
- quick operational inspection during development or runtime incidents

## Run with Docker

```bash
docker run -p 8080:8080 \
  -e PLYWATCH_CELERY_BROKER_URL=redis://your-redis:6379/0 \
  ghcr.io/massivadatascope/plywatch:latest
```

Open `http://127.0.0.1:8080`.

## Run locally

```bash
make up
make smoke
```

The default local lab exposes:

- monitor: `http://127.0.0.1:8080`
- producer API: `http://127.0.0.1:8090`
- rabbitmq monitor lab: `http://127.0.0.1:8081`
- rabbitmq producer lab: `http://127.0.0.1:8091`

## Related documentation

- Celery docs: <https://docs.celeryq.dev/>
- loom-py docs: <https://loom-py.readthedocs.io/en/latest/>
