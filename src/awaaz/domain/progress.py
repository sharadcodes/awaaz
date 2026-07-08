from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Progress:
    total: int
    completed: int
    failed: int
    processed: int
    percent: float


def calculate_progress(total: int, completed: int, failed: int) -> Progress:
    processed = completed + failed
    percent = round(processed / total * 100, 2) if total else 0.0
    return Progress(total, completed, failed, processed, percent)
