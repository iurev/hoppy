"""Test that session-zx.py script executes correctly."""
import os
import time
import pexpect


def test_script_exists():
    """Verify the script file exists."""
    assert os.path.exists("session-zx.py")


def test_script_is_executable():
    """Verify the script has execute permissions."""
    assert os.access("session-zx.py", os.X_OK)


def test_script_runs_without_error():
    """Test that script can be executed without crashing."""
    # Run the script and immediately send ESC to cancel
    proc = pexpect.spawn("./session-zx.py", encoding='utf-8', timeout=10)

    try:
        # Wait for fzf to appear (look for prompt or header)
        proc.expect(r'>', timeout=5)
        time.sleep(0.3)

        # Send ESC to cancel
        proc.send('\x1b')
        time.sleep(0.2)

        # Script should exit cleanly
        proc.expect(pexpect.EOF, timeout=2)
        proc.close()

        # Exit code should be 0, 1 (canceled), or 130 (canceled with ESC)
        assert proc.exitstatus in [0, 1, 130], f"Unexpected exit code: {proc.exitstatus}"

    except pexpect.TIMEOUT:
        proc.close(force=True)
        raise AssertionError("Script did not show fzf prompt in time")


def test_script_shows_action_menu():
    """Test that script shows the action menu when run without arguments."""
    proc = pexpect.spawn("./session-zx.py", encoding='utf-8', timeout=10)

    try:
        # Wait for action menu header or prompt
        proc.expect(r'>', timeout=5)
        time.sleep(0.2)

        # Capture output
        output = proc.before + proc.after

        # Send ESC to cancel
        proc.send('\x1b')
        time.sleep(0.2)

        proc.expect(pexpect.EOF, timeout=2)
        proc.close()

        # Verify we saw something that looks like a menu
        assert '>' in output, "No fzf prompt found"

    except pexpect.TIMEOUT:
        proc.close(force=True)
        raise AssertionError("Script did not show action menu in time")
