"""Action-menu flow tests when script is run with no explicit action."""
import time


def test_action_menu_shows_all_options(tmux):
    tmux.run_command("/app/session-zx")
    time.sleep(1.5)

    content = tmux.get_output()
    expected = ["switch", "new", "rename", "detach", "kill", "[cancel]"]
    for item in expected:
        assert item in content, f"'{item}' not visible in action menu. Content:\n{content}"

    tmux.press_escape()
    time.sleep(0.5)


def test_action_menu_cancel_does_nothing(tmux):
    """Picking '[cancel]' in the action menu ends the run at once.

    Breaks if: the action menu does not render, if '[cancel]' stops ending the
    run (the session selector would open next), if the client moves, or if the
    exit code is not 0.
    """
    before = tmux.get_current_session()

    tmux.run_command("/app/session-zx")
    assert tmux.wait_for_text("Select an action.", timeout=6), (
        f"Action menu did not render. Content:\n{tmux.get_output()}"
    )

    tmux.send_keys("cancel")
    time.sleep(0.5)
    tmux.press_enter()

    assert tmux.wait_for_fzf_gone(), "fzf still running after picking [cancel]"

    content = tmux.get_output()
    assert "Select target session" not in content, (
        f"[cancel] opened the switch list instead of exiting. Content:\n{content}"
    )

    after = tmux.get_current_session()
    assert after == before, f"Session changed from {before} to {after}"
    assert tmux.last_exit_code() == 0, "[cancel] must exit 0"


def test_action_menu_selects_switch_then_switches(tmux, create_sessions):
    create_sessions("Up Up Down Down")

    tmux.run_command("/app/session-zx")
    time.sleep(1.5)

    tmux.send_keys("switch")
    time.sleep(0.3)
    tmux.press_enter()
    time.sleep(1.5)

    # A capital D makes fzf case-sensitive; only 'Up Up Down Down' holds "Down".
    tmux.send_keys("Down")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("Up Up Down Down", timeout=3), (
        f"Did not switch to 'Up Up Down Down'. Current: {tmux.get_current_session()}"
    )
