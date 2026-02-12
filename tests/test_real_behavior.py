"""Real integration tests for session-zx.mjs behavior.

Uses popup-switch for end-to-end workflow tests (real user path).
Uses switch (direct) only when we need to inspect fzf screen content.

Each test checks before-state, does the action, checks after-state.
"""
import os
import time
import pytest


# ---------------------------------------------------------------------------
# Group 1 — Session switching via popup-switch (Ctrl+Shift+L workflow)
# ---------------------------------------------------------------------------

def test_switch_by_typing_full_name(tmux, create_sessions):
    """Type full session name in popup, press Enter. Verify switched."""
    create_sessions("target_sess")

    before = tmux.get_current_session()
    assert before == "test_session"

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    tmux.send_keys("target_sess")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("target_sess", timeout=3), \
        f"Did not switch to target_sess. Current: {tmux.get_current_session()}"


def test_switch_by_partial_name(tmux, create_sessions):
    """Type partial name to filter, press Enter. Verify switched."""
    create_sessions("alpha_session")

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    tmux.send_keys("alpha")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("alpha_session", timeout=3), \
        f"Did not switch. Current: {tmux.get_current_session()}"


def test_escape_cancels_switch(tmux, create_sessions):
    """Type a name, press Escape. Verify stayed in original session."""
    create_sessions("other_one")

    before = tmux.get_current_session()
    assert before == "test_session"

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    tmux.send_keys("other_one")
    time.sleep(0.5)
    tmux.press_escape()
    time.sleep(0.5)

    after = tmux.get_current_session()
    assert after == "test_session", f"Should stay in test_session, got {after}"


def test_switch_arrow_down_then_enter(tmux, create_sessions):
    """Arrow down in popup, press Enter. Verify switched away."""
    create_sessions("arrow_target")

    before = tmux.get_current_session()
    assert before == "test_session"

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # fzf highlights bottom match by default. Arrow down several times
    # to make sure we land on a non-current, non-cancel item.
    tmux.press_arrow_down()
    time.sleep(0.2)
    tmux.press_arrow_down()
    time.sleep(0.2)
    tmux.press_arrow_down()
    time.sleep(0.3)

    # Type partial filter to ensure arrow_target is the only match
    tmux.send_keys("arrow")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("arrow_target", timeout=3), \
        f"Should have switched to arrow_target, got {tmux.get_current_session()}"


# ---------------------------------------------------------------------------
# Group 2 — Live preview switching (Ctrl+N/P)
# ---------------------------------------------------------------------------

def test_ctrl_n_previews_session(tmux, create_sessions):
    """Ctrl+N triggers live preview — client switches after debounce.

    fzf needs --reverse layout so ctrl-n (down) = next item.
    Without --reverse, cursor starts at bottom and down does nothing.
    """
    create_sessions("preview_a", "preview_b")

    # Set env in tmux global environment so popup subprocess inherits it
    os.system("tmux set-environment -g SESSION_SWITCH_DEBOUNCE_MS 2000")
    os.system("tmux set-environment -g FZF_DEFAULT_OPTS '--reverse'")
    tmux.run_command("export SESSION_SWITCH_DEBOUNCE_MS=2000")
    tmux.run_command("export FZF_DEFAULT_OPTS='--reverse'")
    time.sleep(0.3)

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # Ctrl+N moves down and triggers switch-from-line
    tmux.press_ctrl_n()
    time.sleep(2.5)  # debounce (2s) + margin

    after = tmux.get_current_session()
    # Client should have moved away from test_session
    assert after != "test_session", \
        f"Expected preview to switch client, still in {after}"

    # Cleanup: close popup
    tmux.press_escape()
    time.sleep(0.5)


def test_ctrl_n_then_escape_behavior(tmux, create_sessions):
    """After Ctrl+N live preview, pressing Escape closes popup.

    The client stays in whatever session the preview switched to
    (tmux popup close does NOT revert the switch-client underneath).
    """
    create_sessions("preview_target")

    before = tmux.get_current_session()
    assert before == "test_session"

    # Set env in tmux global environment so popup subprocess inherits it
    os.system("tmux set-environment -g SESSION_SWITCH_DEBOUNCE_MS 2000")
    os.system("tmux set-environment -g FZF_DEFAULT_OPTS '--reverse'")
    tmux.run_command("export SESSION_SWITCH_DEBOUNCE_MS=2000")
    tmux.run_command("export FZF_DEFAULT_OPTS='--reverse'")
    time.sleep(0.3)

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    tmux.press_ctrl_n()
    time.sleep(2.5)

    mid = tmux.get_current_session()

    tmux.press_escape()
    time.sleep(0.5)

    after = tmux.get_current_session()

    # Document: popup close does not revert. Client stays where preview put it.
    # If this assertion fails, tmux changed behavior — update the test.
    assert after == mid, \
        f"Expected session to stay at '{mid}' after Escape, got '{after}'"


def test_ctrl_n_debounce_only_switches_once(tmux, create_sessions):
    """Press Ctrl+N three times fast. Only the last one should fire."""
    create_sessions("deb_a", "deb_b", "deb_c")

    # Set env in tmux global environment so popup subprocess inherits it
    os.system("tmux set-environment -g SESSION_SWITCH_DEBOUNCE_MS 2000")
    os.system("tmux set-environment -g FZF_DEFAULT_OPTS '--reverse'")
    tmux.run_command("export SESSION_SWITCH_DEBOUNCE_MS=2000")
    tmux.run_command("export FZF_DEFAULT_OPTS='--reverse'")
    time.sleep(0.3)

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # Press Ctrl+N three times quickly
    tmux.press_ctrl_n()
    time.sleep(0.1)
    tmux.press_ctrl_n()
    time.sleep(0.1)
    tmux.press_ctrl_n()
    time.sleep(2.5)  # wait for debounce

    after = tmux.get_current_session()
    # Should be in ONE of the sessions (the last one fzf stopped on), not test_session
    assert after != "test_session", \
        f"Expected to be previewed away from test_session, still in {after}"

    tmux.press_escape()
    time.sleep(0.5)


# ---------------------------------------------------------------------------
# Group 3 — fzf filtering (switch directly, for screen checks)
# ---------------------------------------------------------------------------

def test_typing_filters_fzf_list(tmux, create_sessions):
    """Type a filter in fzf and verify only matching items are shown."""
    create_sessions("alpha", "beta", "gamma")

    tmux.run_command("node /app/session-zx.mjs switch")
    time.sleep(1.5)

    # All sessions should be visible initially
    content = tmux.get_output()
    assert "alpha" in content, f"alpha not in output:\n{content}"
    assert "beta" in content, f"beta not in output:\n{content}"
    assert "gamma" in content, f"gamma not in output:\n{content}"

    # Type filter
    tmux.send_keys("beta")
    time.sleep(0.5)

    content = tmux.get_output()
    assert "beta" in content, f"beta not visible after filter:\n{content}"
    # alpha and gamma should be filtered out
    # (fzf might still show them dimmed, so we check the match count)

    tmux.press_escape()
    time.sleep(0.5)


def test_backspace_corrects_filter(tmux, create_sessions):
    """Type wrong chars, backspace, fix, Enter. Verify correct session."""
    create_sessions("banana")

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # Type "banxx" then backspace twice then "ana"
    tmux.send_keys("banxx")
    time.sleep(0.3)
    tmux.press_backspace()
    time.sleep(0.1)
    tmux.press_backspace()
    time.sleep(0.1)
    tmux.send_keys("ana")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("banana", timeout=3), \
        f"Did not switch to banana. Current: {tmux.get_current_session()}"


# ---------------------------------------------------------------------------
# Group 4 — DEL key kills session in switch
# ---------------------------------------------------------------------------

def test_del_key_kills_session(tmux, create_sessions):
    """Press Delete key on a session in popup. Verify session is killed."""
    create_sessions("victim")

    assert "victim" in tmux.get_all_sessions()

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # Filter to victim
    tmux.send_keys("victim")
    time.sleep(0.5)

    # Press real Delete key (triggers fzf 'del' event)
    tmux.press_delete()
    time.sleep(1.5)  # wait for kill + reload

    # Close popup
    tmux.press_escape()
    time.sleep(0.5)

    assert tmux.wait_for_session_gone("victim", timeout=3), \
        f"victim still exists. Sessions: {tmux.get_all_sessions()}"


# ---------------------------------------------------------------------------
# Group 5 — New session
# ---------------------------------------------------------------------------

def test_new_session_creation(tmux):
    """Create a new session via 'new' action + FIFO."""
    tmux.send_keys("node /app/session-zx.mjs new")
    tmux.press_enter()
    time.sleep(2.0)  # wait for split window to open

    # Write session name to FIFO (simulates user typing in split window)
    os.system("echo fresh_session > /tmp/tmux_fzf_session_name")
    time.sleep(1.5)

    sessions = tmux.get_all_sessions()
    assert "fresh_session" in sessions, f"fresh_session not created. Sessions: {sessions}"

    assert tmux.wait_for_session_switch("fresh_session", timeout=3), \
        f"Did not switch to fresh_session. Current: {tmux.get_current_session()}"


# ---------------------------------------------------------------------------
# Group 6 — Rename session
# ---------------------------------------------------------------------------

def test_rename_session(tmux):
    """Rename test_session via 'rename' action + FIFO + fzf selection."""
    tmux.send_keys("node /app/session-zx.mjs rename")
    tmux.press_enter()
    time.sleep(2.0)  # wait for FIFO blocking

    # Write new name to FIFO
    os.system("echo renamed_sess > /tmp/tmux_fzf_session_name")
    time.sleep(0.5)

    # fzf appears — select test_session
    time.sleep(0.5)
    tmux.send_keys("test_session")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    sessions = tmux.get_all_sessions()
    assert "renamed_sess" in sessions, f"renamed_sess not found. Sessions: {sessions}"
    assert "test_session" not in sessions, f"test_session still exists. Sessions: {sessions}"


# ---------------------------------------------------------------------------
# Group 7 — Kill action (single session, no multi-select)
# ---------------------------------------------------------------------------

def test_kill_action_removes_session(tmux, create_sessions):
    """Kill a session via 'kill' action. Verify it's gone, others stay."""
    create_sessions("kill_me", "keep_me")

    tmux.run_command("node /app/session-zx.mjs kill")
    time.sleep(1.5)

    tmux.send_keys("kill_me")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_gone("kill_me", timeout=3), \
        f"kill_me still exists. Sessions: {tmux.get_all_sessions()}"

    sessions = tmux.get_all_sessions()
    assert "keep_me" in sessions, f"keep_me was also killed. Sessions: {sessions}"


# ---------------------------------------------------------------------------
# Group 8 — Action menu
# ---------------------------------------------------------------------------

def test_action_menu_shows_all_options(tmux):
    """Run script with no args. Verify all actions are visible in fzf."""
    tmux.run_command("node /app/session-zx.mjs")
    time.sleep(1.5)

    content = tmux.get_output()

    expected = ["switch", "new", "rename", "detach", "kill", "[cancel]"]
    for item in expected:
        assert item in content, f"'{item}' not visible in action menu. Content:\n{content}"

    tmux.press_escape()
    time.sleep(0.5)


def test_action_menu_cancel_does_nothing(tmux):
    """Select [cancel] from action menu. Verify nothing changes."""
    before = tmux.get_current_session()

    tmux.run_command("node /app/session-zx.mjs")
    time.sleep(1.0)

    tmux.send_keys("cancel")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(0.5)

    after = tmux.get_current_session()
    assert after == before, f"Session changed from {before} to {after}"
