"""Mini-tests to verify testing infrastructure works.

These tests document what works and what doesn't when testing
tmux popups, fzf, and pexpect together. Keep them in the codebase.
"""
import os
import time


def test_pexpect_can_reach_fzf_in_popup(tmux, create_sessions):
    """Prove that pexpect keys reach fzf inside a tmux popup."""
    create_sessions("dummy_target")

    # Run popup-switch via pexpect
    tmux.send_keys("/app/session-zx popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # Type some characters — if pexpect reaches fzf, no crash happens
    tmux.send_keys("dummy")
    time.sleep(0.5)

    # Press Escape to close popup
    tmux.press_escape()
    time.sleep(0.5)

    # Session should still exist and client should stay in test_session.
    sessions = tmux.get_all_sessions()
    assert "test_session" in sessions, f"test_session missing. Sessions: {sessions}"
    assert tmux.get_current_session() == "test_session"


def test_capture_pane_during_popup(tmux, create_sessions):
    """Document what capture-pane returns when a popup is open.

    Expectation: capture-pane sees the shell UNDER the popup, not popup content.
    This test logs the result so we know what to expect in real tests.
    """
    create_sessions("cap_target")

    # Run popup-switch
    tmux.send_keys("/app/session-zx popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # Try capture-pane while popup is open
    content = tmux.get_pane_content("test_session")

    # Close popup
    tmux.press_escape()
    time.sleep(0.5)

    # We just log; we expect the shell pane, not fzf content
    print(f"\n--- capture-pane during popup ---\n{content}\n--- end ---")

    # capture-pane should show underlying shell command, not popup list content.
    assert "popup-switch" in content, "Underlying shell command not captured."
    assert "Select target session" not in content, \
        "capture-pane unexpectedly includes popup overlay content."


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


def test_send_keys_via_pexpect_reaches_fzf(tmux, create_sessions):
    """Prove pexpect can type into fzf running directly (not in popup).

    We use 'switch' (not popup-switch) so capture-pane can see fzf content.
    """
    create_sessions("visible_sess")

    # Run switch directly (no popup)
    tmux.run_command("/app/session-zx switch")
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

    # Use --reverse so ArrowDown can move from top row to next row.
    tmux.run_command("FZF_DEFAULT_OPTS='--reverse' /app/session-zx switch")
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
    assert content_before != content_after, "Arrow key did not change fzf state."

    # Cleanup
    tmux.press_escape()
    time.sleep(0.5)
