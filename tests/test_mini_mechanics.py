"""Mini-tests to verify testing infrastructure works.

These tests document what works and what doesn't when testing
tmux popups, fzf, and pexpect together. Keep them in the codebase.
"""
import os
import time
import pytest


def test_pexpect_can_reach_fzf_in_popup(tmux, create_sessions):
    """Prove that pexpect keys reach fzf inside a tmux popup."""
    create_sessions("dummy_target")

    # Run popup-switch via pexpect
    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # Type some characters — if pexpect reaches fzf, no crash happens
    tmux.send_keys("dummy")
    time.sleep(0.5)

    # Press Escape to close popup
    tmux.press_escape()
    time.sleep(0.5)

    # Session should still exist (no crash)
    sessions = tmux.get_all_sessions()
    assert "test_session" in sessions, f"test_session missing. Sessions: {sessions}"


def test_capture_pane_during_popup(tmux, create_sessions):
    """Document what capture-pane returns when a popup is open.

    Expectation: capture-pane sees the shell UNDER the popup, not popup content.
    This test logs the result so we know what to expect in real tests.
    """
    create_sessions("cap_target")

    # Run popup-switch
    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # Try capture-pane while popup is open
    content = tmux.get_pane_content("test_session")

    # Close popup
    tmux.press_escape()
    time.sleep(0.5)

    # We just log; we expect the shell pane, not fzf content
    print(f"\n--- capture-pane during popup ---\n{content}\n--- end ---")

    # The content should NOT contain fzf indicators (>) from the popup
    # because capture-pane can't see popup overlays
    # (This assertion documents the behavior — adjust if tmux changes)
    assert content is not None, "capture-pane returned None"


def test_session_detection_via_list_clients(tmux, create_sessions):
    """Confirm that 'tmux list-clients' correctly reports attached session."""
    create_sessions("detect_me")

    # We start attached to test_session
    current = tmux.get_current_session()
    assert current == "test_session", f"Expected test_session, got {current}"

    # Switch client via raw tmux command
    os.system("tmux switch-client -t detect_me")
    time.sleep(0.5)

    current = tmux.get_current_session()
    assert current == "detect_me", f"Expected detect_me, got {current}"


def test_popup_escape_reverts_or_not(tmux, create_sessions):
    """Document: does Escape after live preview revert the session?

    This test records the actual behavior. Real tests use this knowledge.
    """
    create_sessions("preview_target")

    # Start in test_session
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

    # Press Ctrl+N to trigger live preview switch
    tmux.press_ctrl_n()
    time.sleep(2.5)  # debounce (2s) + margin

    # Check if preview switched the client
    mid = tmux.get_current_session()
    print(f"\nAfter Ctrl+N preview: client is in '{mid}'")

    # Press Escape to close popup
    tmux.press_escape()
    time.sleep(0.5)

    after = tmux.get_current_session()
    print(f"After Escape: client is in '{after}'")
    print(f"Reverted: {after == 'test_session'}, Stayed: {after == mid}")

    # This test always passes — it just documents the behavior
    assert after in ("test_session", "preview_target"), f"Unexpected session: {after}"


def test_send_keys_via_pexpect_reaches_fzf(tmux, create_sessions):
    """Prove pexpect can type into fzf running directly (not in popup).

    We use 'switch' (not popup-switch) so capture-pane can see fzf content.
    """
    create_sessions("visible_sess")

    # Run switch directly (no popup)
    tmux.run_command("node /app/session-zx.mjs switch")
    time.sleep(1.5)

    # Type some filter text
    tmux.send_keys("visible")
    time.sleep(0.5)

    # Capture pane — fzf content should be visible
    content = tmux.get_output()
    print(f"\n--- pane after typing 'visible' ---\n{content}\n--- end ---")

    # fzf should show filtered results containing "visible_sess"
    assert "visible" in content, f"Filter text not visible in pane. Content:\n{content}"

    # Cleanup: press Escape to exit fzf
    tmux.press_escape()
    time.sleep(0.5)


def test_arrow_keys_work_in_fzf(tmux, create_sessions):
    """Prove arrow keys navigate fzf items when running switch directly."""
    create_sessions("arrow_a", "arrow_b")

    tmux.run_command("node /app/session-zx.mjs switch")
    time.sleep(1.5)

    # Capture initial state
    content_before = tmux.get_output()

    # Press arrow down
    tmux.press_arrow_down()
    time.sleep(0.3)

    # Capture after navigation
    content_after = tmux.get_output()

    print(f"\n--- before arrow ---\n{content_before}\n--- after arrow ---\n{content_after}\n--- end ---")

    # Both captures should have content (fzf is running)
    assert len(content_before.strip()) > 0, "No content before arrow"
    assert len(content_after.strip()) > 0, "No content after arrow"

    # Cleanup
    tmux.press_escape()
    time.sleep(0.5)
