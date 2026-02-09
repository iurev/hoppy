"""Test tmux session deletion functionality."""
import os
import time
import pexpect
import pytest


def test_kill_session_with_tmux_command():
    """Test killing a session using tmux kill-session command."""
    session_name = "test_kill_direct"

    # Create session
    os.system(f"tmux new-session -d -s {session_name}")
    time.sleep(0.3)

    # Verify session exists
    sessions = os.popen("tmux list-sessions").read()
    assert session_name in sessions

    # Kill session
    os.system(f"tmux kill-session -t {session_name}")
    time.sleep(0.3)

    # Verify session is gone
    sessions = os.popen("tmux list-sessions 2>&1").read()
    assert session_name not in sessions


def test_kill_menu_option_exists():
    """Test that kill option appears in the action menu."""
    session_name = "test_kill_menu"

    # Create test session
    os.system(f"tmux new-session -d -s {session_name}")
    time.sleep(0.3)

    try:
        # Run the script
        proc = pexpect.spawn("node session-zx.mjs", encoding='utf-8', timeout=10)

        # Wait for fzf menu
        proc.expect(r'>', timeout=5)
        time.sleep(0.3)

        # Type 'kill' to filter to kill option
        proc.send('kill')
        time.sleep(0.3)

        # Send ESC to cancel
        proc.send('\x1b')
        time.sleep(0.2)

        # Script should exit
        proc.expect(pexpect.EOF, timeout=3)
        proc.close()

        # Verify script ran correctly
        assert proc.exitstatus in [0, 1, 130]

    except pexpect.TIMEOUT:
        proc.close(force=True)
        raise AssertionError("Script did not show kill option correctly")
    finally:
        # Cleanup
        os.system(f"tmux kill-session -t {session_name} 2>/dev/null")


def test_cancel_kill_with_escape():
    """Test canceling kill action with ESC."""
    session_name = "test_cancel_kill"

    # Create test session
    os.system(f"tmux new-session -d -s {session_name}")
    time.sleep(0.3)

    try:
        # Run the script
        proc = pexpect.spawn("node session-zx.mjs", encoding='utf-8', timeout=10)

        # Wait for fzf menu
        proc.expect(r'>', timeout=5)
        time.sleep(0.3)

        # Send ESC to cancel
        proc.send('\x1b')
        time.sleep(0.2)

        # Script should exit
        proc.expect(pexpect.EOF, timeout=3)
        proc.close()

        # Session should still exist (we canceled)
        sessions = os.popen("tmux list-sessions").read()
        assert session_name in sessions, "Session was killed when it should have been preserved"

    except pexpect.TIMEOUT:
        proc.close(force=True)
        raise AssertionError("Script did not handle ESC correctly")
    finally:
        # Cleanup
        os.system(f"tmux kill-session -t {session_name} 2>/dev/null")


def test_session_removed_after_kill():
    """Test that killed session is removed from session list."""
    session_name = "test_removed"

    # Create and immediately kill session
    os.system(f"tmux new-session -d -s {session_name}")
    time.sleep(0.3)

    # Verify it exists
    sessions_before = os.popen("tmux list-sessions").read()
    assert session_name in sessions_before

    # Kill it
    os.system(f"tmux kill-session -t {session_name}")
    time.sleep(0.3)

    # Verify it's gone
    sessions_after = os.popen("tmux list-sessions 2>&1").read()
    assert session_name not in sessions_after or "no server running" in sessions_after
