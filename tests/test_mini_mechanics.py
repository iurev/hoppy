"""Mini-tests that prove the test rig AND the product work together.

Each one drives the real binary. If the binary stops working, the test fails.
"""
import os
import re
import time


def test_pexpect_can_reach_fzf_in_popup(tmux, create_sessions):
    """Prove that pexpect keys reach fzf inside a tmux popup.

    Breaks if: the popup never opens (no fzf process starts), or the keys
    pexpect sends do not reach fzf, so Enter does not switch to dummy_target.
    """
    create_sessions("dummy_target")

    # Run popup-switch via pexpect
    tmux.send_keys("/app/session-zx popup-switch")
    tmux.press_enter()

    assert tmux.wait_for_fzf_process(), "popup-switch did not start fzf"

    # Type a query, then accept it. Only real keys can select a row.
    tmux.send_keys("dummy")
    time.sleep(0.5)
    tmux.press_enter()

    assert tmux.wait_for_session_switch("dummy_target", timeout=4), (
        f"Keys did not reach fzf in the popup. Current: {tmux.get_current_session()}"
    )
    tmux.assert_session_exists("test_session")


def test_capture_pane_during_popup(tmux, create_sessions):
    """Document what capture-pane returns while a popup is open.

    Expectation: capture-pane sees the shell UNDER the popup, not popup content.

    Breaks if: the popup does not open (no fzf process), or capture-pane starts
    returning the popup overlay, which would silently change what every popup
    test can assert.
    """
    create_sessions("cap_target")

    # Run popup-switch
    tmux.send_keys("/app/session-zx popup-switch")
    tmux.press_enter()

    assert tmux.wait_for_fzf_process(), "popup-switch did not start fzf"

    # Try capture-pane while the popup is open
    content = tmux.get_pane_content("test_session")

    # Close popup
    tmux.press_escape()
    assert tmux.wait_for_fzf_gone(), "fzf still runs after Escape"

    print(f"\n--- capture-pane during popup ---\n{content}\n--- end ---")

    # capture-pane must show the shell pane, not the popup list.
    assert "Select target session" not in content, \
        "capture-pane unexpectedly includes the popup header."
    assert "cap_target @" not in content, \
        "capture-pane unexpectedly includes a popup session row."
    tmux.assert_current_session("test_session")


def test_switch_from_line_moves_the_client(tmux, create_sessions):
    """Drive the Ctrl+N preview helper straight from the command line.

    `switch-from-line` strips the '[N] ' prefix and the ' @ ...' suffix, writes
    the debounce state, and a detached child then switches the client (SPEC
    §3.5, §7).

    Breaks if: the row parsing changes, the debounce child is not spawned, or
    the delayed switch stops calling `tmux switch-client`.
    """
    create_sessions("detect_me")
    tmux.assert_current_session("test_session")

    os.system('/app/session-zx switch-from-line "[2] detect_me @ 1 windows"')

    assert tmux.wait_for_session_switch("detect_me", timeout=5), (
        f"switch-from-line did not move the client. "
        f"Current: {tmux.get_current_session()}"
    )


def test_send_keys_via_pexpect_reaches_fzf(tmux, create_sessions):
    """Prove pexpect can type into fzf running directly (not in a popup).

    We use 'switch' (not popup-switch) so capture-pane can see fzf content.

    Breaks if: fzf never lists the session rows, or typing stops filtering them.
    The matching row must stay on screen and the other row must go.
    """
    create_sessions("visible_sess", "hidden_sess")

    # Run switch directly (no popup)
    tmux.run_command("/app/session-zx switch")
    time.sleep(1.5)

    # Type some filter text
    tmux.send_keys("visible")
    time.sleep(0.5)

    content = tmux.strip_ansi(tmux.get_output())
    print(f"\n--- pane after typing 'visible' ---\n{content}\n--- end ---")

    assert re.search(r"visible_sess @ \d+ windows", content), (
        f"Matching session row not shown by fzf. Content:\n{content}"
    )
    assert "hidden_sess @" not in content, (
        f"fzf did not filter out the non-matching row. Content:\n{content}"
    )

    # Cleanup: press Escape to exit fzf
    tmux.press_escape()
    time.sleep(0.5)


def test_arrow_keys_work_in_fzf(tmux, create_sessions):
    """Prove arrow keys move the fzf cursor to the NEXT row, by name.

    Rows are [1] test_session (current, pinned), [2] arrow_a, [3] arrow_b.

    Breaks if: the arrow key stops moving the cursor, the current session stops
    being pinned to [1], or the number prefixes disappear.
    """
    create_sessions("arrow_a", "arrow_b")

    # Use --reverse so ArrowDown can move from top row to next row.
    tmux.run_command("FZF_DEFAULT_OPTS='--reverse' /app/session-zx switch")
    time.sleep(1.5)

    before = tmux.get_selected_row()
    assert before is not None, f"No fzf cursor on screen:\n{tmux.get_output()}"
    assert before.startswith("[1] test_session @"), (
        f"Cursor should start on '[1] test_session', got '{before}'"
    )

    tmux.press_arrow_down()
    time.sleep(0.4)

    after = tmux.get_selected_row()
    assert after is not None, f"No fzf cursor after arrow:\n{tmux.get_output()}"
    assert after.startswith("[2] arrow_a @"), (
        f"Arrow down should select '[2] arrow_a', got '{after}'"
    )

    # Cleanup
    tmux.press_escape()
    time.sleep(0.5)
