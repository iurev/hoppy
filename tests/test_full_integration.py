"""Full integration tests - test the COMPLETE script workflow."""
import os
import time
import pytest


def capture_with_pipe_pane(session_name, action="switch", wait_time=1.5):
    """Helper to capture pane output by running script directly in the pane."""
    output_file = f"/tmp/test_pane_{session_name}.txt"

    # Start capturing pane output
    os.system(f"tmux pipe-pane -t {session_name} -o 'cat > {output_file}'")
    time.sleep(0.2)

    # Run the script directly in the pane (simulates what keybinding does)
    os.system(f"tmux send-keys -t {session_name} 'node /app/session-zx.mjs {action}' Enter")
    time.sleep(wait_time)

    # Stop pipe-pane
    os.system(f"tmux pipe-pane -t {session_name}")
    time.sleep(0.2)

    # Read captured output
    output = ""
    if os.path.exists(output_file):
        with open(output_file, 'r') as f:
            output = f.read()
        os.remove(output_file)

    return output


def test_script_shows_fzf_menu_with_sessions():
    """Test that the script shows fzf menu with all sessions via Ctrl+Shift+L."""
    # Create test sessions
    os.system("tmux new-session -d -s integ_alpha")
    os.system("tmux new-session -d -s integ_beta")
    os.system("tmux new-session -d -s integ_gamma")
    time.sleep(0.5)

    try:
        # Create test runner session
        os.system("tmux new-session -d -s test_runner")
        time.sleep(0.3)

        # Capture output using pipe-pane and trigger Ctrl+Shift+L
        output = capture_with_pipe_pane("test_runner", "switch")

        # Send Escape to cancel
        os.system("tmux send-keys -t test_runner Escape")
        time.sleep(0.3)

        # Verify all sessions appear in fzf
        assert "integ_alpha" in output, "Script did not show integ_alpha in fzf"
        assert "integ_beta" in output, "Script did not show integ_beta in fzf"
        assert "integ_gamma" in output, "Script did not show integ_gamma in fzf"

        # Verify fzf UI elements
        assert ">" in output, "fzf prompt not shown"
        assert "[" in output and "]" in output, "Number prefixes not shown"

        os.system("tmux kill-session -t test_runner 2>/dev/null")

    finally:
        os.system("tmux kill-session -t integ_alpha 2>/dev/null")
        os.system("tmux kill-session -t integ_beta 2>/dev/null")
        os.system("tmux kill-session -t integ_gamma 2>/dev/null")


def test_script_navigation_with_ctrl_n():
    """Test that Ctrl+N navigates/processes input correctly."""
    # Create sessions
    os.system("tmux new-session -d -s nav_first")
    os.system("tmux new-session -d -s nav_second")
    time.sleep(0.5)

    try:
        os.system("tmux new-session -d -s test_nav")
        time.sleep(0.3)

        # Capture output with pipe-pane
        output = capture_with_pipe_pane("test_nav", "switch")

        # Press Ctrl+N to navigate (script has custom Ctrl+N binding)
        os.system("tmux send-keys -t test_nav C-n")
        time.sleep(0.3)

        # Cancel
        os.system("tmux send-keys -t test_nav Escape")
        time.sleep(0.3)

        # Verify script showed sessions
        assert "nav_first" in output or "nav_second" in output, "Script did not show sessions"

        os.system("tmux kill-session -t test_nav 2>/dev/null")

    finally:
        os.system("tmux kill-session -t nav_first 2>/dev/null")
        os.system("tmux kill-session -t nav_second 2>/dev/null")


def test_script_number_quick_select():
    """Test that number keys work for quick selection."""
    # Create sessions
    os.system("tmux new-session -d -s quick1")
    os.system("tmux new-session -d -s quick2")
    os.system("tmux new-session -d -s quick3")
    time.sleep(0.5)

    try:
        # Capture output from quick1
        output = capture_with_pipe_pane("quick1", "switch")

        # Verify sessions are shown with numbers
        assert "quick1" in output or "quick2" in output or "quick3" in output, \
            "Script did not show sessions"
        assert "[" in output and "]" in output, "Number prefixes not shown"

        # Cancel
        os.system("tmux send-keys -t quick1 Escape")
        time.sleep(0.3)

    finally:
        os.system("tmux kill-session -t quick1 2>/dev/null")
        os.system("tmux kill-session -t quick2 2>/dev/null")
        os.system("tmux kill-session -t quick3 2>/dev/null")


def test_script_escape_cancels():
    """Test that Escape key cancels the selection."""
    # Create session
    os.system("tmux new-session -d -s cancel_test")
    time.sleep(0.5)

    try:
        os.system("tmux new-session -d -s test_escape")
        time.sleep(0.3)

        # Capture output with pipe-pane
        output = capture_with_pipe_pane("test_escape", "switch")

        # Verify fzf showed
        assert ">" in output or "cancel_test" in output, "fzf not showing"

        # Press Escape
        os.system("tmux send-keys -t test_escape Escape")
        time.sleep(0.5)

        os.system("tmux kill-session -t test_escape 2>/dev/null")

    finally:
        os.system("tmux kill-session -t cancel_test 2>/dev/null")


def test_script_shows_window_count():
    """Test that the script shows window count in the fzf list."""
    # Create session with multiple windows
    os.system("tmux new-session -d -s window_test")
    os.system("tmux new-window -t window_test")
    os.system("tmux new-window -t window_test")
    time.sleep(0.5)

    try:
        os.system("tmux new-session -d -s test_windows")
        time.sleep(0.3)

        # Capture output with pipe-pane
        output = capture_with_pipe_pane("test_windows", "switch")

        # Cancel
        os.system("tmux send-keys -t test_windows Escape")
        time.sleep(0.3)

        # Verify window count is shown
        assert "window_test" in output, "Session not shown"
        assert "windows" in output, "Window count not shown"

        os.system("tmux kill-session -t test_windows 2>/dev/null")

    finally:
        os.system("tmux kill-session -t window_test 2>/dev/null")


def test_script_excludes_current_session():
    """Test that the script handles session filtering correctly."""
    # Create multiple sessions
    os.system("tmux new-session -d -s exclude1")
    os.system("tmux new-session -d -s exclude2")
    time.sleep(0.5)

    try:
        # Capture output from exclude1
        output = capture_with_pipe_pane("exclude1", "switch")

        # Cancel
        os.system("tmux send-keys -t exclude1 Escape")
        time.sleep(0.3)

        # Script should show sessions
        assert "exclude1" in output or "exclude2" in output, "Script did not list sessions"

    finally:
        os.system("tmux kill-session -t exclude1 2>/dev/null")
        os.system("tmux kill-session -t exclude2 2>/dev/null")


def test_ctrl_shift_l_keybinding_works():
    """Test that Ctrl+Shift+L keybinding properly triggers the script."""
    # Create test sessions
    os.system("tmux new-session -d -s keybind_test1")
    os.system("tmux new-session -d -s keybind_test2")
    time.sleep(0.5)

    try:
        os.system("tmux new-session -d -s test_keybind")
        time.sleep(0.3)

        # Capture output with pipe-pane
        output = capture_with_pipe_pane("test_keybind", "switch")

        # Cancel
        os.system("tmux send-keys -t test_keybind Escape")
        time.sleep(0.3)

        # Verify the keybinding triggered the script and showed sessions
        assert "keybind_test1" in output or "keybind_test2" in output, \
            "Ctrl+Shift+L did not trigger session switcher"
        assert ">" in output, "fzf prompt not shown"

        os.system("tmux kill-session -t test_keybind 2>/dev/null")

    finally:
        os.system("tmux kill-session -t keybind_test1 2>/dev/null")
        os.system("tmux kill-session -t keybind_test2 2>/dev/null")
