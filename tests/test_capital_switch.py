"""End-to-end tests for capital-switch and popup-capital-switch (SPEC §3.10).

The filter keeps a session only when its name is made of uppercase letters,
digits, underscore, hyphen and whitespace, AND holds at least one A-Z.
"""
import time

from .helpers.workflow import MSG_NO_CAPITAL_SESSIONS

# The fixture session. It holds lowercase letters, so the CAPITAL filter always
# drops it. Keep it that way or every count below moves.
CURRENT = "Destruction of the Universe"


def test_capital_switch_lists_only_capital_sessions(tmux, create_sessions):
    """Only CAPITAL-named sessions reach the list.

    Sessions: ALL YOUR BASE, THE_CAKE_IS_A_LIE, mostly_harmless and the
    fixture session. So 2 of 4 are kept.

    Breaks if: the CAPITAL filter stops filtering (mostly_harmless would show
    up), if an uppercase session is dropped, if the '<kept>/<all>' header counts
    change, or if picking a row no longer switches the client.
    """
    create_sessions("ALL YOUR BASE", "THE_CAKE_IS_A_LIE", "mostly_harmless")

    tmux.run_command("/app/hoppy capital-switch")
    assert tmux.wait_for_text("CAPITAL sessions (2/4)", timeout=8), (
        f"Wrong or missing CAPITAL header. Content:\n{tmux.get_output()}"
    )

    content = tmux.strip_ansi(tmux.get_output())
    assert "ALL YOUR BASE @" in content, f"'ALL YOUR BASE' missing. Content:\n{content}"
    assert "THE_CAKE_IS_A_LIE @" in content, (
        f"'THE_CAKE_IS_A_LIE' missing. Content:\n{content}"
    )
    assert "mostly_harmless @" not in content, (
        f"A lowercase session was listed. Content:\n{content}"
    )
    assert f"{CURRENT} @" not in content, (
        f"A lowercase session was listed. Content:\n{content}"
    )

    # Uppercase in the query makes fzf case-sensitive, and the three terms must
    # all land on one row. THE_CAKE_IS_A_LIE has no second 'L' after its 'A'.
    tmux.send_keys("ALL YOUR BASE")
    time.sleep(0.5)
    tmux.press_enter()

    assert tmux.wait_for_session_switch("ALL YOUR BASE", timeout=4), (
        f"Did not switch to 'ALL YOUR BASE'. Current: {tmux.get_current_session()}"
    )


def test_popup_capital_switch_switches_session(tmux, create_sessions):
    """popup-capital-switch opens the same filtered list inside a popup.

    Breaks if: the popup command or its inner action changes, if the popup
    never starts fzf, or if the pick stops switching the client.
    """
    create_sessions("HAL 9000", "dave_stop")

    tmux.run_command("/app/hoppy popup-capital-switch")
    assert tmux.wait_for_fzf_process(), "CAPITAL popup did not start fzf"

    tmux.send_keys("HAL 9000")
    time.sleep(0.5)
    tmux.press_enter()

    assert tmux.wait_for_session_switch("HAL 9000", timeout=4), (
        f"Popup CAPITAL switch failed. Current: {tmux.get_current_session()}"
    )


def test_capital_switch_without_capital_sessions_shows_message(tmux, create_sessions):
    """No uppercase session: tell the user and stop (SPEC §3.10 step 3).

    Breaks if: the empty-filter guard goes away (a selector with only a
    '[cancel]' row would open), the message text changes, or the CAPITAL filter
    starts accepting lowercase names.
    """
    create_sessions("dont_panic", "mostly_harmless")

    tmux.run_command("/app/hoppy capital-switch")

    assert tmux.wait_for_client_message(MSG_NO_CAPITAL_SESSIONS), (
        f"tmux never showed '{MSG_NO_CAPITAL_SESSIONS}'"
    )
    assert "CAPITAL sessions (" not in tmux.strip_ansi(tmux.get_output()), (
        f"A selector opened with no CAPITAL session. Content:\n{tmux.get_output()}"
    )
    assert tmux.last_exit_code() == 0, "this path must exit 0"
