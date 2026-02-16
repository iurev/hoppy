"""Tmux orchestration port contract."""

from collections.abc import Sequence
from typing import Protocol


class TmuxPort(Protocol):
    """Contract for tmux operations."""

    def list_session_rows(self) -> Sequence[str]:
        """Return formatted session rows from tmux."""
        ...

    def get_current_session(self) -> str | None:
        """Return the name of the current tmux session."""
        ...

    def get_attached_session_names(self) -> Sequence[str]:
        """Return names of all sessions currently attached to a client."""
        ...

    def create_session(self, name: str) -> bool:
        """Create a new detached tmux session."""
        ...

    def switch_client(self, target: str) -> bool:
        """Switch the current client to the target session."""
        ...

    def rename_session(self, target: str, new_name: str) -> bool:
        """Rename a tmux session."""
        ...

    def kill_session(self, target: str) -> bool:
        """Kill a tmux session."""
        ...

    def detach_session(self, target: str) -> bool:
        """Detach all clients from the target session."""
        ...
