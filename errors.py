"""Transient game-state failures are retryable; write/compatibility errors are not."""
class TransientGameState(RuntimeError):
    pass


class ProcessSelectionError(RuntimeError):
    pass
