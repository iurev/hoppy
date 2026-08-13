"""Session creation, rename, kill, and detach action tests."""
import time

from .helpers.workflow import clear_query, write_session_name_to_fifo

# The fixture session, spelled once.
CURRENT = "Destruction of the Universe"


def test_new_session_creation(tmux):
    tmux.run_command("/app/hoppy new")
    time.sleep(2.0)

    write_session_name_to_fifo("Hello_World_Again")
    time.sleep(1.5)

    tmux.assert_session_exists("Hello_World_Again")
    assert tmux.wait_for_session_switch("Hello_World_Again", timeout=3), (
        f"Did not switch to Hello_World_Again. Current: {tmux.get_current_session()}"
    )


def test_rename_current_session(tmux):
    tmux.run_command("/app/hoppy rename")
    time.sleep(2.0)

    write_session_name_to_fifo("Universe Restored")
    time.sleep(0.5)

    tmux.send_keys(CURRENT)
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    sessions = tmux.get_all_sessions()
    assert "Universe Restored" in sessions, (
        f"'Universe Restored' not found. Sessions: {sessions}"
    )
    assert CURRENT not in sessions, f"'{CURRENT}' still exists. Sessions: {sessions}"


def test_rename_other_session(tmux, create_sessions):
    create_sessions("Deprecated_Since_1999")

    tmux.run_command("/app/hoppy rename")
    time.sleep(2.0)

    write_session_name_to_fifo("Modern_Stack_2026")
    time.sleep(0.5)

    tmux.send_keys("Deprecated_Since_1999")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    sessions = tmux.get_all_sessions()
    assert "Modern_Stack_2026" in sessions, (
        f"'Modern_Stack_2026' not found. Sessions: {sessions}"
    )
    assert "Deprecated_Since_1999" not in sessions, (
        f"'Deprecated_Since_1999' still exists. Sessions: {sessions}"
    )
    assert CURRENT in sessions, f"'{CURRENT}' missing. Sessions: {sessions}"


def test_kill_action_removes_session(tmux, create_sessions):
    create_sessions("Keep_Calm_And_Vim_On", "kill_it_with_fire")

    tmux.run_command("/app/hoppy kill")
    time.sleep(1.5)

    tmux.send_keys("kill_it")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_gone("kill_it_with_fire", timeout=3), (
        f"kill_it_with_fire still exists. Sessions: {tmux.get_all_sessions()}"
    )
    tmux.assert_session_exists("Keep_Calm_And_Vim_On")


def test_kill_multiple_sessions_with_tab(tmux, create_sessions):
    """TAB marks two rows and Enter kills both, leaving the third alone.

    Q14: `kill` deletes in REVERSE lexicographic order, so 'Goodbye Cruel
    World' dies before 'Farewell My Segfault'. Both are gone either way, and
    neither is the attached session, so the order changes nothing here.
    """
    create_sessions("Farewell My Segfault", "Goodbye Cruel World", "Immortal Snail")

    tmux.run_command("TMUX_FZF_OPTIONS='--multi' /app/hoppy kill")
    time.sleep(1.5)

    tmux.send_keys("goodbye")
    time.sleep(0.4)
    tmux.press_tab()
    time.sleep(0.2)

    clear_query(tmux, len("goodbye"))
    time.sleep(0.2)

    tmux.send_keys("farewell")
    time.sleep(0.4)
    tmux.press_tab()
    time.sleep(0.2)

    tmux.press_enter()
    time.sleep(1.2)

    assert tmux.wait_for_session_gone("Goodbye Cruel World", timeout=3), (
        f"'Goodbye Cruel World' still exists after multi-select kill. "
        f"Sessions: {tmux.get_all_sessions()}"
    )
    assert tmux.wait_for_session_gone("Farewell My Segfault", timeout=3), (
        f"'Farewell My Segfault' still exists after multi-select kill. "
        f"Sessions: {tmux.get_all_sessions()}"
    )
    tmux.assert_session_exists("Immortal Snail")


def test_detach_action_detaches_the_client(tmux):
    """`detach` must really detach a client, and must NOT kill the session.

    Breaks if: `tmux detach` is not run (the client stays attached), if the
    attached-session list stops showing the current session as a pickable row,
    or if detach starts killing the session instead.
    (Only checking that the session still exists could never fail: detaching
    never removes a session.)
    """
    tmux.assert_session_exists(CURRENT)
    assert CURRENT in tmux.get_attached_sessions(), (
        f"No client attached before detach. Clients: {tmux.get_attached_sessions()}"
    )

    tmux.run_command("/app/hoppy detach")
    time.sleep(1.5)

    tmux.send_keys(CURRENT)
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_client_detached(CURRENT, timeout=5), (
        f"Client is still attached. Clients: {tmux.get_attached_sessions()}"
    )
    tmux.assert_session_exists(CURRENT)
