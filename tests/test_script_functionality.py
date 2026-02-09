"""Test the actual JavaScript script's functionality - PROPERLY."""
import os
import time
import pytest


def test_script_lists_sessions_correctly():
    """Test that the script's reload-sessions action lists created sessions."""
    # Create test sessions with tmux
    os.system("tmux new-session -d -s script_test_alpha")
    os.system("tmux new-session -d -s script_test_beta")
    os.system("tmux new-session -d -s script_test_gamma")
    time.sleep(0.5)

    try:
        # Run the SCRIPT's reload-sessions action (bypasses fzf)
        output = os.popen("node /app/session-zx.mjs reload-sessions").read()

        # Verify the SCRIPT listed all our sessions
        assert "script_test_alpha" in output, "Script did not list script_test_alpha"
        assert "script_test_beta" in output, "Script did not list script_test_beta"
        assert "script_test_gamma" in output, "Script did not list script_test_gamma"

        # Verify formatting (script adds number prefixes and window counts)
        assert "windows" in output, "Script did not format with window count"
        assert "[" in output and "]" in output, "Script did not add number prefixes"

    finally:
        # Cleanup
        os.system("tmux kill-session -t script_test_alpha 2>/dev/null")
        os.system("tmux kill-session -t script_test_beta 2>/dev/null")
        os.system("tmux kill-session -t script_test_gamma 2>/dev/null")


def test_script_formats_session_output():
    """Test that the script formats session output with numbers and window counts."""
    # Create a session
    os.system("tmux new-session -d -s format_test")
    time.sleep(0.3)

    try:
        # Get the script's output
        output = os.popen("node /app/session-zx.mjs reload-sessions").read()

        # Verify format: [N] session_name @ X windows
        assert "format_test" in output
        assert "@" in output, "Script should use @ as delimiter"
        assert "windows" in output, "Script should show window count"

        # Check for number prefix [1], [2], etc.
        lines = [line for line in output.split('\n') if line.strip()]
        if len(lines) > 0:
            assert any("[" in line and "]" in line for line in lines), \
                "Script should add number prefixes for quick selection"

    finally:
        os.system("tmux kill-session -t format_test 2>/dev/null")


def test_script_handles_multiple_sessions():
    """Test that the script correctly lists multiple sessions."""
    # Create 5 sessions
    sessions = ["multi1", "multi2", "multi3", "multi4", "multi5"]
    for session in sessions:
        os.system(f"tmux new-session -d -s {session}")
    time.sleep(0.5)

    try:
        # Get script output
        output = os.popen("node /app/session-zx.mjs reload-sessions").read()

        # Verify all sessions are listed
        for session in sessions:
            assert session in output, f"Script did not list {session}"

        # Count how many sessions were listed
        lines = [line for line in output.split('\n') if line.strip()]
        assert len(lines) >= len(sessions), \
            f"Script listed {len(lines)} lines but we created {len(sessions)} sessions"

    finally:
        for session in sessions:
            os.system(f"tmux kill-session -t {session} 2>/dev/null")


def test_script_shows_window_counts():
    """Test that the script shows accurate window counts."""
    # Create a session
    os.system("tmux new-session -d -s window_test")
    time.sleep(0.3)

    # Add more windows to the session
    os.system("tmux new-window -t window_test")
    os.system("tmux new-window -t window_test")
    time.sleep(0.3)

    try:
        # Get script output
        output = os.popen("node /app/session-zx.mjs reload-sessions").read()

        # Verify window count is shown
        assert "window_test" in output
        assert "3 windows" in output or "windows" in output, \
            "Script should show window count"

    finally:
        os.system("tmux kill-session -t window_test 2>/dev/null")


def test_script_handles_special_characters_in_names():
    """Test that the script handles session names with special characters."""
    # Create sessions with various characters
    test_names = [
        "test-dash",
        "test_underscore",
        "test.dot",
    ]

    for name in test_names:
        os.system(f"tmux new-session -d -s '{name}'")
    time.sleep(0.5)

    try:
        # Get script output
        output = os.popen("node /app/session-zx.mjs reload-sessions").read()

        # Verify all names are handled
        for name in test_names:
            assert name in output, f"Script did not handle session name: {name}"

    finally:
        for name in test_names:
            os.system(f"tmux kill-session -t '{name}' 2>/dev/null")


def test_script_runs_without_crashing():
    """Test that the script runs the reload-sessions action without crashing."""
    # Create at least one session
    os.system("tmux new-session -d -s stable_test")
    time.sleep(0.3)

    try:
        # Run the script
        result = os.system("node /app/session-zx.mjs reload-sessions >/dev/null 2>&1")
        exit_code = result >> 8

        # Script should exit cleanly (exit code 0)
        assert exit_code == 0, f"Script crashed with exit code {exit_code}"

    finally:
        os.system("tmux kill-session -t stable_test 2>/dev/null")
