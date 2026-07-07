# API workflow

Create text: `POST /api/v1/documents`. Upload EPUB/TXT as multipart:
`POST /api/v1/documents/upload`. EPUB extraction uses Calibre `ebook-convert`.

Edit cleaned text:

```http
PUT /api/v1/documents/{document_id}/text
Content-Type: application/json

{"text":"Cleaned text","expected_revision":1}
```

Queue audiobook:

```http
POST /api/v1/documents/{document_id}/jobs
Content-Type: application/json

{"backend":"kokoro","voice":"af_bella","speed":1.0,"chunking_mode":"paragraph","character_limit":1000}
```

- Progress: `GET /api/v1/jobs/{job_id}`
- Live progress: `GET /api/v1/jobs/{job_id}/events`
- Chunks: `GET /api/v1/jobs/{job_id}/chunks`
- Controls: `POST /api/v1/jobs/{job_id}/pause|resume|cancel`
- Output: `GET /api/v1/jobs/{job_id}/download`

OpenAI-compatible short TTS: `POST /v1/audio/speech`. Audiobooks should use durable job API.
Select its upstream with `AWAAZ_OPENAI_BACKEND`. Frontends can discover non-secret engine
configuration using `GET /api/v1/backends`.
