"""Popup-action use case helpers."""

from collections.abc import Callable
from typing import Final, cast

from session_zx.app.context import AppContext
from session_zx.app.exit_codes import EXIT_ERROR, EXIT_SUCCESS

PopupDisplay = Callable[[str, str], object | None]

SWITCH_POPUP_TITLE: Final[str] = "SESSIONS"
WORKTREE_POPUP_TITLE: Final[str] = "WORKTREE SESSIONS"
CAPITAL_POPUP_TITLE: Final[str] = "CAPITAL SESSIONS"

SWITCH_CHILD_ACTION: Final[str] = "switch"
WORKTREE_CHILD_ACTION: Final[str] = "worktree-switch"
CAPITAL_CHILD_ACTION: Final[str] = "capital-switch"


def run_popup_switch(ctx: AppContext) -> int:
    """Run the standard popup wrapper that executes the switch action."""
    return _run_popup_action(ctx, SWITCH_POPUP_TITLE, SWITCH_CHILD_ACTION)


def run_popup_worktree_switch(ctx: AppContext) -> int:
    """Run the worktree popup wrapper."""
    return _run_popup_action(ctx, WORKTREE_POPUP_TITLE, WORKTREE_CHILD_ACTION)


def run_popup_capital_switch(ctx: AppContext) -> int:
    """Run the capital-session popup wrapper."""
    return _run_popup_action(ctx, CAPITAL_POPUP_TITLE, CAPITAL_CHILD_ACTION)


def _run_popup_action(ctx: AppContext, title: str, child_action: str) -> int:
    display_popup = _get_display_popup(ctx.deps)
    result = display_popup(title, child_action)
    return _normalize_popup_exit_code(result)


def _get_display_popup(deps: object) -> PopupDisplay:
    display_popup = getattr(deps, "display_popup", None)
    if not callable(display_popup):
        raise TypeError("Context deps must expose a callable display_popup")

    return cast(PopupDisplay, display_popup)


def _normalize_popup_exit_code(code: object | None) -> int:
    if code is None or code is True:
        return EXIT_SUCCESS

    if code is False:
        return EXIT_ERROR

    if isinstance(code, int):
        return code

    raise TypeError("display_popup must return an int, bool, or None")
