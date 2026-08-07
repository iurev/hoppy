"""reload-sessions run INSIDE tmux, and frecency changing the list order.

Every other reload-sessions test runs from outside tmux, so the Q7 FIX (pin the
current session, append '[cancel]') is never seen there. And conftest wipes the
frecency store before every test, so nothing else ever runs at a score above 0.
"""
import os
import time

from .helpers.workflow import (
    read_frecency,
    row_session_names,
    run_reload_in_pane,
    wait_for_frecency_session,
)


def test_reload_sessions_inside_tmux_pins_current_and_appends_cancel(tmux, create_sessions):
    """Q7 FIX (SPEC §3.3): run inside a session, reload-sessions pins it as [1]
    and ends with a '[cancel]' row, so its rows match the initial switch list.

    Breaks if: the current session stops being pinned (the .mjs passed a null
    current session here), if the '[cancel]' row is dropped, if the numbering
    goes away, or if a session is missing from the output.
    """
    create_sessions("r_alpha", "r_beta")

    rows = run_reload_in_pane(tmux)

    assert rows[0].startswith("[1] test_session @"), (
        f"The current session must be pinned as row [1]. Rows: {rows}"
    )
    assert rows[-1] == "[cancel]", (
        f"reload-sessions must end with a '[cancel]' row. Rows: {rows}"
    )
    assert row_session_names(rows) == ["test_session", "r_alpha", "r_beta"], (
        f"Unexpected rows: {rows}"
    )


def test_frecency_moves_the_picked_session_up_the_list(tmux, create_sessions):
    """A switch records a pick, and the picked session then sorts higher.

    Sessions sort alphabetically while every score is 0, so frec_aaa starts
    above frec_zzz. After we switch to frec_zzz its score is 100 (SPEC §5.2),
    so it must move above frec_aaa. The current session stays pinned at [1].

    Breaks if: `switch` stops writing .session-frecency, the score buckets stop
    scoring a fresh pick above 0, or the list stops sorting by score.
    """
    create_sessions("frec_aaa", "frec_zzz")

    before = run_reload_in_pane(tmux, out_path="/tmp/zx_reload_before.txt")
    assert row_session_names(before) == ["test_session", "frec_aaa", "frec_zzz"], (
        f"Unexpected starting order: {before}"
    )
    assert read_frecency() == {}, "the frecency store must start empty"

    # Pick frec_zzz with the real switch UI: only a successful switch records.
    tmux.run_command("/app/session-zx switch")
    time.sleep(1.5)
    tmux.send_keys("frec_zzz")
    time.sleep(0.5)
    tmux.press_enter()

    assert tmux.wait_for_session_switch("frec_zzz", timeout=4), (
        f"Did not switch to frec_zzz. Current: {tmux.get_current_session()}"
    )
    assert wait_for_frecency_session("frec_zzz"), (
        f"No frecency record was written. Frecency: {read_frecency()}"
    )

    # Go back with raw tmux: that path records nothing, so only frec_zzz scores.
    os.system("tmux switch-client -t test_session")
    time.sleep(0.8)
    assert tmux.wait_for_session_switch("test_session", timeout=4)

    after = run_reload_in_pane(tmux, out_path="/tmp/zx_reload_after.txt")
    assert row_session_names(after) == ["test_session", "frec_zzz", "frec_aaa"], (
        f"frec_zzz did not move up the list. Rows: {after}"
    )
