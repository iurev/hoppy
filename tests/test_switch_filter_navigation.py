"""Switch UI filtering, navigation, and delete-key workflows."""
import os
import re
import time

from .helpers.workflow import clear_query, run_popup_switch


def test_switch_typing_filters_fzf_list(tmux, create_sessions):
    create_sessions("alpha", "beta", "gamma")

    tmux.run_command("/app/session-zx switch")
    time.sleep(1.5)

    content = tmux.get_output()
    assert "alpha" in content, f"alpha not in output:\n{content}"
    assert "beta" in content, f"beta not in output:\n{content}"
    assert "gamma" in content, f"gamma not in output:\n{content}"

    tmux.send_keys("beta")
    time.sleep(0.5)

    cleaned = tmux.strip_ansi(tmux.get_output())
    match_count_is_one = re.search(r"\b1/\d+\b", cleaned) is not None
    only_beta_visible = "alpha" not in cleaned and "gamma" not in cleaned
    assert match_count_is_one or only_beta_visible, (
        f"Expected list narrowed to beta. Output:\n{cleaned}"
    )

    tmux.press_escape()
    time.sleep(0.5)


def test_switch_arrow_down_then_enter_switches(tmux, create_sessions):
    create_sessions("arrow_pick")
    tmux.assert_current_session("test_session")

    tmux.run_command("FZF_DEFAULT_OPTS='--reverse' /app/session-zx switch")
    time.sleep(1.5)

    tmux.press_arrow_down()
    time.sleep(0.3)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("arrow_pick", timeout=3), (
        f"Arrow + Enter did not switch to arrow_pick. Current: {tmux.get_current_session()}"
    )


def test_switch_arrow_up_changes_cursor_then_switches(tmux, create_sessions):
    """Arrow Up moves the cursor back exactly one row, and Enter takes it.

    Rows are [1] test_session (current, pinned), [2] up_a, [3] up_b, [4] up_c.
    Down, Down lands on [3] up_b; Up goes back to [2] up_a.

    Breaks if: the row order changes, Arrow Up stops moving the cursor, or
    Enter switches to any other session than up_a. (Checking only that the
    screen redrew, or that we landed on *some* up_* session, could not catch
    an off-by-one cursor.)
    """
    create_sessions("up_a", "up_b", "up_c")

    tmux.run_command("FZF_DEFAULT_OPTS='--reverse' /app/session-zx switch")
    time.sleep(1.5)

    tmux.press_arrow_down()
    time.sleep(0.2)
    tmux.press_arrow_down()
    time.sleep(0.4)

    before_up = tmux.get_selected_row()
    assert before_up is not None and before_up.startswith("[3] up_b @"), (
        f"Two arrows down should select '[3] up_b', got '{before_up}'"
    )

    tmux.press_arrow_up()
    time.sleep(0.4)

    after_up = tmux.get_selected_row()
    assert after_up is not None and after_up.startswith("[2] up_a @"), (
        f"Arrow up should select '[2] up_a', got '{after_up}'"
    )

    tmux.press_enter()

    assert tmux.wait_for_session_switch("up_a", timeout=4), (
        f"Enter should switch to up_a. Current: {tmux.get_current_session()}"
    )


def test_switch_clear_filter_with_backspaces(tmux, create_sessions):
    create_sessions("alpha", "beta")

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
    assert "alpha" in cleared and "beta" in cleared, (
        f"Expected list to return after clearing filter. Output:\n{cleared}"
    )
    assert re.search(r"\b0/\d+\b", cleared) is None, (
        f"Filter still shows zero matches after clearing query. Output:\n{cleared}"
    )

    tmux.send_keys("alpha")
    time.sleep(0.4)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("alpha", timeout=3), (
        f"Expected switch to alpha after clearing filter. Current: {tmux.get_current_session()}"
    )


def test_switch_filter_then_arrow_selects_second_match(tmux, create_sessions):
    create_sessions("proj_alpha", "proj_beta", "other")

    tmux.run_command("FZF_DEFAULT_OPTS='--reverse' /app/session-zx switch")
    time.sleep(1.5)
    tmux.send_keys("proj_")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    first_pick = tmux.get_current_session()
    assert first_pick in {"proj_alpha", "proj_beta"}, (
        f"Unexpected first filtered pick: {first_pick}"
    )

    os.system("tmux switch-client -t test_session")
    time.sleep(0.5)

    tmux.run_command("FZF_DEFAULT_OPTS='--reverse' /app/session-zx switch")
    time.sleep(1.5)
    tmux.send_keys("proj_")
    time.sleep(0.5)
    tmux.press_arrow_down()
    time.sleep(0.3)
    tmux.press_enter()
    time.sleep(1.0)

    second_pick = tmux.get_current_session()
    assert second_pick in {"proj_alpha", "proj_beta"}, (
        f"Unexpected second filtered pick: {second_pick}"
    )
    assert second_pick != first_pick, (
        f"Arrow down did not change selection. Both picks: {second_pick}"
    )


def test_popup_switch_delete_key_kills_session(tmux, create_sessions):
    create_sessions("victim")
    tmux.assert_session_exists("victim")

    run_popup_switch(tmux)
    tmux.send_keys("victim")
    time.sleep(0.5)
    tmux.press_delete()
    time.sleep(1.5)
    tmux.press_escape()
    time.sleep(0.5)

    assert tmux.wait_for_session_gone("victim", timeout=3), (
        f"victim still exists. Sessions: {tmux.get_all_sessions()}"
    )


def test_popup_switch_delete_then_switch_survivor_without_reopen(tmux, create_sessions):
    create_sessions("victim", "survivor")

    run_popup_switch(tmux)
    tmux.send_keys("victim")
    time.sleep(0.4)
    tmux.press_delete()
    time.sleep(1.5)

    clear_query(tmux, len("victim"))
    time.sleep(0.3)
    tmux.send_keys("survivor")
    time.sleep(0.4)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_gone("victim", timeout=3), (
        f"victim still exists after delete flow. Sessions: {tmux.get_all_sessions()}"
    )
    assert tmux.wait_for_session_switch("survivor", timeout=3), (
        f"Did not switch to survivor after delete+reload flow. Current: {tmux.get_current_session()}"
    )
