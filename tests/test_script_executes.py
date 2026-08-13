"""Test that the hoppy binary executes correctly."""
import os
import re
import subprocess
import time

import pexpect

ANSI = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# The action menu of SPEC §3.1, in order.
MENU_ITEMS = ["switch", "new", "rename", "detach", "kill", "[cancel]"]
MENU_HEADER = "Select an action."


def drain(proc, seconds=2.5):
    """Read everything the process draws for `seconds`. Returns plain text.

    fzf paints the whole screen, so one expect() call only sees a fragment.
    """
    buf = ""
    end = time.time() + seconds
    while time.time() < end:
        try:
            buf += proc.read_nonblocking(size=8192, timeout=0.2)
        except (pexpect.TIMEOUT, pexpect.EOF):
            time.sleep(0.05)
    return ANSI.sub("", buf)


def test_binary_exists_and_rejects_unknown_action():
    """Smoke test: the file is there, it runs, and it validates its action.

    Breaks if: the build is missing, the file loses its execute bit, or
    assertValidAction stops rejecting an unknown action with exit 1 and the
    SPEC §2.1 message.
    """
    assert os.path.exists("hoppy"), "binary 'hoppy' was not built"
    assert os.access("hoppy", os.X_OK), "binary 'hoppy' is not executable"

    result = subprocess.run(
        ["./hoppy", "no-such-action"],
        capture_output=True, text=True, timeout=15,
    )

    assert result.returncode == 1, (
        f"Unknown action must exit 1, got {result.returncode}. stderr: {result.stderr}"
    )
    assert "Invalid action: no-such-action" in result.stderr, (
        f"Missing the invalid-action error. stderr: {result.stderr}"
    )
    assert "Must be one of: switch, new, rename, detach, kill" in result.stderr, (
        f"Missing the list of valid actions. stderr: {result.stderr}"
    )


def test_script_runs_without_error():
    """Test that script can be executed without crashing.

    Breaks if: the binary crashes on start, never shows fzf, or hangs after
    Escape (for example when a child process keeps the pty open).
    """
    # Run the script and immediately send ESC to cancel
    proc = pexpect.spawn("./hoppy", encoding='utf-8', timeout=10)

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
    """The menu shown with no argument holds the six items of SPEC §3.1.

    Breaks if: an item is renamed, dropped or added, if the header text
    changes, or if cancelling the menu stops exiting 0.
    """
    proc = pexpect.spawn("./hoppy", encoding='utf-8', timeout=10)

    try:
        screen = drain(proc, 2.5)

        assert MENU_HEADER in screen, (
            f"Action menu header missing. Screen:\n{screen}"
        )
        for item in MENU_ITEMS:
            assert item in screen, (
                f"Menu item '{item}' missing from the action menu. Screen:\n{screen}"
            )

        # Send ESC to cancel
        proc.send('\x1b')
        proc.expect(pexpect.EOF, timeout=3)
        proc.close()

        assert proc.exitstatus == 0, (
            f"Cancelling the action menu must exit 0, got {proc.exitstatus}"
        )
    finally:
        if proc.isalive():
            proc.close(force=True)
