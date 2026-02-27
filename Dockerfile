# syntax=docker/dockerfile:1.7

FROM python:3.13-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

COPY pyproject.toml README.md ./
COPY sena ./sena

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir .


FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    WORKSPACE_ROOT=/workspace \
    OLLAMA_BASE_URL=http://host.docker.internal:11434

RUN groupadd --system --gid 10001 sena \
    && useradd --system --uid 10001 --gid 10001 --create-home sena

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY sena /app/sena
COPY config /app/config

RUN mkdir -p /workspace /tmp /run \
    && chown -R sena:sena /workspace /tmp /run

USER sena:sena

CMD ["python", "-m", "sena"]
