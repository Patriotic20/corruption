# syntax=docker/dockerfile:1

# ---------- build stage: resolve dependencies into a standalone venv ----------
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.9.18 /uv /bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /app

# only the lockfile layer — rebuilt when dependencies change, not on every code edit
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---------- runtime stage ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH"

# tini reaps zombies and forwards SIGTERM, so `docker compose stop` is graceful
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends tini; \
    rm -rf /var/lib/apt/lists/*; \
    groupadd --system app; \
    useradd --system --gid app --home-dir /app --no-create-home app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app . .

USER app

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "client_bot.main"]
