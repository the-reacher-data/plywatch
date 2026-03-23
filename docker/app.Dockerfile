FROM node:22-alpine AS web-builder

WORKDIR /app/apps/web

# Copy lockfile first to maximise layer cache reuse
COPY apps/web/package.json apps/web/package-lock.json ./

RUN npm ci --ignore-scripts

# Copy only build-time sources — no test configs, no playwright, no examples
COPY apps/web/svelte.config.js apps/web/tsconfig.json apps/web/vite.config.ts ./
COPY apps/web/postcss.config.cjs apps/web/tailwind.config.ts ./
COPY apps/web/src ./src
COPY apps/web/static ./static

RUN npm run build

# ── Runtime image ──────────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONFAULTHANDLER=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# Dedicated non-root user
RUN groupadd -r plywatch && useradd -r -g plywatch -s /sbin/nologin plywatch

# Install uv for fast dependency installation
COPY --from=ghcr.io/astral-sh/uv@sha256:72ab0aeb448090480ccabb99fb5f52b0dc3c71923bffb5e2e26517a1c27b7fec /uv /usr/local/bin/uv

# Copy only production source — lab and examples are excluded via .dockerignore
COPY apps/backend/pyproject.toml ./apps/backend/pyproject.toml
COPY apps/backend/src ./apps/backend/src
COPY apps/backend/config ./apps/backend/config

# Embed the pre-built frontend artifact
COPY --from=web-builder /app/apps/web/build ./apps/web/build

RUN --mount=type=cache,target=/root/.cache/uv,sharing=locked \
    uv pip install --system ./apps/backend

RUN chown -R plywatch:plywatch /app

USER plywatch

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')"

CMD ["uvicorn", "plywatch.main:app", \
     "--app-dir", "/app/apps/backend/src", \
     "--host", "0.0.0.0", "--port", "8080", \
     "--loop", "uvloop", "--http", "httptools", \
     "--proxy-headers", "--forwarded-allow-ips", "*", \
     "--no-server-header"]
