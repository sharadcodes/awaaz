from pathlib import Path

import pytest

from awaaz.services.files import FileValidationError, validate_upload


def test_txt_and_epub_are_supported() -> None:
    assert validate_upload("book.txt") == ".txt"
    assert validate_upload("book.epub") == ".epub"


def test_future_loader_type_fails_fast() -> None:
    with pytest.raises(FileValidationError, match="unsupported"):
        validate_upload("book.pdf")


def test_path_like_filename_is_sanitized() -> None:
    assert validate_upload(str(Path("unsafe") / "book.txt")) == ".txt"
