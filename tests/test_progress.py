from awaaz.domain.progress import calculate_progress


def test_progress_uses_completed_and_failed_chunks() -> None:
    progress = calculate_progress(total=8, completed=3, failed=1)

    assert progress.processed == 4
    assert progress.percent == 50.0


def test_empty_job_has_zero_progress() -> None:
    assert calculate_progress(0, 0, 0).percent == 0.0

