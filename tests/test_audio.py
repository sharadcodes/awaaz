import wave
from pathlib import Path

import pytest

from awaaz.domain.exceptions import AudioAssemblyError
from awaaz.services.audio import assemble_mp3


def _write_silence(path: Path) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24_000)
        output.writeframes(b"\x00\x00" * 2_400)


@pytest.mark.asyncio
async def test_ffmpeg_assembles_wav_chunks_into_mp3(tmp_path: Path) -> None:
    first = tmp_path / "first.wav"
    second = tmp_path / "second.wav"
    _write_silence(first)
    _write_silence(second)
    target = tmp_path / "book.mp3"

    await assemble_mp3([first, second], target)

    assert target.stat().st_size > 0


@pytest.mark.asyncio
async def test_assembly_fails_before_ffmpeg_for_missing_chunk(tmp_path: Path) -> None:
    with pytest.raises(AudioAssemblyError, match="must exist"):
        await assemble_mp3([tmp_path / "missing.wav"], tmp_path / "book.mp3")

