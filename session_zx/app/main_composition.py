"""Main composition root for the CLI application."""

import os
import random
import sys
import time
from pathlib import Path

from session_zx.adapters.debounce_storage import JsonDebounceStorage
from session_zx.adapters.env_file import EnvFileAdapter
from session_zx.adapters.frecency_storage import JsonFrecencyStorage
from session_zx.adapters.fzf_cli import FzfCliAdapter
from session_zx.adapters.process_subprocess import SubprocessAdapter
from session_zx.adapters.tmux_cli import TmuxCliAdapter
from session_zx.adapters.tmux_prompt import TmuxPromptAdapter
from session_zx.app.composition import AppDependencies, build_app_dependencies
from session_zx.cli.fzf_selectors import FzfSelectors
from session_zx.use_cases.action_menu import run_action_menu
from session_zx.use_cases.helper_actions import (
    run_delayed_switch,
    run_kill_single_from_line,
    run_reload_sessions,
    run_switch_from_line,
)
from session_zx.use_cases.mutation_actions import (
    run_detach,
    run_kill,
    run_new,
    run_rename,
)
from session_zx.use_cases.popup_actions import (
    run_popup_capital_switch,
    run_popup_switch,
    run_popup_worktree_switch,
)
from session_zx.use_cases.switch_actions import (
    run_capital_switch,
    run_switch,
    run_worktree_switch,
)


class AppDeps:
    """Dependency container for the application."""

    def __init__(self, script_dir: Path, env: dict[str, str]) -> None:
        self.script_dir = script_dir
        self.process_port = SubprocessAdapter()
        self.tmux = TmuxCliAdapter(self.process_port)
        self.fzf_adapter = FzfCliAdapter(self.process_port)
        self.selectors = FzfSelectors(self.fzf_adapter, env)
        self.prompt_adapter = TmuxPromptAdapter()
        
        # Storage
        self.frecency_storage = JsonFrecencyStorage(script_dir / ".session-frecency")
        self.debounce_storage = JsonDebounceStorage(
            Path("/tmp") / f"tmux-session-{os.getuid()}.json"
        )
        
        # Action mapping
        self.action_handlers = {
            "switch": run_switch,
            "new": run_new,
            "rename": run_rename,
            "detach": run_detach,
            "kill": run_kill,
            "popup-switch": run_popup_switch,
            "popup-worktree-switch": run_popup_worktree_switch,
            "popup-capital-switch": run_popup_capital_switch,
            "worktree-switch": run_worktree_switch,
            "capital-switch": run_capital_switch,
            "reload-sessions": run_reload_sessions,
            "kill-single-from-line": run_kill_single_from_line,
            "switch-from-line": run_switch_from_line,
            "delayed-switch": run_delayed_switch,
        }
        
        # Properties for use cases
        self.switch_script_path = sys.argv[0]
        self.process_id = os.getpid()

    # Loader methods
    def list_session_rows(self): return self.tmux.list_session_rows()
    def get_current_session(self): return self.tmux.get_current_session()
    def get_attached_session_names(self): return self.tmux.get_attached_session_names()
    def get_pane_current_path(self): return self.tmux.get_pane_current_path()
    def get_git_worktrees(self, p): return self.tmux.get_git_worktrees(p)
    def get_all_pane_paths(self): return self.tmux.get_all_pane_paths()
    
    # Mutator methods
    def create_session(self, n): return self.tmux.create_session(n)
    def switch_client(self, t): return self.tmux.switch_client(t)
    def rename_session(self, t, n): return self.tmux.rename_session(t, n)
    def kill_session(self, t): return self.tmux.kill_session(t)
    def detach_session(self, t): return self.tmux.detach_session(t)
    def display_popup(self, t, a): return self.tmux.display_popup(t, a)
    
    # UI methods
    def action_menu_selector(self, i, h, m): return self.selectors.select_action(i, h, m)
    def switch_session_selector(self, i, h, m, e): return self.selectors.select_switch(i, h, m, e)
    def rename_session_selector(self, i, h, m): return self.selectors.select_action(i, h, m)
    def kill_session_selector(self, i, h, m): return self.selectors.select_action(i, h, m)
    def detach_session_selector(self, i, h, m): return self.selectors.select_action(i, h, m)
    def prompt_session_name(self): return self.prompt_adapter.prompt()
    
    # Helper methods
    def write_stdout(self, s): sys.stdout.write(s)
    def sleep_ms(self, ms): time.sleep(ms / 1000.0)
    def now_ms(self): return int(time.time() * 1000)
    def random_suffix(self, n): return "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=n))
    def read_debounce_state(self): return self.debounce_storage.read()
    def write_debounce_state(self, s): return self.debounce_storage.write(s)
    def record_frecency(self, target): self.frecency_storage.save_selection(target, self.now_ms())
    
    def spawn_delayed_switch(self, token):
        """Spawn a background process for delayed switch."""
        return self.process_port.spawn_detached([sys.argv[0], "delayed-switch", token])

    def log_event(self, message: str) -> None:
        """Log an event to the session-zx.log file."""
        log_path = self.script_dir / "session-zx.log"
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        try:
            with open(log_path, "a") as f:
                f.write(f"{timestamp} {message}\n")
        except Exception:
            pass


def compose_app() -> tuple[dict[str, str], AppDeps, EnvFileAdapter]:
    """Compose all application components and return them."""
    script_path = Path(sys.argv[0]).resolve()
    script_dir = script_path.parent
    
    # Preliminary environment
    env = dict(os.environ)
    
    # Create deps container
    deps = AppDeps(script_dir, env)
    
    # Env loader
    env_port = EnvFileAdapter()
    
    return env, deps, env_port
