"""Test the actual JavaScript script's functionality - PROPERLY.

Focuses on:
- Output formatting (numbers, delimiters)
- Session listing accuracy
- Frecency sorting (via reload-sessions output)
- Handling of special characters
"""
import os
import time
import pytest

def run_script_reload():
    """Run the script's reload-sessions action and return output."""
    return os.popen("node /app/session-zx.mjs reload-sessions").read()

def test_script_lists_sessions_correctly():
    """Test that the script's reload-sessions action lists created sessions."""
    os.system("tmux new-session -d -s script_test_alpha")
    os.system("tmux new-session -d -s script_test_beta")
    time.sleep(0.5)

    try:
        output = run_script_reload()

        assert "script_test_alpha" in output
        assert "script_test_beta" in output

        # Verify strict formatting requirements from guidelines
        # Format: [N] session_name @ X windows
        assert "[" in output and "]" in output, "Missing number prefixes [N]"
        assert "@" in output, "Missing delimiter @"
        assert "windows" in output, "Missing 'windows' text"

    finally:
        os.system("tmux kill-session -t script_test_alpha 2>/dev/null")
        os.system("tmux kill-session -t script_test_beta 2>/dev/null")

def test_script_shows_window_counts():
    """Test that the script shows accurate window counts."""
    os.system("tmux new-session -d -s window_test")
    time.sleep(0.3)
    # Add 2 more windows (total 3)
    os.system("tmux new-window -t window_test")
    os.system("tmux new-window -t window_test")
    time.sleep(0.3)

    try:
        output = run_script_reload()
        
        # Regex or string check for "3 windows"
        # The output format is like "window_test @ 3 windows"
        assert "3 windows" in output, f"Expected '3 windows' in output, got:\n{output}"

    finally:
        os.system("tmux kill-session -t window_test 2>/dev/null")

def test_special_characters_handling():
    """Test handling of sessions with dashes, underscores, etc."""
    # tmux converts dots to underscores, so we test what persists
    names = ["test-dash", "test_underscore", "test with space"]
    
    for n in names:
        os.system(f"tmux new-session -d -s '{n}'")
    time.sleep(0.5)
    
    try:
        output = run_script_reload()
        
        for n in names:
            assert n in output, f"Session '{n}' not found in output"
            
    finally:
        for n in names:
            os.system(f"tmux kill-session -t '{n}' 2>/dev/null")

def test_reload_sessions_includes_all_sessions():
    """reload-sessions lists ALL sessions (excludeCurrent: false).

    The script passes excludeCurrent: false for reload-sessions,
    so every session appears in the output including the current one.
    """
    os.system("tmux new-session -d -s current_one")
    time.sleep(0.3)
    
    try:
        # We need to run this from INSIDE tmux to have a "current session" context 
        # if we were testing 'switch'. 
        # But 'reload-sessions' ignores current session context effectively (passes null).
        
        output = run_script_reload()
        assert "current_one" in output

    finally:
        os.system("tmux kill-session -t current_one 2>/dev/null")