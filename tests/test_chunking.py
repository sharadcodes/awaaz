import pytest

from awaaz.domain.chunking import ChunkingError, ChunkingMode, chunk_text


def test_paragraph_mode_preserves_paragraphs() -> None:
    assert chunk_text("First.\n\nSecond.", ChunkingMode.PARAGRAPH, 1_000) == [
        "First.",
        "Second.",
    ]


def test_paragraph_mode_one_chunk_per_paragraph_without_packing() -> None:
    # Multiple sentences in one paragraph stay together as a single chunk
    # even when they would fit individually under the limit.
    assert chunk_text("One. Two. Three.", ChunkingMode.PARAGRAPH, 1_000) == ["One. Two. Three."]


def test_paragraph_mode_never_splits_even_when_oversized() -> None:
    # The character limit is bypassed in non-character modes; an oversized
    # paragraph is sent as a single chunk regardless of the limit.
    assert chunk_text("Short. Also short.", ChunkingMode.PARAGRAPH, 12) == ["Short. Also short."]


def test_line_mode_ignores_empty_lines() -> None:
    assert chunk_text("one\n\n two ", ChunkingMode.LINE, 1_000) == ["one", "two"]


def test_line_mode_one_chunk_per_line_without_packing() -> None:
    assert chunk_text("alpha beta\ngamma delta", ChunkingMode.LINE, 1_000) == [
        "alpha beta",
        "gamma delta",
    ]


def test_line_mode_never_splits_even_when_oversized() -> None:
    assert chunk_text("alpha beta gamma delta", ChunkingMode.LINE, 10) == [
        "alpha beta gamma delta",
    ]


def test_sentence_mode_splits_at_sentence_boundaries() -> None:
    assert chunk_text("One. Two? Three!", ChunkingMode.SENTENCE, 1_000) == [
        "One.",
        "Two?",
        "Three!",
    ]


def test_sentence_mode_never_splits_even_when_oversized() -> None:
    assert chunk_text("alpha beta gamma delta", ChunkingMode.SENTENCE, 10) == [
        "alpha beta gamma delta",
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


def test_whole_mode_returns_single_chunk_regardless_of_size() -> None:
    # The character limit is bypassed in whole mode; the entire text is sent
    # as one chunk even when it exceeds the limit.
    assert chunk_text("too long for the limit", ChunkingMode.WHOLE, 4) == ["too long for the limit"]

