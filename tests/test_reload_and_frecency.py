"""reload-sessions run INSIDE tmux, and frecency changing the list order.

Every other reload-sessions test runs from outside tmux, so the Q7 FIX (pin the
current session, append '[cancel]') is never seen there. And conftest wipes the
frecency store before every test, so nothing else ever runs at a score above 0.
"""
import os
import shlex
import time

from .helpers.workflow import (
    read_frecency,
    row_session_names,
    run_reload_in_pane,
    wait_for_frecency_session,
)

# The fixture session, spelled once.
CURRENT = "Destruction of the Universe"


def test_reload_sessions_inside_tmux_pins_current_and_appends_cancel(tmux, create_sessions):
    """Q7 FIX (SPEC §3.3): run inside a session, reload-sessions pins it as [1]
    and ends with a '[cancel]' row, so its rows match the initial switch list.

    Breaks if: the current session stops being pinned (the .mjs passed a null
    current session here), if the '[cancel]' row is dropped, if the numbering
    goes away, or if a session is missing from the output.
    """
    create_sessions("Ada Lovelace", "Grace Hopper")

    rows = run_reload_in_pane(tmux)

    assert rows[0].startswith(f"[1] {CURRENT} @"), (
        f"The current session must be pinned as row [1]. Rows: {rows}"
    )
    assert rows[-1] == "[cancel]", (
        f"reload-sessions must end with a '[cancel]' row. Rows: {rows}"
    )
    assert row_session_names(rows) == [CURRENT, "Ada Lovelace", "Grace Hopper"], (
        f"Unexpected rows: {rows}"
    )


def test_frecency_moves_the_picked_session_up_the_list(tmux, create_sessions):
    """A switch records a pick, and the picked session then sorts higher.

    Sessions sort by name while every score is 0, so 'Alpha Centauri' starts
    above 'Zeta Reticuli'. After we switch to 'Zeta Reticuli' its score is 100
    (SPEC §5.2), so it must move above 'Alpha Centauri'. The current session
    stays pinned at [1].

    Breaks if: `switch` stops writing .session-frecency, the score buckets stop
    scoring a fresh pick above 0, or the list stops sorting by score.
    """
    create_sessions("Alpha Centauri", "Zeta Reticuli")

    before = run_reload_in_pane(tmux, out_path="/tmp/zx_reload_before.txt")
    assert row_session_names(before) == [CURRENT, "Alpha Centauri", "Zeta Reticuli"], (
        f"Unexpected starting order: {before}"
    )
    assert read_frecency() == {}, "the frecency store must start empty"

    # Pick 'Zeta Reticuli' with the real switch UI: only a successful switch
    # records. A capital Z makes fzf case-sensitive, and no other row holds one.
    tmux.run_command("/app/session-zx switch")
    time.sleep(1.5)
    tmux.send_keys("Zeta")
    time.sleep(0.5)
    tmux.press_enter()

    assert tmux.wait_for_session_switch("Zeta Reticuli", timeout=4), (
        f"Did not switch to 'Zeta Reticuli'. Current: {tmux.get_current_session()}"
    )
    assert wait_for_frecency_session("Zeta Reticuli"), (
        f"No frecency record was written. Frecency: {read_frecency()}"
    )

    # Go back with raw tmux: that path records nothing, so only Zeta scores.
    os.system(f"tmux switch-client -t {shlex.quote(CURRENT)}")
    time.sleep(0.8)
    assert tmux.wait_for_session_switch(CURRENT, timeout=4)

    after = run_reload_in_pane(tmux, out_path="/tmp/zx_reload_after.txt")
    assert row_session_names(after) == [CURRENT, "Zeta Reticuli", "Alpha Centauri"], (
        f"'Zeta Reticuli' did not move up the list. Rows: {after}"
    )
