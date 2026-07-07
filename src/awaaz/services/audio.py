import asyncio
from pathlib import Path

import aiofiles

from awaaz.domain.exceptions import AudioAssemblyError


async def assemble_mp3(chunks: list[Path], target: Path) -> None:
    if not chunks or any(not chunk.is_file() for chunk in chunks):
        raise AudioAssemblyError("all chunk audio files must exist before assembly")
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest = target.with_suffix(".concat.txt")
    async with aiofiles.open(manifest, "w", encoding="utf-8") as output:
        for chunk in chunks:
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
    if process.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        raise AudioAssemblyError(
            f"FFmpeg assembly failed: {stderr.decode(errors='replace')[-1_000:]}"
        )

