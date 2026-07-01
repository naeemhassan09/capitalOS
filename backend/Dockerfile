# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/venv/bin:$PATH"

WORKDIR /app

# Runtime system deps (libpq for psycopg2, curl for healthcheck).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# ---- builder: install python deps into a venv ----
FROM base AS builder
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN python -m venv /venv
COPY . /app
RUN pip install --upgrade pip && pip install ".[dev]"

# ---- runtime ----
FROM base AS runtime
COPY --from=builder /venv /venv
COPY . /app

# Non-root user; ensure upload dir exists and is writable.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/var/uploads \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/health/live || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
