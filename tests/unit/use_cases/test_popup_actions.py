from collections.abc import Callable

import pytest

from session_zx.app.context import AppContext
from session_zx.app.exit_codes import EXIT_ERROR, EXIT_SUCCESS
from session_zx.use_cases.popup_actions import (
    CAPITAL_CHILD_ACTION,
    CAPITAL_POPUP_TITLE,
    SWITCH_CHILD_ACTION,
    SWITCH_POPUP_TITLE,
    WORKTREE_CHILD_ACTION,
    WORKTREE_POPUP_TITLE,
    run_popup_capital_switch,
    run_popup_switch,
    run_popup_worktree_switch,
)


class DepsWithoutDisplayPopup:
    pass


class DepsWithDisplayPopup:
    def __init__(self, display_popup: object) -> None:
        self.display_popup = display_popup


def _context_with_deps(deps: object) -> AppContext:
    return AppContext(action=None, argv=(), env={}, deps=deps)


@pytest.mark.parametrize(
    ("runner", "title", "child_action"),
    (
        (run_popup_switch, SWITCH_POPUP_TITLE, SWITCH_CHILD_ACTION),
        (
            run_popup_worktree_switch,
            WORKTREE_POPUP_TITLE,
            WORKTREE_CHILD_ACTION,
        ),
        (run_popup_capital_switch, CAPITAL_POPUP_TITLE, CAPITAL_CHILD_ACTION),
    ),
)
def test_popup_runners_call_display_popup_with_parity_values(
    runner: Callable[[AppContext], int],
    title: str,
    child_action: str,
) -> None:
    captured: list[tuple[str, str]] = []

    def display_popup(captured_title: str, captured_child_action: str) -> bool:
        captured.append((captured_title, captured_child_action))
        return True

    context = _context_with_deps(DepsWithDisplayPopup(display_popup))

    result = runner(context)

    assert result == EXIT_SUCCESS
    assert captured == [(title, child_action)]


def test_run_popup_switch_treats_none_as_success() -> None:
    context = _context_with_deps(
        DepsWithDisplayPopup(lambda _title, _child_action: None)
    )

    result = run_popup_switch(context)

    assert result == EXIT_SUCCESS


def test_run_popup_switch_maps_false_to_error_exit_code() -> None:
    context = _context_with_deps(
        DepsWithDisplayPopup(lambda _title, _child_action: False)
    )

    result = run_popup_switch(context)

    assert result == EXIT_ERROR


def test_run_popup_switch_passes_through_int_exit_code() -> None:
    context = _context_with_deps(
        DepsWithDisplayPopup(lambda _title, _child_action: 23)
    )

    result = run_popup_switch(context)

    assert result == 23


def test_run_popup_switch_requires_display_popup_dependency() -> None:
    context = _context_with_deps(DepsWithoutDisplayPopup())

    with pytest.raises(
        TypeError, match="Context deps must expose a callable display_popup"
    ):
        run_popup_switch(context)


def test_run_popup_switch_requires_callable_display_popup_dependency() -> None:
    context = _context_with_deps(DepsWithDisplayPopup("not-callable"))

    with pytest.raises(
        TypeError, match="Context deps must expose a callable display_popup"
    ):
        run_popup_switch(context)


def test_run_popup_switch_rejects_invalid_display_popup_return_type() -> None:
    context = _context_with_deps(
        DepsWithDisplayPopup(lambda _title, _child_action: "x")
    )

    with pytest.raises(
        TypeError, match="display_popup must return an int, bool, or None"
    ):
        run_popup_switch(context)
