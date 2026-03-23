# Plywatch

[![CI](https://github.com/massivadatascope/plywatch/actions/workflows/ci-pr.yml/badge.svg?branch=main)](https://github.com/massivadatascope/plywatch/actions/workflows/ci-pr.yml)
[![Release](https://img.shields.io/github/v/release/massivadatascope/plywatch?sort=semver&color=blue)](https://github.com/massivadatascope/plywatch/releases/latest)
[![Container](https://img.shields.io/badge/ghcr.io-plywatch-0075C4?logo=docker&logoColor=white)](https://ghcr.io/massivadatascope/plywatch)
[![Python](https://img.shields.io/badge/python-3.11-informational?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/github/license/massivadatascope/plywatch)](LICENSE)

Ephemeral Celery monitoring with a self-contained, single-container deployment model. Built as an open-source alternative to Flower with a cleaner architecture and better UX.

## Quick start

```bash
docker run -p 8080:8080 \
  -e PLYWATCH_CELERY_BROKER_URL=redis://your-redis:6379/0 \
  ghcr.io/massivadatascope/plywatch:latest
```

Open `http://localhost:8080` to access the monitoring UI.

## What it does

- Live task monitoring via SSE
- Worker and queue visibility
- Bounded retention by age and task count
- Optional Redis-backed ephemeral state
- Single-pod deployment — no separate frontend server

## Architecture

```
┌────────────────────────────────────────────┐
│              plywatch container             │
│                                            │
│  ┌─────────────────┐  ┌─────────────────┐  │
│  │  FastAPI backend │  │  SvelteKit SPA  │  │
│  │  (loom-kernel)   │  │  (served static) │  │
│  └────────┬────────┘  └─────────────────┘  │
│           │ SSE + REST                      │
└───────────┼────────────────────────────────┘
            │
     ┌──────▼──────┐
     │  Celery +   │
     │   Broker    │
     └─────────────┘
```

## Configuration

All config is passed via environment variables or the YAML layer at `apps/backend/config/`:

| Variable | Description | Required |
|---|---|---|
| `PLYWATCH_CELERY_BROKER_URL` | Celery broker URL (`redis://...`) | ✓ |
| `PLYWATCH_CELERY_RESULT_BACKEND` | Result backend URL | ✓ |
| `PLYWATCH_CACHE_BACKEND` | Cache backend (`memory` or `redis`) | — |

## Repository layout

```text
apps/
  backend/         Python backend (FastAPI + loom-kernel)
    src/plywatch/  Production source
    config/        YAML config layers
    tests/         Pytest suite
  web/             SvelteKit frontend
    src/           Production source
docker/
  app.Dockerfile   Production multi-stage image
examples/          Bruno collections and local lab tooling
docs/
```

## Local development

Requires Docker and `make`.

```bash
make up       # start full local stack (redis + plywatch + lab producers)
make down
make rebuild
make smoke    # hit all health endpoints
make logs
```

The local stack exposes:

- Monitor UI and API → `http://127.0.0.1:8080`
- Lab producer API → `http://127.0.0.1:8090`
- RabbitMQ-backed monitor UI and API → `http://127.0.0.1:8081`
- RabbitMQ-backed lab producer API → `http://127.0.0.1:8091`
- RabbitMQ management UI → `http://127.0.0.1:15672`

```bash
make logs-plywatch   # plywatch container logs
make logs-producer   # producer-api logs
make logs-worker     # celery worker logs
make logs-plywatch-rabbit
make logs-producer-rabbit
make logs-worker-rabbit
make logs-rabbitmq
make logs-web        # frontend dev server logs (if running separately)
```

## Running tests

**Backend:**
```bash
uv run pytest
```

**Frontend:**
```bash
cd apps/web
npm ci
npm run check   # typecheck
npm run lint
npm test        # vitest unit tests
```

## Container image

Published to GHCR on every release:

```
ghcr.io/massivadatascope/plywatch:latest     # latest stable
ghcr.io/massivadatascope/plywatch:v1         # major track
ghcr.io/massivadatascope/plywatch:v1.2.3     # exact version
```

Multi-arch: `linux/amd64` + `linux/arm64`.

## CI/CD

| Workflow | Trigger | What it does |
|---|---|---|
| `ci-pr` | Pull request → `main` | Backend quality gate, frontend lint/test, SonarCloud scan, Docker build + Trivy scan, Snyk scan, changelog preview |
| `ci-main` | Push → `main` | Full test suite, coverage upload, SonarCloud scan, Snyk monitoring |
| `docs` | PR/push/docs dispatch | Build and publish documentation to GitHub Pages |
| `release` | Merged PR → `main` | Materialize version + changelog, build + push multi-arch image to GHCR, create git tag, create GitHub release |

Secrets used:

| Secret / Variable | Purpose |
|---|---|
| `CODECOV_TOKEN` | Coverage upload |
| `SNYK_TOKEN` | Dependency security scanning |
| `SONAR_TOKEN` + `SONAR_HOST_URL` | SonarCloud integration |
| `SONAR_PROJECT_KEY` (var) | SonarCloud project key |
