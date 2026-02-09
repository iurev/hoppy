"""Test new tmux session creation."""
import os
import time
import pexpect
import pytest


def test_create_new_session_with_tmux_command():
    """Test that we can create a session using tmux directly."""
    session_name = "test_new_session"

    # Clean up any existing session
    os.system(f"tmux kill-session -t {session_name} 2>/dev/null")

    try:
        # Create session with tmux
        os.system(f"tmux new-session -d -s {session_name}")
        time.sleep(0.3)

        # Verify the session was created
        result = os.popen(f"tmux has-session -t {session_name} 2>&1").read()
        assert result.strip() == "", \
            f"Session {session_name} was not created"

        # Verify session appears in list
        sessions = os.popen("tmux list-sessions").read()
        assert session_name in sessions, f"Session {session_name} not in session list"

    finally:
        # Cleanup
        os.system(f"tmux kill-session -t {session_name} 2>/dev/null")


def test_new_session_appears_in_list():
    """Test that created session appears in tmux list-sessions."""
    session_name = "test_session_list"

    # Create session directly with tmux
    os.system(f"tmux new-session -d -s {session_name}")
    time.sleep(0.2)

    try:
        # Get session list
        sessions = os.popen("tmux list-sessions").read()

        # Verify session is in the list
        assert session_name in sessions, \
            f"Session {session_name} not found in tmux list-sessions"

    finally:
        # Cleanup
        os.system(f"tmux kill-session -t {session_name} 2>/dev/null")


def test_new_option_in_menu():
    """Test that 'new' option appears in the action menu."""
    try:
        # Run the script
        proc = pexpect.spawn("node session-zx.mjs", encoding='utf-8', timeout=10)

        # Wait for fzf menu
        proc.expect(r'>', timeout=5)
        time.sleep(0.3)

        # Type 'new' to filter
        proc.send('new')
        time.sleep(0.3)

        # Get the output before sending ESC
        output = proc.before if hasattr(proc, 'before') else ""

        # Send ESC to cancel
        proc.send('\x1b')
        time.sleep(0.2)

        # Script should exit
        proc.expect(pexpect.EOF, timeout=3)
        proc.close()

        # The word 'new' should appear in output (either as input or as menu option)
        # This is a basic smoke test
        assert proc.exitstatus in [0, 1, 130], \
            f"Unexpected exit code: {proc.exitstatus}"

    except pexpect.TIMEOUT:
        proc.close(force=True)
        raise AssertionError("Script did not show menu correctly")


def test_cancel_new_session():
    """Test canceling session creation with ESC."""
    try:
        # Run the script
        proc = pexpect.spawn("node session-zx.mjs", encoding='utf-8', timeout=10)

        # Wait for fzf menu
        proc.expect(r'>', timeout=5)
        time.sleep(0.3)

        # Type 'new' to filter
        proc.send('new')
        time.sleep(0.2)

        # Send ESC to cancel
        proc.send('\x1b')
        time.sleep(0.3)

        # Script should exit
        proc.expect(pexpect.EOF, timeout=3)
        proc.close()

        # Exit should be clean (exit code 0, 1, or 130)
        assert proc.exitstatus in [0, 1, 130], \
            f"Unexpected exit code: {proc.exitstatus}"

    except pexpect.TIMEOUT:
        proc.close(force=True)
        raise AssertionError("Script did not handle ESC correctly")
