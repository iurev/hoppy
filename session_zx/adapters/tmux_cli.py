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

    def get_pane_current_path(self) -> str:
        """Execute tmux display-message to get current pane path."""
        code, stdout, _ = self.process.run(["tmux", "display-message", "-p", "#{pane_current_path}"])
        return stdout.strip() if code == 0 else ""

    def get_git_worktrees(self, dir_path: str) -> Sequence[str]:
        """Execute git worktree list to find all worktree paths for a directory."""
        if not dir_path:
            return []
        code, stdout, _ = self.process.run(
            ["git", "-C", dir_path, "worktree", "list", "--porcelain"]
        )
        if code != 0:
            return []

        paths = []
        for line in stdout.split("\n"):
            if line.startswith("worktree "):
                paths.append(line[9:])  # Remove 'worktree ' prefix
        return paths

    def get_all_pane_paths(self) -> dict[str, set[str]]:
        """Execute tmux list-panes -a to get all pane paths grouped by session."""
        code, stdout, _ = self.process.run(
            ["tmux", "list-panes", "-a", "-F", "#{session_name}\t#{pane_current_path}"]
        )
        if code != 0:
            return {}

        session_paths: dict[str, set[str]] = {}
        for line in parse_lines(stdout):
            parts = line.split("\t")
            if len(parts) == 2:
                session_name, pane_path = parts
                session_paths.setdefault(session_name, set()).add(pane_path)
        return session_paths

    def display_popup(self, title: str, child_action: str) -> int:
        """Execute tmux display-popup to run a sub-action."""
        # We need the path to the current script
        import sys
        script_path = sys.argv[0]
        
        cmd = [
            "tmux", "display-popup", "-E", "-w", "60%", "-h", "90%",
            "-x", "R", "-y", "C", "-T", title, "-b", "rounded",
            script_path, child_action
        ]
        code, _, _ = self.process.run(cmd)
        return code
