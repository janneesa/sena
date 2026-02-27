# syntax=docker/dockerfile:1.7

FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

COPY pyproject.toml README.md ./
COPY zenbot ./zenbot

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir .


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    WORKSPACE_ROOT=/workspace \
    OLLAMA_BASE_URL=http://host.docker.internal:11434

RUN groupadd --system --gid 10001 zenbot \
    && useradd --system --uid 10001 --gid 10001 --create-home zenbot

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY zenbot /app/zenbot
COPY config /app/config

RUN mkdir -p /workspace /tmp /run \
    && chown -R zenbot:zenbot /workspace /tmp /run

USER zenbot:zenbot

CMD ["python", "-m", "zenbot"]
