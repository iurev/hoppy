"""Switch UI filtering, navigation, and delete-key workflows."""
import os
import re
import shlex
import time

from .helpers.workflow import clear_query, run_popup_switch

# The fixture session, spelled once. Every test below lives next to it.
CURRENT = "Destruction of the Universe"


def test_switch_typing_filters_fzf_list(tmux, create_sessions):
    create_sessions("Blue Screen of Joy", "Gopher Rodeo", "sixty-seven")

    tmux.run_command("/app/session-zx switch")
    time.sleep(1.5)

    content = tmux.get_output()
    assert "Blue Screen of Joy" in content, f"Blue Screen of Joy not in output:\n{content}"
    assert "Gopher Rodeo" in content, f"Gopher Rodeo not in output:\n{content}"
    assert "sixty-seven" in content, f"sixty-seven not in output:\n{content}"

    # "seven" is a subsequence of no other row on screen.
    tmux.send_keys("seven")
    time.sleep(0.5)

    cleaned = tmux.strip_ansi(tmux.get_output())
    match_count_is_one = re.search(r"\b1/\d+\b", cleaned) is not None
    only_seven_visible = (
        "Blue Screen of Joy" not in cleaned and "Gopher Rodeo" not in cleaned
    )
    assert match_count_is_one or only_seven_visible, (
        f"Expected list narrowed to sixty-seven. Output:\n{cleaned}"
    )

    tmux.press_escape()
    time.sleep(0.5)


def test_switch_arrow_down_then_enter_switches(tmux, create_sessions):
    create_sessions("Rubber Duck HQ")
    tmux.assert_current_session(CURRENT)

    tmux.run_command("FZF_DEFAULT_OPTS='--reverse' /app/session-zx switch")
    time.sleep(1.5)

    tmux.press_arrow_down()
    time.sleep(0.3)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("Rubber Duck HQ", timeout=3), (
        f"Arrow + Enter did not switch to 'Rubber Duck HQ'. "
        f"Current: {tmux.get_current_session()}"
    )


def test_switch_arrow_up_changes_cursor_then_switches(tmux, create_sessions):
    """Arrow Up moves the cursor back exactly one row, and Enter takes it.

    tmux lists sessions in name order, so the rows are
    [1] Destruction of the Universe (current, pinned), [2] emacs_is_an_os,
    [3] nano_gang, [4] vim_or_death.
    Down, Down lands on [3] nano_gang; Up goes back to [2] emacs_is_an_os.

    Breaks if: the row order changes, Arrow Up stops moving the cursor, or
    Enter switches to any other session than emacs_is_an_os. (Checking only
    that the screen redrew, or that we landed on *some* editor session, could
    not catch an off-by-one cursor.)
    """
    create_sessions("emacs_is_an_os", "nano_gang", "vim_or_death")

    tmux.run_command("FZF_DEFAULT_OPTS='--reverse' /app/session-zx switch")
    time.sleep(1.5)

    tmux.press_arrow_down()
    time.sleep(0.2)
    tmux.press_arrow_down()
    time.sleep(0.4)

    before_up = tmux.get_selected_row()
    assert before_up is not None and before_up.startswith("[3] nano_gang @"), (
        f"Two arrows down should select '[3] nano_gang', got '{before_up}'"
    )

    tmux.press_arrow_up()
    time.sleep(0.4)

    after_up = tmux.get_selected_row()
    assert after_up is not None and after_up.startswith("[2] emacs_is_an_os @"), (
        f"Arrow up should select '[2] emacs_is_an_os', got '{after_up}'"
    )

    tmux.press_enter()

    assert tmux.wait_for_session_switch("emacs_is_an_os", timeout=4), (
        f"Enter should switch to emacs_is_an_os. Current: {tmux.get_current_session()}"
    )


def test_switch_clear_filter_with_backspaces(tmux, create_sessions):
    create_sessions("Stack Overflow Copypasta", "printf_debugging")

    tmux.run_command("/app/session-zx switch")
    time.sleep(1.5)

    tmux.send_keys("xxxxx")
    time.sleep(0.5)

    no_match = tmux.strip_ansi(tmux.get_output())
    assert re.search(r"\b0/\d+\b", no_match) is not None, (
        f"Expected 0 matches after junk filter. Output:\n{no_match}"
    )

    clear_query(tmux, 5)
    time.sleep(0.5)

    cleared = tmux.strip_ansi(tmux.get_output())
    assert "Stack Overflow Copypasta" in cleared and "printf_debugging" in cleared, (
        f"Expected list to return after clearing filter. Output:\n{cleared}"
    )
    assert re.search(r"\b0/\d+\b", cleared) is None, (
        f"Filter still shows zero matches after clearing query. Output:\n{cleared}"
    )

    tmux.send_keys("printf")
    time.sleep(0.4)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("printf_debugging", timeout=3), (
        f"Expected switch to printf_debugging after clearing filter. "
        f"Current: {tmux.get_current_session()}"
    )


def test_switch_filter_then_arrow_selects_second_match(tmux, create_sessions):
    create_sessions("Doom_On_A_Fridge", "Doom_On_A_Toaster", "Excel Turing Machine")

    tmux.run_command("FZF_DEFAULT_OPTS='--reverse' /app/session-zx switch")
    time.sleep(1.5)
    tmux.send_keys("doom_")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    first_pick = tmux.get_current_session()
    assert first_pick in {"Doom_On_A_Fridge", "Doom_On_A_Toaster"}, (
        f"Unexpected first filtered pick: {first_pick}"
    )

    os.system(f"tmux switch-client -t {shlex.quote(CURRENT)}")
    time.sleep(0.5)

    tmux.run_command("FZF_DEFAULT_OPTS='--reverse' /app/session-zx switch")
    time.sleep(1.5)
    tmux.send_keys("doom_")
    time.sleep(0.5)
    tmux.press_arrow_down()
    time.sleep(0.3)
    tmux.press_enter()
    time.sleep(1.0)

    second_pick = tmux.get_current_session()
    assert second_pick in {"Doom_On_A_Fridge", "Doom_On_A_Toaster"}, (
        f"Unexpected second filtered pick: {second_pick}"
    )
    assert second_pick != first_pick, (
        f"Arrow down did not change selection. Both picks: {second_pick}"
    )


def test_popup_switch_delete_key_kills_session(tmux, create_sessions):
    create_sessions("doomed_penguin")
    tmux.assert_session_exists("doomed_penguin")

    run_popup_switch(tmux)
    tmux.send_keys("doomed")
    time.sleep(0.5)
    tmux.press_delete()
    time.sleep(1.5)
    tmux.press_escape()
    time.sleep(0.5)

    assert tmux.wait_for_session_gone("doomed_penguin", timeout=3), (
        f"doomed_penguin still exists. Sessions: {tmux.get_all_sessions()}"
    )


def test_popup_switch_delete_then_switch_survivor_without_reopen(tmux, create_sessions):
    create_sessions("Sole Survivor", "crash_dummy")

    run_popup_switch(tmux)
    tmux.send_keys("crash")
    time.sleep(0.4)
    tmux.press_delete()
    time.sleep(1.5)

    clear_query(tmux, len("crash"))
    time.sleep(0.3)
    tmux.send_keys("Survivor")
    time.sleep(0.4)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_gone("crash_dummy", timeout=3), (
        f"crash_dummy still exists after delete flow. Sessions: {tmux.get_all_sessions()}"
    )
    assert tmux.wait_for_session_switch("Sole Survivor", timeout=3), (
        f"Did not switch to 'Sole Survivor' after delete+reload flow. "
        f"Current: {tmux.get_current_session()}"
    )
