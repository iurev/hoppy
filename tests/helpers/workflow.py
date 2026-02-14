"""Shared workflow helpers for tmux integration tests."""
import os
import time


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


def write_session_name_to_fifo(session_name, fifo_path="/tmp/tmux_fzf_session_name"):
    """Write a session name to the FIFO used by new/rename actions."""
    with open(fifo_path, "w", encoding="utf-8") as fifo:
        fifo.write(f"{session_name}\n")
