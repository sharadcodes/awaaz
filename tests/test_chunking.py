import pytest

from awaaz.domain.chunking import ChunkingError, ChunkingMode, chunk_text


def test_paragraph_mode_preserves_paragraphs() -> None:
    assert chunk_text("First.\n\nSecond.", ChunkingMode.PARAGRAPH, 1_000) == [
        "First.",
        "Second.",
    ]


def test_line_mode_ignores_empty_lines() -> None:
    assert chunk_text("one\n\n two ", ChunkingMode.LINE, 1_000) == ["one", "two"]


def test_sentence_mode_splits_at_sentence_boundaries() -> None:
    assert chunk_text("One. Two? Three!", ChunkingMode.SENTENCE, 1_000) == [
        "One.",
        "Two?",
        "Three!",
    ]


def test_character_mode_packs_sentences_without_exceeding_limit() -> None:
    chunks = chunk_text("One short. Two short. Last.", ChunkingMode.CHARACTER, 21)
    assert chunks == ["One short. Two short.", "Last."]
    assert all(len(chunk) <= 21 for chunk in chunks)


def test_character_mode_splits_long_sentence_only_at_whitespace() -> None:
    chunks = chunk_text("alpha beta gamma delta", ChunkingMode.CHARACTER, 10)
    assert chunks == ["alpha beta", "gamma", "delta"]


def test_character_mode_rejects_word_longer_than_limit() -> None:
    with pytest.raises(ChunkingError, match="word exceeds"):
        chunk_text("extraordinary", ChunkingMode.CHARACTER, 5)


def test_whole_mode_rejects_oversized_text() -> None:
    with pytest.raises(ChunkingError, match="whole text exceeds"):
        chunk_text("too long", ChunkingMode.WHOLE, 4)

