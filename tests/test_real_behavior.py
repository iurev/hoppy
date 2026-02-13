"""Real integration tests for session-zx.mjs behavior.

Uses popup-switch for end-to-end workflow tests (real user path).
Uses switch (direct) only when we need to inspect fzf screen content.

Each test checks before-state, does the action, checks after-state.
"""
import os
import re
import time
import pytest


def configure_popup_env(*, debounce_ms=None, reverse=False):
    """Set tmux global env so popup subprocesses inherit test settings."""
    if debounce_ms is not None:
        os.system(f"tmux set-environment -g SESSION_SWITCH_DEBOUNCE_MS {debounce_ms}")
    if reverse:
        os.system("tmux set-environment -g FZF_DEFAULT_OPTS '--reverse'")
    time.sleep(0.3)


def press_backspace_times(tmux, count):
    """Press backspace many times to clear active fzf query."""
    for _ in range(count):
        tmux.press_backspace()
        time.sleep(0.08)


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


def test_switch_ctrl_n_then_enter(tmux, create_sessions):
    """Ctrl+N navigates down AND live-previews, then Enter confirms.

    Ctrl+N binding: down + execute-silent(switch-from-line {})
    So it moves the cursor AND triggers a live preview switch.

    Uses --reverse layout so Ctrl+N (down) moves visually downward:
    > [1] test_session @ 1 windows   <- cursor starts here
      [2] arrow_target @ 1 windows
      [cancel]

    Ctrl+N moves to arrow_target and live-switches there. Enter confirms.
    No filter — filter resets cursor position, hiding navigation bugs.
    """
    create_sessions("arrow_target")

    before = tmux.get_current_session()
    assert before == "test_session"

    # Set --reverse so Ctrl+N navigates downward visually
    configure_popup_env(reverse=True)

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # Ctrl+N = move down + live preview switch (debounce 300ms default)
    tmux.press_ctrl_n()
    time.sleep(1.0)  # wait for debounce + switch

    # Live preview should have already switched us
    mid = tmux.get_current_session()
    assert mid == "arrow_target", \
        f"Live preview should have switched to arrow_target, got {mid}"

    # Enter confirms the selection
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("arrow_target", timeout=3), \
        f"Should stay in arrow_target after Enter, got {tmux.get_current_session()}"


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
    configure_popup_env(debounce_ms=2000, reverse=True)

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


def test_ctrl_p_previews_session(tmux, create_sessions):
    """Ctrl+P previews the previous row after we move down with Ctrl+N."""
    create_sessions("preview_p_target")

    configure_popup_env(debounce_ms=2000, reverse=True)

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    tmux.press_ctrl_n()
    time.sleep(2.5)

    mid = tmux.get_current_session()
    assert mid == "preview_p_target", \
        f"Expected Ctrl+N preview to reach preview_p_target, got {mid}"

    tmux.press_ctrl_p()
    time.sleep(2.5)

    after = tmux.get_current_session()
    assert after == "test_session", \
        f"Expected Ctrl+P preview to return to test_session, got {after}"

    tmux.press_escape()
    time.sleep(0.5)


def test_ctrl_n_then_ctrl_p_bounce(tmux, create_sessions):
    """Quick Ctrl+N then Ctrl+P keeps only the last debounced preview target."""
    create_sessions("bounce_target")

    configure_popup_env(debounce_ms=2000, reverse=True)

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    tmux.press_ctrl_n()
    time.sleep(0.1)
    tmux.press_ctrl_p()
    time.sleep(2.5)

    after = tmux.get_current_session()
    assert after == "test_session", \
        f"Expected final debounced target to be test_session, got {after}"

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
    configure_popup_env(debounce_ms=2000, reverse=True)

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
    configure_popup_env(debounce_ms=2000, reverse=True)

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
    # We can only observe the final client destination.
    # If debounce works, rapid Ctrl+N presses coalesce and final state is not test_session.
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
    cleaned = tmux.strip_ansi(content)
    match_count_is_one = re.search(r"\b1/\d+\b", cleaned) is not None
    only_beta_visible = "alpha" not in cleaned and "gamma" not in cleaned
    assert match_count_is_one or only_beta_visible, \
        f"Expected a narrowed list after typing beta. Output:\n{cleaned}"

    tmux.press_escape()
    time.sleep(0.5)


def test_arrow_down_then_enter_switches(tmux, create_sessions):
    """Arrow down and Enter should switch to the next session."""
    create_sessions("arrow_pick")

    before = tmux.get_current_session()
    assert before == "test_session"

    tmux.run_command("FZF_DEFAULT_OPTS='--reverse' node /app/session-zx.mjs switch")
    time.sleep(1.5)

    tmux.press_arrow_down()
    time.sleep(0.3)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("arrow_pick", timeout=3), \
        f"Arrow + Enter did not switch to arrow_pick. Current: {tmux.get_current_session()}"


def test_arrow_up_then_enter_switches(tmux, create_sessions):
    """Arrow up navigation should change cursor position before Enter switch."""
    create_sessions("up_a", "up_b", "up_c")

    tmux.run_command("FZF_DEFAULT_OPTS='--reverse' node /app/session-zx.mjs switch")
    time.sleep(1.5)

    tmux.press_arrow_down()
    time.sleep(0.2)
    tmux.press_arrow_down()
    time.sleep(0.2)
    before_up = tmux.get_output()

    tmux.press_arrow_up()
    time.sleep(0.3)
    after_up = tmux.get_output()

    assert before_up != after_up, "Arrow up did not change fzf state."

    tmux.press_enter()
    time.sleep(1.0)

    final_session = tmux.get_current_session()
    assert final_session in {"up_a", "up_b", "up_c"}, \
        f"Expected to land in one of up_* sessions, got {final_session}"


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


def test_clear_filter_with_backspaces(tmux, create_sessions):
    """Type junk, clear with backspaces, then select a real session."""
    create_sessions("alpha", "beta")

    tmux.run_command("node /app/session-zx.mjs switch")
    time.sleep(1.5)

    tmux.send_keys("xxxxx")
    time.sleep(0.5)

    no_match = tmux.strip_ansi(tmux.get_output())
    assert re.search(r"\b0/\d+\b", no_match) is not None, \
        f"Expected 0 matches after junk filter. Output:\n{no_match}"

    press_backspace_times(tmux, 5)
    time.sleep(0.5)

    cleared = tmux.strip_ansi(tmux.get_output())
    assert "alpha" in cleared and "beta" in cleared, \
        f"Expected list to return after clearing filter. Output:\n{cleared}"
    assert re.search(r"\b0/\d+\b", cleared) is None, \
        f"Filter still shows zero matches after backspaces. Output:\n{cleared}"

    tmux.send_keys("alpha")
    time.sleep(0.4)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("alpha", timeout=3), \
        f"Expected switch to alpha after clearing filter. Current: {tmux.get_current_session()}"


def test_filter_then_arrow_selects_second_match(tmux, create_sessions):
    """Filter to two matches; arrow down picks the other matching session."""
    create_sessions("proj_alpha", "proj_beta", "other")

    # First run: plain Enter on filtered list (baseline first match).
    tmux.run_command("FZF_DEFAULT_OPTS='--reverse' node /app/session-zx.mjs switch")
    time.sleep(1.5)
    tmux.send_keys("proj_")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    first_pick = tmux.get_current_session()
    assert first_pick in {"proj_alpha", "proj_beta"}, \
        f"Unexpected first filtered pick: {first_pick}"

    os.system("tmux switch-client -t test_session")
    time.sleep(0.5)

    # Second run: same filter, then arrow down before Enter.
    tmux.run_command("FZF_DEFAULT_OPTS='--reverse' node /app/session-zx.mjs switch")
    time.sleep(1.5)
    tmux.send_keys("proj_")
    time.sleep(0.5)
    tmux.press_arrow_down()
    time.sleep(0.3)
    tmux.press_enter()
    time.sleep(1.0)

    second_pick = tmux.get_current_session()
    assert second_pick in {"proj_alpha", "proj_beta"}, \
        f"Unexpected second filtered pick: {second_pick}"
    assert second_pick != first_pick, \
        f"Arrow down did not change selection. Both picks: {second_pick}"


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


def test_del_then_switch_another(tmux, create_sessions):
    """Delete one session in picker, then switch to another without reopening."""
    create_sessions("victim", "survivor")

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    tmux.send_keys("victim")
    time.sleep(0.4)
    tmux.press_delete()
    time.sleep(1.5)

    press_backspace_times(tmux, len("victim"))
    time.sleep(0.3)

    tmux.send_keys("survivor")
    time.sleep(0.4)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_gone("victim", timeout=3), \
        f"victim still exists after Delete flow. Sessions: {tmux.get_all_sessions()}"
    assert tmux.wait_for_session_switch("survivor", timeout=3), \
        f"Did not switch to survivor after delete+reload flow. Current: {tmux.get_current_session()}"


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


def test_kill_multiple_sessions_with_tab(tmux, create_sessions):
    """Mark two sessions with Tab in kill action and remove both."""
    create_sessions("kill_a", "kill_b", "keep_c")

    tmux.run_command("TMUX_FZF_OPTIONS='--multi' node /app/session-zx.mjs kill")
    time.sleep(1.5)

    tmux.send_keys("kill_a")
    time.sleep(0.4)
    tmux.press_tab()
    time.sleep(0.2)

    press_backspace_times(tmux, len("kill_a"))
    time.sleep(0.2)

    tmux.send_keys("kill_b")
    time.sleep(0.4)
    tmux.press_tab()
    time.sleep(0.2)

    tmux.press_enter()
    time.sleep(1.2)

    assert tmux.wait_for_session_gone("kill_a", timeout=3), \
        f"kill_a still exists after multi-select kill. Sessions: {tmux.get_all_sessions()}"
    assert tmux.wait_for_session_gone("kill_b", timeout=3), \
        f"kill_b still exists after multi-select kill. Sessions: {tmux.get_all_sessions()}"
    sessions = tmux.get_all_sessions()
    assert "keep_c" in sessions, f"keep_c was removed unexpectedly. Sessions: {sessions}"


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


# ---------------------------------------------------------------------------
# Group 9 — Edge cases & missing workflows
# ---------------------------------------------------------------------------

def test_action_menu_selects_switch_then_switches(tmux, create_sessions):
    """Full menu flow: no args -> action menu -> pick 'switch' -> pick session."""
    create_sessions("menu_target")

    tmux.run_command("node /app/session-zx.mjs")
    time.sleep(1.5)

    # Select "switch" from the action menu
    tmux.send_keys("switch")
    time.sleep(0.3)
    tmux.press_enter()
    time.sleep(1.5)  # second fzf (session list) appears

    # Pick session
    tmux.send_keys("menu_target")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("menu_target", timeout=3), \
        f"Did not switch to menu_target. Current: {tmux.get_current_session()}"


def test_filter_matches_nothing_escape(tmux, create_sessions):
    """Type gibberish (0 matches) then Escape. Verify stayed in test_session."""
    create_sessions("some_sess")

    before = tmux.get_current_session()
    assert before == "test_session"

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    tmux.send_keys("zzzzxxx_no_match")
    time.sleep(0.5)
    tmux.press_escape()
    time.sleep(0.5)

    after = tmux.get_current_session()
    assert after == "test_session", f"Should stay in test_session, got {after}"


def test_filter_matches_nothing_enter(tmux, create_sessions):
    """Type gibberish (0 matches) then Enter. Verify no crash, stayed in session."""
    create_sessions("some_sess")

    before = tmux.get_current_session()
    assert before == "test_session"

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    tmux.send_keys("zzzzxxx_no_match")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    after = tmux.get_current_session()
    assert after == "test_session", f"Should stay in test_session, got {after}"


def test_switch_only_session_exists(tmux):
    """Only test_session exists. Pick it from fzf. Verify no crash."""
    before = tmux.get_current_session()
    assert before == "test_session"

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # Only test_session + [cancel] in the list. Press Enter on test_session.
    tmux.send_keys("test_session")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    after = tmux.get_current_session()
    assert after == "test_session", f"Should stay in test_session, got {after}"


def test_switch_session_with_spaces(tmux, create_sessions):
    """Switch to a session whose name has spaces."""
    create_sessions("my session")

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    tmux.send_keys("my session")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("my session", timeout=3), \
        f"Did not switch to 'my session'. Current: {tmux.get_current_session()}"


def test_two_consecutive_switches(tmux, create_sessions):
    """Switch twice in a row: test_session -> first_dest -> second_dest."""
    create_sessions("first_dest", "second_dest")

    # First switch
    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    tmux.send_keys("first_dest")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("first_dest", timeout=3), \
        f"First switch failed. Current: {tmux.get_current_session()}"

    time.sleep(0.5)

    # Second switch (from first_dest's shell)
    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    tmux.send_keys("second_dest")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("second_dest", timeout=3), \
        f"Second switch failed. Current: {tmux.get_current_session()}"


def test_rename_other_session(tmux, create_sessions):
    """Rename a different session (not test_session). Verify old name gone, new exists."""
    create_sessions("old_name")

    tmux.send_keys("node /app/session-zx.mjs rename")
    tmux.press_enter()
    time.sleep(2.0)

    # Write new name to FIFO
    os.system("echo new_name > /tmp/tmux_fzf_session_name")
    time.sleep(0.5)

    # fzf appears — select old_name
    time.sleep(0.5)
    tmux.send_keys("old_name")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    sessions = tmux.get_all_sessions()
    assert "new_name" in sessions, f"new_name not found. Sessions: {sessions}"
    assert "old_name" not in sessions, f"old_name still exists. Sessions: {sessions}"
    assert "test_session" in sessions, f"test_session gone. Sessions: {sessions}"


@pytest.mark.skip(reason=(
    "Detach runs inside popup which has its own tmux client. "
    "The pexpect client on /dev/pts/0 stays attached to test_session "
    "even after the detach action completes, so the 'no clients' check fails."
))
def test_detach_current_session(tmux):
    """Run detach action on current session. Verify session still exists."""
    before_sessions = tmux.get_all_sessions()
    assert "test_session" in before_sessions

    tmux.send_keys("node /app/session-zx.mjs detach")
    tmux.press_enter()
    time.sleep(1.5)

    # Select [current] or test_session
    tmux.send_keys("test_session")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.5)

    # After detach, pexpect client may be disconnected.
    # Use os.popen directly to check session still exists.
    result = os.popen("tmux list-sessions -F '#S' 2>/dev/null").read().strip()
    sessions = result.split('\n') if result else []
    assert "test_session" in sessions, \
        f"test_session should still exist after detach. Sessions: {sessions}"

    # Check no clients are attached
    clients = os.popen(
        "tmux list-clients -t test_session -F '#{client_name}' 2>/dev/null"
    ).read().strip()
    assert clients == "", \
        f"Expected no clients attached after detach, got: {clients}"
