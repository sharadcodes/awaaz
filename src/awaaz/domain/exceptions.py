class AwaazError(Exception):
    """Base application error."""


class DocumentError(AwaazError):
    """Document operation failed."""


class JobError(AwaazError):
    """Job operation failed."""


class TtsRequestError(AwaazError):
    def __init__(self, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.retryable = retryable


class AudioAssemblyError(AwaazError):
    """Audio assembly failed."""
