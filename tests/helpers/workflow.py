"""Shared workflow helpers for tmux integration tests."""
import json
import os
import shutil
import time

# Where the binary keeps frecency data (SPEC §0.3, §0.55).
FRECENCY_FILE = "/app/.session-frecency/sessions.json"

# tmux display-message texts (SPEC §3.9, §3.10).
MSG_NOT_IN_GIT = "Not in a git repository"
MSG_NO_WORKTREE_SESSIONS = "No sessions found for this project's worktrees"
MSG_NO_CAPITAL_SESSIONS = "No CAPITAL sessions found"


def configure_popup_env(*, debounce_ms=None, reverse=False):
    """Set tmux environment variables inherited by popup subprocesses."""
    if debounce_ms is not None:
        os.system(f"tmux set-environment -g SESSION_SWITCH_DEBOUNCE_MS {debounce_ms}")
    if reverse:
        os.system("tmux set-environment -g FZF_DEFAULT_OPTS '--reverse'")
    time.sleep(0.3)


def run_popup_switch(tmux, action="popup-switch", wait=1.5):
    """Open popup switch workflow and wait for fzf UI."""
    tmux.run_popup_switch(action=action, wait=wait)


def type_query_and_accept(tmux, query, query_wait=0.5, accept_wait=1.0):
    """Type query and accept current row."""
    tmux.type_and_accept(query, type_wait=query_wait, accept_wait=accept_wait)


def clear_query(tmux, count, delay=0.08):
    """Clear active query by pressing backspace repeatedly."""
    tmux.clear_query_backspaces(count, delay=delay)


def session_name_fifo_path():
    """Return the per-user FIFO path the binary creates (SPEC 9.2.1).

    The binary builds the same path: <tmpdir>/tmux-session-<uid>/name.fifo.
    The old path was the shared, world-writable /tmp/tmux_fzf_session_name.
    """
    tmpdir = os.environ.get("TMPDIR", "/tmp").rstrip("/") or "/tmp"
    return os.path.join(tmpdir, f"tmux-session-{os.getuid()}", "name.fifo")


def write_session_name_to_fifo(session_name, fifo_path=None):
    """Write a session name to the FIFO used by new/rename actions."""
    if fifo_path is None:
        fifo_path = session_name_fifo_path()
    with open(fifo_path, "w", encoding="utf-8") as fifo:
        fifo.write(f"{session_name}\n")


# --- reload-sessions ---------------------------------------------------------


def run_reload_in_pane(tmux, out_path="/tmp/zx_reload_out.txt", timeout=10):
    """Run `reload-sessions` inside the attached pane and return its rows.

    Running it in a pane is the only way to give the binary a real current
    session, which is what the Q7 FIX pins to the top (SPEC §3.3).
    """
    if os.path.exists(out_path):
        os.remove(out_path)

    tmux.run_command(f"/app/session-zx reload-sessions > {out_path} 2>&1")

    deadline = time.time() + timeout
    previous = None
    while time.time() < deadline:
        time.sleep(0.4)
        if not os.path.exists(out_path):
            continue
        with open(out_path, encoding="utf-8") as handle:
            text = handle.read()
        # Wait for two equal reads, so we never parse a half-written file.
        if text and text == previous:
            return [line for line in text.split("\n") if line.strip()]
        previous = text

    raise AssertionError(f"reload-sessions wrote nothing to {out_path}")


def row_session_names(rows):
    """Return the session name of every '[N] name @ K windows' row."""
    names = []
    for row in rows:
        body = row
        if body.startswith("["):
            head, _, rest = body.partition("] ")
            if head[1:].isdigit():
                body = rest
            else:
                continue  # a literal row such as [cancel]
        name, sep, _ = body.rpartition(" @ ")
        names.append(name if sep else body)
    return names


# --- frecency ----------------------------------------------------------------


def read_frecency():
    """Return the frecency JSON, or {} when the file is missing or broken."""
    try:
        with open(FRECENCY_FILE, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def wait_for_frecency_session(name, timeout=5):
    """Poll until the frecency file records a pick of `name`."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        record = read_frecency().get("sessions", {}).get(name)
        if record and record.get("selectedAt"):
            return True
        time.sleep(0.2)
    return False


# --- git repositories for worktree-switch ------------------------------------


def reset_dir(path):
    """Delete `path` and make it again, empty."""
    shutil.rmtree(path, ignore_errors=True)
    os.makedirs(path, exist_ok=True)


def create_git_repo(path):
    """Make a git repo with one commit at `path`."""
    reset_dir(path)
    os.system(f"git -C {path} init -q -b main")
    os.system(f"git -C {path} config user.email test@example.com")
    os.system(f"git -C {path} config user.name Test")
    with open(os.path.join(path, "file.txt"), "w", encoding="utf-8") as handle:
        handle.write("hello\n")
    os.system(f"git -C {path} add -A")
    os.system(f"git -C {path} commit -q -m init")


def add_git_worktree(repo, path, branch):
    """Add a linked worktree of `repo` at `path`."""
    shutil.rmtree(path, ignore_errors=True)
    os.system(f"git -C {repo} worktree add -q {path} -b {branch}")


def create_repo_with_detached_git_dir(work, git_dir):
    """Make a repo whose git dir sits outside the working copy.

    `git worktree list` then reports the GIT DIR as the worktree path. No tmux
    pane can ever be inside it, so every session is filtered out. That is how we
    reach the "No sessions found for this project's worktrees" branch.
    """
    shutil.rmtree(work, ignore_errors=True)
    shutil.rmtree(git_dir, ignore_errors=True)
    os.makedirs(work)
    os.system(f"git init -q -b main --separate-git-dir={git_dir} {work}")
