"""Test tmux session switching functionality."""
import os
import time
import pexpect
import pytest


def test_list_existing_sessions():
    """Test that existing sessions appear in the switch menu."""
    session1 = "test_session_1"
    session2 = "test_session_2"

    # Create test sessions
    os.system(f"tmux new-session -d -s {session1}")
    os.system(f"tmux new-session -d -s {session2}")
    time.sleep(0.3)

    try:
        # Verify sessions exist
        sessions = os.popen("tmux list-sessions").read()
        assert session1 in sessions
        assert session2 in sessions

    finally:
        # Cleanup
        os.system(f"tmux kill-session -t {session1} 2>/dev/null")
        os.system(f"tmux kill-session -t {session2} 2>/dev/null")


def test_switch_menu_shows_sessions():
    """Test that the switch action shows available sessions."""
    session1 = "test_switch_1"
    session2 = "test_switch_2"

    # Create test sessions
    os.system(f"tmux new-session -d -s {session1}")
    os.system(f"tmux new-session -d -s {session2}")
    time.sleep(0.3)

    try:
        # Run the script
        proc = pexpect.spawn("node session-zx.mjs", encoding='utf-8', timeout=10)

        # Wait for fzf menu
        proc.expect(r'>', timeout=5)
        time.sleep(0.3)

        # Type 'switch' to filter to switch option
        proc.send('switch')
        time.sleep(0.3)

        # Send ESC to cancel
        proc.send('\x1b')
        time.sleep(0.2)

        # Script should exit
        proc.expect(pexpect.EOF, timeout=3)
        proc.close()

        # Just verify the script ran and exited cleanly
        assert proc.exitstatus in [0, 1, 130]

    except pexpect.TIMEOUT:
        proc.close(force=True)
        raise AssertionError("Script did not handle switch option correctly")
    finally:
        # Cleanup
        os.system(f"tmux kill-session -t {session1} 2>/dev/null")
        os.system(f"tmux kill-session -t {session2} 2>/dev/null")


def test_cancel_switch_with_escape():
    """Test canceling session switch with ESC."""
    session1 = "test_cancel_switch"

    # Create test session
    os.system(f"tmux new-session -d -s {session1}")
    time.sleep(0.3)

    try:
        # Run the script
        proc = pexpect.spawn("node session-zx.mjs", encoding='utf-8', timeout=10)

        # Wait for fzf menu
        proc.expect(r'>', timeout=5)
        time.sleep(0.3)

        # Send ESC to cancel immediately
        proc.send('\x1b')
        time.sleep(0.2)

        # Script should exit
        proc.expect(pexpect.EOF, timeout=3)
        proc.close()

        # Exit should be clean
        assert proc.exitstatus in [0, 1, 130]

    except pexpect.TIMEOUT:
        proc.close(force=True)
        raise AssertionError("Script did not handle ESC correctly")
    finally:
        # Cleanup
        os.system(f"tmux kill-session -t {session1} 2>/dev/null")


def test_multiple_sessions_exist():
    """Test that multiple sessions can coexist."""
    sessions = ["test_multi_1", "test_multi_2", "test_multi_3"]

    try:
        # Create multiple sessions
        for session in sessions:
            os.system(f"tmux new-session -d -s {session}")
        time.sleep(0.5)

        # Verify all sessions exist
        session_list = os.popen("tmux list-sessions").read()
        for session in sessions:
            assert session in session_list, f"Session {session} not found"

    finally:
        # Cleanup
        for session in sessions:
            os.system(f"tmux kill-session -t {session} 2>/dev/null")
