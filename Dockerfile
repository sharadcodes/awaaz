FROM ghcr.io/astral-sh/uv:0.7.8-python3.12-bookworm-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN apt-get update \
    && apt-get install --yes --no-install-recommends calibre ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock* README.md ./
RUN uv sync --frozen --no-dev || uv sync --no-dev
COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv sync --no-dev

RUN useradd --create-home --uid 10001 awaaz \
    && mkdir -p /data \
    && chown -R awaaz:awaaz /app /data
USER awaaz

CMD ["/app/.venv/bin/uvicorn", "awaaz.main:app", "--host", "0.0.0.0", "--port", "8000"]
