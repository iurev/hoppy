"""Action-menu flow tests when script is run with no explicit action."""
import time


def test_action_menu_shows_all_options(tmux):
    tmux.run_command("/app/session-zx.py")
    time.sleep(1.5)

    content = tmux.get_output()
    expected = ["switch", "new", "rename", "detach", "kill", "[cancel]"]
    for item in expected:
        assert item in content, f"'{item}' not visible in action menu. Content:\n{content}"

    tmux.press_escape()
    time.sleep(0.5)


def test_action_menu_cancel_does_nothing(tmux):
    before = tmux.get_current_session()

    tmux.run_command("/app/session-zx.py")
    time.sleep(1.0)
    tmux.send_keys("cancel")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(0.5)

    after = tmux.get_current_session()
    assert after == before, f"Session changed from {before} to {after}"


def test_action_menu_selects_switch_then_switches(tmux, create_sessions):
    create_sessions("menu_target")

    tmux.run_command("/app/session-zx.py")
    time.sleep(1.5)

    tmux.send_keys("switch")
    time.sleep(0.3)
    tmux.press_enter()
    time.sleep(1.5)

    tmux.send_keys("menu_target")
    time.sleep(0.5)
    tmux.press_enter()
    time.sleep(1.0)

    assert tmux.wait_for_session_switch("menu_target", timeout=3), (
        f"Did not switch to menu_target. Current: {tmux.get_current_session()}"
    )
