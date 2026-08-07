"""Popup-switch workflow tests (primary user path)."""
import time

from .helpers.workflow import (
    configure_popup_env,
    read_frecency,
    run_popup_switch,
    type_query_and_accept,
    wait_for_frecency_session,
)

DEBOUNCE_MS = 900
DEBOUNCE_WAIT = 1.2


def test_popup_switch_by_typing_full_name(tmux, create_sessions):
    create_sessions("target_sess")
    tmux.assert_current_session("test_session")

    run_popup_switch(tmux)
    type_query_and_accept(tmux, "target_sess")

    assert tmux.wait_for_session_switch("target_sess", timeout=3), (
        f"Did not switch to target_sess. Current: {tmux.get_current_session()}"
    )


def test_popup_switch_by_partial_name(tmux, create_sessions):
    create_sessions("alpha_session")

    run_popup_switch(tmux)
    type_query_and_accept(tmux, "alpha")

    assert tmux.wait_for_session_switch("alpha_session", timeout=3), (
        f"Did not switch by partial name. Current: {tmux.get_current_session()}"
    )


def test_popup_switch_escape_cancels(tmux, create_sessions):
    """Escape closes the popup and changes nothing.

    Breaks if: the popup never opens (a crash would also "keep the current
    session"), if Escape stops closing the selector, if a switch happens
    anyway, or if a cancel stops exiting 0.
    """
    create_sessions("other_one")
    tmux.assert_current_session("test_session")

    run_popup_switch(tmux)
    assert tmux.wait_for_fzf_process(), "popup selector did not open"

    tmux.send_keys("other_one")
    time.sleep(0.5)
    tmux.press_escape()

    assert tmux.wait_for_fzf_gone(), "selector still open after Escape"
    tmux.assert_current_session("test_session")
    assert tmux.last_exit_code() == 0, "cancelling the popup must exit 0"
    assert read_frecency() == {}, "a cancel must not record frecency"


def test_popup_switch_ctrl_n_then_enter_confirms_target(tmux, create_sessions):
    create_sessions("arrow_target")
    tmux.assert_current_session("test_session")

    configure_popup_env(reverse=True)

    run_popup_switch(tmux)
    tmux.press_ctrl_n()
    time.sleep(1.0)

    tmux.assert_current_session("arrow_target")

    tmux.press_enter()
    time.sleep(1.0)
    assert tmux.wait_for_session_switch("arrow_target", timeout=3), (
        f"Should stay on arrow_target after Enter. Current: {tmux.get_current_session()}"
    )


def test_popup_switch_ctrl_n_preview_moves_client(tmux, create_sessions):
    create_sessions("preview_a", "preview_b")
    configure_popup_env(debounce_ms=DEBOUNCE_MS, reverse=True)

    run_popup_switch(tmux)
    tmux.press_ctrl_n()
    time.sleep(DEBOUNCE_WAIT)

    after = tmux.get_current_session()
    assert after != "test_session", f"Expected preview to move client, still in {after}"

    tmux.press_escape()
    time.sleep(0.5)


def test_popup_switch_ctrl_p_preview_returns_to_current(tmux, create_sessions):
    create_sessions("preview_p_target")
    configure_popup_env(debounce_ms=DEBOUNCE_MS, reverse=True)

    run_popup_switch(tmux)
    tmux.press_ctrl_n()
    time.sleep(DEBOUNCE_WAIT)
    tmux.assert_current_session("preview_p_target")

    tmux.press_ctrl_p()
    time.sleep(DEBOUNCE_WAIT)
    tmux.assert_current_session("test_session")

    tmux.press_escape()
    time.sleep(0.5)


def test_popup_switch_ctrl_n_then_ctrl_p_last_target_wins(tmux, create_sessions):
    """Two fast preview keys: only the LAST one may fire (SPEC §7.3).

    Breaks if: the popup never opens, or the debounce stops dropping the older
    token, so the Ctrl+N target switches in after Ctrl+P moved back.
    """
    create_sessions("bounce_target")
    configure_popup_env(debounce_ms=DEBOUNCE_MS, reverse=True)

    run_popup_switch(tmux)
    assert tmux.wait_for_fzf_process(), "popup selector did not open"

    tmux.press_ctrl_n()
    time.sleep(0.1)
    tmux.press_ctrl_p()
    time.sleep(DEBOUNCE_WAIT)

    tmux.assert_current_session("test_session")
    tmux.press_escape()
    time.sleep(0.5)


def test_popup_switch_ctrl_n_then_escape_keeps_preview_target(tmux, create_sessions):
    """Closing the popup does not undo the preview switch.

    Breaks if: the popup never opens, if Ctrl+N stops moving the client (there
    would be no preview target to keep), or if Escape moves the client back.
    """
    create_sessions("preview_target")
    configure_popup_env(debounce_ms=DEBOUNCE_MS, reverse=True)

    run_popup_switch(tmux)
    assert tmux.wait_for_fzf_process(), "popup selector did not open"

    tmux.press_ctrl_n()
    time.sleep(DEBOUNCE_WAIT)
    preview_target = tmux.get_current_session()
    assert preview_target == "preview_target", (
        f"Ctrl+N should preview 'preview_target', client is on '{preview_target}'"
    )

    tmux.press_escape()
    time.sleep(0.5)

    after = tmux.get_current_session()
    assert after == preview_target, (
        f"Expected popup close to keep preview target '{preview_target}', got '{after}'"
    )


def test_popup_switch_backspace_correction(tmux, create_sessions):
    create_sessions("banana")

    run_popup_switch(tmux)
    tmux.send_keys("banxx")
    time.sleep(0.3)
    tmux.clear_query_backspaces(2, delay=0.1)
    tmux.send_keys("ana")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("banana", timeout=3), (
        f"Did not switch to banana. Current: {tmux.get_current_session()}"
    )


def test_popup_switch_no_match_escape_keeps_current(tmux, create_sessions):
    """A query that matches nothing, then Escape: nothing happens.

    Breaks if: the popup never opens, if the selector stays open after Escape,
    if the client moves anyway, or if the exit code is not 0.
    """
    create_sessions("some_sess")
    tmux.assert_current_session("test_session")

    run_popup_switch(tmux)
    assert tmux.wait_for_fzf_process(), "popup selector did not open"

    tmux.send_keys("zzzzxxx_no_match")
    time.sleep(0.5)
    tmux.press_escape()

    assert tmux.wait_for_fzf_gone(), "selector still open after Escape"
    tmux.assert_current_session("test_session")
    assert tmux.last_exit_code() == 0, "cancelling the popup must exit 0"


def test_popup_switch_no_match_enter_keeps_current(tmux, create_sessions):
    """A query that matches nothing, then Enter: fzf exits 1 and we exit 0.

    fzf's "no match" exit code is normal for us (SPEC §12), so the binary must
    treat the empty selection as a cancel.

    Breaks if: the popup never opens, if the selector stays open after Enter, if
    an empty selection starts a switch, or if fzf's exit code 1 leaks out as a
    non-zero exit code of our binary.
    """
    create_sessions("some_sess")
    tmux.assert_current_session("test_session")

    run_popup_switch(tmux)
    assert tmux.wait_for_fzf_process(), "popup selector did not open"

    tmux.send_keys("zzzzxxx_no_match")
    time.sleep(0.5)
    tmux.press_enter()

    assert tmux.wait_for_fzf_gone(), "selector still open after Enter"
    tmux.assert_current_session("test_session")
    assert tmux.last_exit_code() == 0, "an empty selection must exit 0"
    assert read_frecency() == {}, "an empty selection must not record frecency"


def test_popup_switch_only_current_session_noop(tmux):
    """With one session, picking it really runs a switch to itself.

    The frecency record is the proof: it is written only after a SUCCESSFUL
    `tmux switch-client` (SPEC §5.3). A binary that did nothing would leave the
    client on test_session too, but would write no record.

    Breaks if: the popup never opens, if the only row cannot be accepted, or if
    a successful switch stops recording frecency.
    """
    tmux.assert_current_session("test_session")

    run_popup_switch(tmux)
    assert tmux.wait_for_fzf_process(), "popup selector did not open"

    type_query_and_accept(tmux, "test_session")

    assert tmux.wait_for_fzf_gone(), "selector still open after Enter"
    tmux.assert_current_session("test_session")
    assert wait_for_frecency_session("test_session"), (
        f"No frecency record for the accepted row. Frecency: {read_frecency()}"
    )


def test_popup_switch_session_name_with_spaces(tmux, create_sessions):
    create_sessions("my session")

    run_popup_switch(tmux)
    type_query_and_accept(tmux, "my session")

    assert tmux.wait_for_session_switch("my session", timeout=3), (
        f"Did not switch to 'my session'. Current: {tmux.get_current_session()}"
    )


def test_popup_switch_twice_consecutive(tmux, create_sessions):
    create_sessions("first_dest", "second_dest")

    run_popup_switch(tmux)
    type_query_and_accept(tmux, "first_dest")
    assert tmux.wait_for_session_switch("first_dest", timeout=3), (
        f"First switch failed. Current: {tmux.get_current_session()}"
    )

    time.sleep(0.5)

    run_popup_switch(tmux)
    type_query_and_accept(tmux, "second_dest")
    assert tmux.wait_for_session_switch("second_dest", timeout=3), (
        f"Second switch failed. Current: {tmux.get_current_session()}"
    )
