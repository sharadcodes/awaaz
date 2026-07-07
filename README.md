# Awaaz

Local, API-first audiobook generator. Upload EPUB/TXT or submit text, edit extracted text,
create resumable synthesis jobs, and download MP3 output. TTS engines remain independent
REST services.

## Start

```bash
cp .env.example .env
docker compose up --build
```

- API: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`
- UI: `http://127.0.0.1:3000`

Start one optional local engine:

```bash
docker compose --profile supertonic up --build
docker compose --profile kokoro up
```

Inactive engine containers stay stopped. Change URLs/models/voices in `.env` when engines
run elsewhere. On Windows/macOS, use `host.docker.internal` for host services.

## Test

All development checks run inside Docker:

```bash
docker compose --profile test run --rm test
docker compose --profile test run --rm test uv run --group dev ruff check src tests
docker compose --profile test run --rm test uv run --group dev mypy src
docker compose --profile test run --rm frontend-test
```

See [API workflow](docs/api.md) and [architecture](docs/architecture.md).
