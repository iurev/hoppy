"""Tmux orchestration adapter using the tmux CLI."""

from collections.abc import Sequence

from session_zx.domain.parsing import parse_lines
from session_zx.ports.process import ProcessPort
from session_zx.ports.tmux import TmuxPort


class TmuxCliAdapter(TmuxPort):
    """Adapter that executes tmux commands via a ProcessPort."""

    def __init__(self, process_port: ProcessPort) -> None:
        self.process = process_port

    def list_session_rows(self) -> Sequence[str]:
        """Execute tmux list-sessions with standard format."""
        code, stdout, _ = self.process.run(
            ["tmux", "list-sessions", "-F", "#S @ #{session_windows} windows"]
        )
        if code != 0:
            return []
        return parse_lines(stdout)

    def get_current_session(self) -> str | None:
        """Execute tmux display-message to get current session name."""
        code, stdout, _ = self.process.run(["tmux", "display-message", "-p", "#S"])
        if code != 0:
            return None
        return stdout.strip()

    def get_attached_session_names(self) -> Sequence[str]:
        """Execute tmux list-sessions to find attached sessions."""
        code, stdout, _ = self.process.run(
            ["tmux", "list-sessions", "-F", "#{session_name} #{session_attached}"]
        )
        if code != 0:
            return []

        attached = []
        for line in parse_lines(stdout):
            parts = line.split()
            if len(parts) == 2 and parts[1] != "0":
                attached.append(parts[0])
        return attached

    def create_session(self, name: str) -> bool:
        """Execute tmux new-session -d -s."""
        code, _, _ = self.process.run(["tmux", "new-session", "-d", "-s", name])
        return code == 0

    def switch_client(self, target: str) -> bool:
        """Execute tmux switch-client -t."""
        code, _, _ = self.process.run(["tmux", "switch-client", "-t", target])
        return code == 0

    def rename_session(self, target: str, new_name: str) -> bool:
        """Execute tmux rename-session -t."""
        code, _, _ = self.process.run(["tmux", "rename-session", "-t", target, new_name])
        return code == 0

    def kill_session(self, target: str) -> bool:
        """Execute tmux kill-session -t."""
        code, _, _ = self.process.run(["tmux", "kill-session", "-t", target])
        return code == 0

    def detach_session(self, target: str) -> bool:
        """Execute tmux detach-client -s."""
        code, _, _ = self.process.run(["tmux", "detach-client", "-s", target])
        return code == 0
