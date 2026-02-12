"""Pytest fixtures and configuration for integration tests."""
import pytest
import os
import shutil
import time
from .helpers.tmux_session import TmuxSession


@pytest.fixture
def tmux():
    """Create a tmux session for testing."""
    session = TmuxSession(session_name="test_session")
    session.launch()

    yield session

    # Cleanup
    session.close()


@pytest.fixture(autouse=True)
def clean_frecency():
    """Clean frecency data before each test."""
    frecency_dir = "/app/.session-frecency"
    if os.path.exists(frecency_dir):
        shutil.rmtree(frecency_dir)

    yield

    # Cleanup after test
    if os.path.exists(frecency_dir):
        shutil.rmtree(frecency_dir)


@pytest.fixture
def create_sessions():
    """Create multiple tmux sessions. Stamp each with an echo for identification."""
    def _create(*names):
        for name in names:
            os.system(f"tmux new-session -d -s '{name}'")
            os.system(f"tmux send-keys -t '{name}' 'echo IN_SESSION_{name}' Enter")
        time.sleep(0.3 * len(names))
        return list(names)
    yield _create


@pytest.fixture
def test_sessions():
    """Helper to create test tmux sessions."""
    created_sessions = []

    def create_session(name):
        """Create a tmux session."""
        os.system(f"tmux new-session -d -s {name}")
        created_sessions.append(name)
        time.sleep(0.2)
        return name

    yield create_session

    # Cleanup all created sessions
    for session_name in created_sessions:
        os.system(f"tmux kill-session -t {session_name} 2>/dev/null")


@pytest.fixture(autouse=True)
def cleanup_all_sessions():
    """Cleanup all tmux sessions before and after each test."""
    os.system("tmux kill-server 2>/dev/null")
    time.sleep(0.5)

    yield

    os.system("tmux kill-server 2>/dev/null")
