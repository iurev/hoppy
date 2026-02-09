"""REAL integration tests that actually test behavior, not just "script ran".

Refactored to strictly follow guideline.md and use TmuxSession fixture for REAL client simulation.
"""
import os
import time
import pytest
import shutil
import subprocess

# Helper to run shell commands
def run(cmd):
    return os.system(cmd)

@pytest.fixture
def git_repo_with_worktrees(tmp_path):
    """Setup a git repo with worktrees for testing worktree-switch."""
    # Create main repo
    repo_dir = tmp_path / "main_repo"
    repo_dir.mkdir()
    
    cwd = os.getcwd()
    try:
        os.chdir(repo_dir)
        subprocess.run(["git", "init"], check=True)
        # Fix for CI/Docker: Set identity
        subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "config", "user.name", "Test User"], check=True)
        
        subprocess.run(["git", "commit", "--allow-empty", "-m", "Initial commit"], check=True)
        
        # Create worktree
        wt_dir = tmp_path / "wt_branch"
        subprocess.run(["git", "worktree", "add", str(wt_dir), "-b", "feature/branch"], check=True)
        
        yield str(repo_dir), str(wt_dir)
    finally:
        os.chdir(cwd)

def test_session_switch_user_workflow(tmux):
    """
    Test the standard Ctrl+Shift+L user workflow (popup-switch).
    """
    # 'tmux' fixture provides a running client attached to 'test_session'
    client_pid = tmux.process.pid
    
    # Create target session
    run("tmux new-session -d -s switch_to")
    time.sleep(0.5)

    # Initial state check
    assert "switch_to" not in os.popen("tmux list-clients -F '#{session_name}'").read()

    # SIMULATE KEYBINDING: Ctrl+Shift+L triggers popup-switch
    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # User types 'switch_to'
    tmux.send_keys("switch_to")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    # VERIFY RESULT
    attached_sessions = os.popen("tmux list-clients -F '#{session_name}'").read()
    assert "switch_to" in attached_sessions, f"No client attached to switch_to. Attached: {attached_sessions}"

    # Cleanup
    run("tmux kill-session -t switch_to 2>/dev/null")

def test_capital_switch_user_workflow(tmux):
    """
    Test the Capital Switch workflow (Ctrl+Shift+O).
    """
    run("tmux new-session -d -s UPPER")
    time.sleep(0.5)

    # Trigger popup-capital-switch
    tmux.send_keys("node /app/session-zx.mjs popup-capital-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # Select UPPER
    tmux.send_keys("UPPER")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    # Verify
    attached_sessions = os.popen("tmux list-clients -F '#{session_name}'").read()
    assert "UPPER" in attached_sessions, "Client did not switch to UPPER"

    run("tmux kill-session -t UPPER 2>/dev/null")

def test_worktree_switch_user_workflow(tmux, git_repo_with_worktrees):
    """
    Test the Worktree Switch workflow (Ctrl+Shift+P).
    """
    main_path, wt_path = git_repo_with_worktrees
    
    tmux.send_keys(f"cd {main_path}")
    tmux.press_enter()
    time.sleep(0.5)
    
    # Create target session
    run(f"tmux new-session -d -s feature -c {wt_path}")
    run("tmux new-session -d -s other -c /tmp")
    time.sleep(0.5)

    # Trigger popup-worktree-switch
    tmux.send_keys("node /app/session-zx.mjs popup-worktree-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # Filter for 'feature'
    tmux.send_keys("feature")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    # Verify switch to feature
    attached_sessions = os.popen("tmux list-clients -F '#{session_name}'").read()
    assert "feature" in attached_sessions, "Did not switch to worktree session"
    
    # Test Isolation
    tmux.send_keys("node /app/session-zx.mjs popup-worktree-switch")
    tmux.press_enter()
    time.sleep(1.5)
    
    tmux.send_keys("other") 
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)
    
    attached_sessions = os.popen("tmux list-clients -F '#{session_name}'").read()
    assert "feature" in attached_sessions, "Should not have switched to unrelated session"

    run("tmux kill-session -t feature 2>/dev/null")
    run("tmux kill-session -t other 2>/dev/null")

def test_number_key_quick_select(tmux):
    """Test that pressing number keys in popup actually selects the specific session."""
    # Ensure a clean state for frecency so order is predictable (num_1 then num_2)
    run("rm -rf .session-frecency")
    
    run("tmux new-session -d -s num_1")
    run("tmux new-session -d -s num_2")
    time.sleep(0.5)

    # Initial: we are in test_session
    attached_before = os.popen("tmux list-clients -F '#{session_name}'").read().strip()
    assert attached_before == "test_session"

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    # In a fresh state:
    # [1] test_session (current)
    # [2] num_1
    # [3] num_2
    tmux.press_number(2)
    time.sleep(1.0)

    attached_after = os.popen("tmux list-clients -F '#{session_name}'").read().strip()
    assert attached_after == "num_1", f"Expected to switch to num_1, but now in {attached_after}"

    run("tmux kill-session -t num_1 2>/dev/null")
    run("tmux kill-session -t num_2 2>/dev/null")

def test_kill_session_workflow(tmux):
    """
    Test killing a session via DEL key in the popup.
    """
    run("tmux new-session -d -s victim_session")
    time.sleep(0.5)

    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)

    tmux.send_keys("victim_session")
    time.sleep(0.5)

    # Press DEL (Send explicit Delete sequence for fzf)
    tmux.send_keys('\x1b[3~')
    time.sleep(1.0)

    # NO confirmation for 'switch' action DEL binding
    # Verify victim is gone
    sessions = os.popen("tmux list-sessions -F '#S'").read()
    assert "victim_session" not in sessions

def test_new_session_action(tmux):
    """
    Test creating a new session via the 'new' action.
    """
    tmux.send_keys("node /app/session-zx.mjs new")
    tmux.press_enter()
    time.sleep(2.0) # Wait for split window
    
    # Write to FIFO directly to simulate user input
    # This bypasses the split-window UI which is flaky in tests
    run("echo brand_new_session > /tmp/tmux_fzf_session_name")
    time.sleep(1.0)
    
    attached = os.popen("tmux list-clients -F '#{session_name}'").read()
    assert "brand_new_session" in attached
    
    run("tmux kill-session -t brand_new_session 2>/dev/null")

def test_rename_session_action(tmux):
    """Test renaming current session."""
    tmux.send_keys("node /app/session-zx.mjs rename")
    tmux.press_enter()
    time.sleep(2.0) # Wait for script to block on FIFO
    
    # Write to FIFO
    run("echo renamed_session > /tmp/tmux_fzf_session_name")
    time.sleep(0.5)
    
    # Select target (current session)
    # fzf appears now
    time.sleep(0.5)
    tmux.send_keys("test_session")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)
    
    sessions = os.popen("tmux list-sessions -F '#S'").read()
    assert "renamed_session" in sessions
    assert "test_session" not in sessions
    
    run("tmux kill-session -t renamed_session 2>/dev/null")

def test_escape_cancels_action(tmux):
    """Test that ESC closes the popup/fzf and remains in the current session."""
    # Start in test_session
    attached_before = os.popen("tmux list-clients -F '#{session_name}'").read().strip()
    assert attached_before == "test_session"
    
    # Create another session to ensure we don't accidentally switch to it
    run("tmux new-session -d -s other_session")
    
    tmux.send_keys("node /app/session-zx.mjs popup-switch")
    tmux.press_enter()
    time.sleep(1.5)
    
    # Type something to filter
    tmux.send_keys("other_session")
    time.sleep(0.5)
    
    # Press ESC
    tmux.press_escape()
    time.sleep(0.5)
    
    # Verify we are STILL in test_session and NOT in other_session
    attached_after = os.popen("tmux list-clients -F '#{session_name}'").read().strip()
    assert attached_after == "test_session", f"Expected to stay in test_session, but now in {attached_after}"
    
    run("tmux kill-session -t other_session 2>/dev/null")

def test_menu_cancel_option(tmux):
    """Test that selecting [cancel] from the action menu works."""
    attached_before = os.popen("tmux list-clients -F '#{session_name}'").read().strip()
    
    # Run script without args to show action menu
    tmux.send_keys("node /app/session-zx.mjs")
    tmux.press_enter()
    time.sleep(1.0)
    
    # Type cancel to filter for [cancel]
    tmux.send_keys("cancel")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(0.5)
    
    # Verify we are still in the same session
    attached_after = os.popen("tmux list-clients -F '#{session_name}'").read().strip()
    assert attached_after == attached_before

def test_frecency_sorting(tmux):
    """
    Test that frequently accessed sessions appear first in the list.
    """
    run("tmux new-session -d -s rarely")
    run("tmux new-session -d -s often")
    time.sleep(0.5)

    # Boost 'often' session score by switching to it multiple times using the script
    # We use popup-switch because it's the standard entry point
    
    for _ in range(3):
        # We are currently in 'test_session' (from fixture) or 'often'
        
        # Open popup
        tmux.send_keys("node /app/session-zx.mjs popup-switch")
        tmux.press_enter()
        time.sleep(1.0) # Wait for fzf
        
        # Filter for 'often'
        tmux.send_keys("often")
        time.sleep(0.5)
        tmux.press_enter()
        time.sleep(1.0) # Wait for switch
        
        # Switch back to 'test_session' using raw tmux for speed/reset
        # This ensures we are ready for the next iteration's "switch to often"
        run("tmux switch-client -t test_session")
        time.sleep(0.5)

    # Now check the order using reload-sessions
    output = os.popen("node /app/session-zx.mjs reload-sessions").read()
    lines = output.strip().split('\n')
    
    often_idx = next((i for i, l in enumerate(lines) if "often" in l), -1)
    rarely_idx = next((i for i, l in enumerate(lines) if "rarely" in l), -1)
            
    assert often_idx != -1 and rarely_idx != -1, "Sessions not found in output"
    assert often_idx < rarely_idx, f"Frecency failed: 'often' ({often_idx}) should be before 'rarely' ({rarely_idx})"

    run("tmux kill-session -t rarely 2>/dev/null")
    run("tmux kill-session -t often 2>/dev/null")
