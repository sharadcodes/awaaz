import array
import asyncio
import shutil
import wave
from pathlib import Path

import aiofiles

from awaaz.domain.exceptions import AudioAssemblyError

_FADE_SAMPLES = 120  # ~5 ms at 24 kHz — eliminates boundary clicks


def _apply_wav_fades(src: Path, dst: Path) -> None:
    """Copy a WAV file applying short linear fade-in and fade-out.

    This eliminates the audible click/snapping sound at chunk boundaries
    caused by waveform discontinuities (last sample of one chunk != first
    sample of the next).
    """
    with wave.open(str(src), "rb") as wav:
        n_channels = wav.getnchannels()
        sampwidth = wav.getsampwidth()
        framerate = wav.getframerate()
        raw = wav.readframes(wav.getnframes())

    # NOTE: some TTS engines (e.g. kokoro) write bogus frame counts in the
    # WAV header (0x7FFFFFFF). We don't rely on n_frames — the actual data
    # length in *raw* is authoritative.

    if sampwidth == 2:
        # 16-bit signed PCM (kokoro and most TTS engines output this)
        arr = array.array("h")
        arr.frombytes(raw)
        total = len(arr)
        fade = min(_FADE_SAMPLES, total // (2 * n_channels))
        if fade > 0:
            denom = max(fade - 1, 1)
            # Fade-in: ramp from 0 to full amplitude
            for i in range(fade):
                factor = i / denom
                for ch in range(n_channels):
                    arr[i * n_channels + ch] = int(arr[i * n_channels + ch] * factor)
            # Fade-out: ramp from full amplitude to 0
            for i in range(fade):
                factor = (fade - 1 - i) / denom
                for ch in range(n_channels):
                    arr[(total - fade + i) * n_channels + ch] = int(
                        arr[(total - fade + i) * n_channels + ch] * factor
                    )
        data = arr.tobytes()
    else:
        # Unsupported sample width — copy without fades
        data = raw

    dst.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dst), "wb") as wav:
        wav.setnchannels(n_channels)
        wav.setsampwidth(sampwidth)
        wav.setframerate(framerate)
        wav.writeframes(data)


def _apply_fades_to_all(chunks: list[Path], output_dir: Path) -> list[Path]:
    """Apply fades to every chunk, writing results into *output_dir*."""
    output_dir.mkdir(parents=True, exist_ok=True)
    faded: list[Path] = []
    for chunk in chunks:
        dst = output_dir / chunk.name
        _apply_wav_fades(chunk, dst)
        faded.append(dst)
    return faded


async def assemble_mp3(chunks: list[Path], target: Path) -> None:
    if not chunks or any(not chunk.is_file() for chunk in chunks):
        raise AudioAssemblyError("all chunk audio files must exist before assembly")
    target.parent.mkdir(parents=True, exist_ok=True)

    # Apply short fade-in/fade-out to each chunk to eliminate boundary clicks.
    faded_dir = target.parent / ".fades"
    faded_chunks = await asyncio.to_thread(_apply_fades_to_all, chunks, faded_dir)

    manifest = target.with_suffix(".concat.txt")
    async with aiofiles.open(manifest, "w", encoding="utf-8") as output:
        for chunk in faded_chunks:
            escaped = str(chunk.resolve()).replace("'", "'\\''")
            await output.write(f"file '{escaped}'\n")
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(manifest),
        "-codec:a",
        "libmp3lame",
        "-b:a",
        "128k",
        str(target),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    manifest.unlink(missing_ok=True)
    shutil.rmtree(faded_dir, ignore_errors=True)
    if process.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        raise AudioAssemblyError(
            f"FFmpeg assembly failed: {stderr.decode(errors='replace')[-1_000:]}"
        )
