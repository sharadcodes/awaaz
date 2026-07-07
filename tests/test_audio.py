import wave
from pathlib import Path

import pytest

from awaaz.domain.exceptions import AudioAssemblyError
from awaaz.services.audio import _apply_wav_fades, assemble_mp3


def _write_silence(path: Path) -> None:
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24_000)
        output.writeframes(b"\x00\x00" * 2_400)


def _write_clicky(path: Path, amp: int = 16000) -> None:
    """Write a WAV that starts and ends at full amplitude (guaranteed click)."""
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(24_000)
        sample = (amp).to_bytes(2, byteorder="little", signed=True)
        output.writeframes(sample * 2_400)


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


def test_apply_wav_fades_zeroes_first_and_last_samples(tmp_path: Path) -> None:
    """Fades must ramp the first and last samples to zero to eliminate clicks."""
    src = tmp_path / "chunk.wav"
    dst = tmp_path / "faded.wav"
    _write_clicky(src)

    _apply_wav_fades(src, dst)

    with wave.open(str(dst), "rb") as wav:
        frames = wav.readframes(wav.getnframes())

    import array

    arr = array.array("h")
    arr.frombytes(frames)
    assert arr[0] == 0, "first sample must be zeroed by fade-in"
    assert arr[-1] == 0, "last sample must be zeroed by fade-out"
    # Middle samples should be untouched
    mid = len(arr) // 2
    assert arr[mid] != 0, "middle samples should retain full amplitude"
