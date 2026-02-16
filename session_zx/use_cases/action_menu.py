"""Action-menu use case helpers."""

from collections.abc import Callable, Sequence
from typing import Final, cast

from session_zx.app.context import AppContext
from session_zx.domain.parsing import parse_lines

ActionMenuSelector = Callable[[Sequence[str], str, bool], object | None]

ACTION_MENU_ITEMS: Final[tuple[str, ...]] = (
    "switch",
    "new",
    "rename",
    "detach",
    "kill",
    "[cancel]",
)
ACTION_MENU_HEADER: Final[str] = "Select an action."


def run_action_menu(ctx: AppContext) -> str:
    """Return the selected top-level action from the interactive menu."""
    selector = _get_action_menu_selector(ctx.deps)
    selection = selector(ACTION_MENU_ITEMS, ACTION_MENU_HEADER, False)
    return _normalize_selection(selection)


def _get_action_menu_selector(deps: object) -> ActionMenuSelector:
    selector = getattr(deps, "action_menu_selector", None)
    if not callable(selector):
        raise TypeError("Context deps must expose a callable action_menu_selector")

    return cast(ActionMenuSelector, selector)


def _normalize_selection(selection: object | None) -> str:
    if selection is None:
        return ""

    lines = parse_lines(str(selection))
    return lines[0] if lines else ""
