import asyncio
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import aiofiles
from fastapi import UploadFile

from awaaz.domain.exceptions import DocumentError


class FileValidationError(DocumentError):
    """Uploaded file is unsupported or invalid."""


def validate_upload(filename: str) -> str:
    extension = Path(filename).suffix.lower()
    if extension not in {".txt", ".epub"}:
        raise FileValidationError(f"unsupported file type: {extension or 'none'}")
    return extension


async def save_upload(upload: UploadFile, target: Path, max_bytes: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    async with aiofiles.open(target, "wb") as output:
        while data := await upload.read(1024 * 1024):
            size += len(data)
            if size > max_bytes:
                target.unlink(missing_ok=True)
                raise FileValidationError(f"upload exceeds {max_bytes} bytes")
            await output.write(data)


async def extract_text(source: Path) -> str:
    if source.suffix.lower() == ".txt":
        try:
            return await asyncio.to_thread(source.read_text, encoding="utf-8")
        except UnicodeDecodeError as error:
            raise FileValidationError("TXT file must use UTF-8 encoding") from error
    target = source.with_suffix(".extracted.txt")
    process = await asyncio.create_subprocess_exec(
        "ebook-convert",
        str(source),
        str(target),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise FileValidationError(
            f"Calibre conversion failed: {stderr.decode(errors='replace')[-1_000:]}"
        )
    return await asyncio.to_thread(target.read_text, encoding="utf-8")


def _parse_opf_metadata(opf_path: Path) -> dict[str, Any]:
    try:
        tree = ET.parse(opf_path)
    except ET.ParseError:
        return {}
    root = tree.getroot()
    ns = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
    metadata = root.find("opf:metadata", ns)
    if metadata is None:
        return {}

    def text(tag: str) -> str | None:
        elem = metadata.find(f"dc:{tag}", ns)
        return elem.text.strip() if elem is not None and elem.text else None

    def texts(tag: str) -> list[str]:
        return [
            elem.text.strip()
            for elem in metadata.findall(f"dc:{tag}", ns)
            if elem.text and elem.text.strip()
        ]

    meta = metadata.find("opf:meta[@name='calibre:series']", ns)
    series = meta.get("content") if meta is not None else None
    meta_index = metadata.find("opf:meta[@name='calibre:series_index']", ns)
    series_index = meta_index.get("content") if meta_index is not None else None

    return {
        "title": text("title"),
        "authors": texts("creator"),
        "tags": texts("subject"),
        "description": text("description"),
        "language": text("language"),
        "publisher": text("publisher"),
        "published": text("date"),
        "series": series,
        "series_index": series_index,
    }


async def extract_metadata(source: Path) -> dict[str, Any]:
    """Extract metadata from EPUB using Calibre's ebook-meta output."""
    if source.suffix.lower() != ".epub":
        return {}
    opf_path = source.with_suffix(".opf")
    process = await asyncio.create_subprocess_exec(
        "ebook-meta",
        str(source),
        "--to-opf",
        str(opf_path),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()
    if process.returncode != 0 or not opf_path.exists():
        return {}
    try:
        return await asyncio.to_thread(_parse_opf_metadata, opf_path)
    finally:
        opf_path.unlink(missing_ok=True)


async def extract_cover(source: Path, target: Path) -> bool:
    """Extract cover image from EPUB using Calibre's ebook-meta."""
    if source.suffix.lower() != ".epub":
        return False
    process = await asyncio.create_subprocess_exec(
        "ebook-meta",
        str(source),
        "--get-cover",
        str(target),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.communicate()
    return target.exists() and target.stat().st_size > 0
