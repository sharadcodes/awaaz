# Architecture

```text
future frontend -> FastAPI -> PostgreSQL queue/state <- async workers -> REST TTS server
                         |                                  |
                         +-> uploads                        +-> WAV chunks -> FFmpeg -> MP3
```

- API never imports inference engines.
- PostgreSQL owns durable document, job, and chunk state.
- Worker claims chunks with row locks. Default concurrency: one.
- Completed WAV chunks are checkpoints. Restart resumes abandoned chunks.
- Adapter protocol isolates OpenAI-compatible services.
- Supertonic and Kokoro containers use optional Compose profiles.

Chunk modes: paragraph, line, sentence, character-limited, whole text. Oversized text splits
first at sentence boundaries, then whitespace. Words are never split. Whole-text mode rejects
input above configured backend limit.

Job states: `queued`, `running`, `paused`, `failed`, `cancelled`, `completed`. Chunk states:
`pending`, `processing`, `failed`, `completed`. Worker startup resets abandoned `processing`
chunks to `pending`. Atomic file replacement prevents partial WAV checkpoints.
