"""Process execution port contract."""

from collections.abc import Mapping, Sequence
from typing import Protocol


class ProcessPort(Protocol):
    """Contract for executing external processes."""

    def run(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        capture_output: bool = True,
    ) -> tuple[int, str, str]:
        """Execute a command and return (exit_code, stdout, stderr)."""
        ...

    def spawn_detached(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
    ) -> bool:
        """Spawn a process in the background, detached from the current one."""
        ...
