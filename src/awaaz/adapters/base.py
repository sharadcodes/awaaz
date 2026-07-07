from pathlib import Path
from typing import Protocol


class TtsAdapter(Protocol):
    async def synthesize(self, text: str, target: Path, *, speed: float = 1.0) -> None: ...

