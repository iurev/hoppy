"""Pytest fixtures and configuration for integration tests."""
import os
import re
import shutil
import time

import pytest

from .helpers.tmux_session import TmuxSession

# Where recordings land. Bind-mounted, so they show up on the host too.
CAST_DIR = "/app/test_output/casts"


def _cast_path(request):
    """Return the .cast path for this test, or None when recording is off.

    Recording is OFF unless RECORD_CAST is set to something other than
    "" or "0". Use `docker compose run --rm test-record`.
    """
    if os.environ.get("RECORD_CAST", "") in ("", "0"):
        return None

    # nodeid is like "tests/test_x.py::test_y[param]". Make it a safe filename.
    name = re.sub(r"[^A-Za-z0-9]+", "_", request.node.nodeid).strip("_")
    return os.path.join(CAST_DIR, f"{name}.cast")


@pytest.fixture(autouse=True)
def cleanup_all_sessions():
    """Cleanup all tmux sessions before and after each test."""
    os.system("tmux kill-server 2>/dev/null")
    time.sleep(0.5)

    yield

    os.system("tmux kill-server 2>/dev/null")


@pytest.fixture
def tmux(request):
    """Create a tmux session for testing."""
    session = TmuxSession(session_name="test_session", cast_path=_cast_path(request))
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
