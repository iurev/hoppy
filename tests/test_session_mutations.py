"""Session creation, rename, kill, and detach action tests."""
import time

from .helpers.workflow import clear_query, write_session_name_to_fifo


def test_new_session_creation(tmux):
    tmux.run_command("/app/session-zx new")
    time.sleep(2.0)

    write_session_name_to_fifo("fresh_session")
    time.sleep(1.5)

    tmux.assert_session_exists("fresh_session")
    assert tmux.wait_for_session_switch("fresh_session", timeout=3), (
        f"Did not switch to fresh_session. Current: {tmux.get_current_session()}"
    )


def test_rename_current_session(tmux):
    tmux.run_command("/app/session-zx rename")
    time.sleep(2.0)

    write_session_name_to_fifo("renamed_sess")
    time.sleep(0.5)

    tmux.send_keys("test_session")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    sessions = tmux.get_all_sessions()
    assert "renamed_sess" in sessions, f"renamed_sess not found. Sessions: {sessions}"
    assert "test_session" not in sessions, f"test_session still exists. Sessions: {sessions}"


def test_rename_other_session(tmux, create_sessions):
    create_sessions("old_name")

    tmux.run_command("/app/session-zx rename")
    time.sleep(2.0)

    write_session_name_to_fifo("new_name")
    time.sleep(0.5)

    tmux.send_keys("old_name")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    sessions = tmux.get_all_sessions()
    assert "new_name" in sessions, f"new_name not found. Sessions: {sessions}"
    assert "old_name" not in sessions, f"old_name still exists. Sessions: {sessions}"
    assert "test_session" in sessions, f"test_session missing. Sessions: {sessions}"


def test_kill_action_removes_session(tmux, create_sessions):
    create_sessions("kill_me", "keep_me")

    tmux.run_command("/app/session-zx kill")
    time.sleep(1.5)

    tmux.send_keys("kill_me")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_gone("kill_me", timeout=3), (
        f"kill_me still exists. Sessions: {tmux.get_all_sessions()}"
    )
    tmux.assert_session_exists("keep_me")


def test_kill_multiple_sessions_with_tab(tmux, create_sessions):
    create_sessions("kill_a", "kill_b", "keep_c")

    tmux.run_command("TMUX_FZF_OPTIONS='--multi' /app/session-zx kill")
    time.sleep(1.5)

    tmux.send_keys("kill_a")
    time.sleep(0.4)
    tmux.press_tab()
    time.sleep(0.2)

    clear_query(tmux, len("kill_a"))
    time.sleep(0.2)

    tmux.send_keys("kill_b")
    time.sleep(0.4)
    tmux.press_tab()
    time.sleep(0.2)

    tmux.press_enter()
    time.sleep(1.2)

    assert tmux.wait_for_session_gone("kill_a", timeout=3), (
        f"kill_a still exists after multi-select kill. Sessions: {tmux.get_all_sessions()}"
    )
    assert tmux.wait_for_session_gone("kill_b", timeout=3), (
        f"kill_b still exists after multi-select kill. Sessions: {tmux.get_all_sessions()}"
    )
    tmux.assert_session_exists("keep_c")


def test_detach_action_detaches_the_client(tmux):
    """`detach` must really detach a client, and must NOT kill the session.

    Breaks if: `tmux detach` is not run (the client stays attached), if the
    attached-session list stops showing the current session as a pickable row,
    or if detach starts killing the session instead.
    (Only checking that the session still exists could never fail: detaching
    never removes a session.)
    """
    tmux.assert_session_exists("test_session")
    assert "test_session" in tmux.get_attached_sessions(), (
        f"No client attached before detach. Clients: {tmux.get_attached_sessions()}"
    )

    tmux.run_command("/app/session-zx detach")
    time.sleep(1.5)

    tmux.send_keys("test_session")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_client_detached("test_session", timeout=5), (
        f"Client is still attached. Clients: {tmux.get_attached_sessions()}"
    )
    tmux.assert_session_exists("test_session")
