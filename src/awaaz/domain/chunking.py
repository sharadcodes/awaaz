import re
from enum import StrEnum


class ChunkingError(ValueError):
    """Text cannot be chunked under requested constraints."""


class ChunkingMode(StrEnum):
    PARAGRAPH = "paragraph"
    LINE = "line"
    SENTENCE = "sentence"
    CHARACTER = "character"
    WHOLE = "whole"


_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_PARAGRAPH_BOUNDARY = re.compile(r"\n\s*\n+")


def _normalize(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").strip()


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in _SENTENCE_BOUNDARY.split(text) if part.strip()]


def _split_at_words(text: str, limit: int) -> list[str]:
    words = text.split()
    if any(len(word) > limit for word in words):
        raise ChunkingError(f"word exceeds character limit of {limit}")
    chunks: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= limit:
            current = candidate
        else:
            chunks.append(current)
            current = word
    if current:
        chunks.append(current)
    return chunks


def _pack(parts: list[str], limit: int) -> list[str]:
    expanded: list[str] = []
    for part in parts:
        expanded.extend([part] if len(part) <= limit else _split_at_words(part, limit))
    chunks: list[str] = []
    current = ""
    for part in expanded:
        candidate = f"{current} {part}".strip()
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                chunks.append(current)
            current = part
    if current:
        chunks.append(current)
    return chunks


def chunk_text(text: str, mode: ChunkingMode, character_limit: int) -> list[str]:
    if character_limit < 1:
        raise ChunkingError("character limit must be positive")
    normalized = _normalize(text)
    if not normalized:
        raise ChunkingError("text cannot be empty")
    if mode is ChunkingMode.WHOLE:
        return [normalized]
    if mode is ChunkingMode.LINE:
        return [line.strip() for line in normalized.splitlines() if line.strip()]
    if mode is ChunkingMode.PARAGRAPH:
        return [part.strip() for part in _PARAGRAPH_BOUNDARY.split(normalized) if part.strip()]
    if mode is ChunkingMode.SENTENCE:
        return _sentences(normalized)
    return _pack(_sentences(normalized), character_limit)
