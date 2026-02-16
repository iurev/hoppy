from collections.abc import Sequence
import pytest

from session_zx.app.context import AppContext
from session_zx.use_cases.action_menu import (
    ACTION_MENU_HEADER,
    ACTION_MENU_ITEMS,
    run_action_menu,
)


class DepsWithoutSelector:
    pass


class DepsWithSelector:
    def __init__(self, selector: object) -> None:
        self.action_menu_selector = selector


def _context_with_deps(deps: object) -> AppContext:
    return AppContext(action=None, argv=(), env={}, deps=deps)


def test_run_action_menu_passes_parity_items_header_and_preview_flag() -> None:
    captured: dict[str, object] = {}

    def selector(items: Sequence[str], header: str, include_preview: bool) -> str:
        captured["items"] = list(items)
        captured["header"] = header
        captured["include_preview"] = include_preview
        return "switch"

    context = _context_with_deps(DepsWithSelector(selector))

    result = run_action_menu(context)

    assert result == "switch"
    assert captured == {
        "items": list(ACTION_MENU_ITEMS),
        "header": ACTION_MENU_HEADER,
        "include_preview": False,
    }


def test_run_action_menu_returns_first_non_empty_line_from_selection() -> None:
    context = _context_with_deps(DepsWithSelector(lambda _i, _h, _p: "detach\nkill\n"))

    result = run_action_menu(context)

    assert result == "detach"


def test_run_action_menu_returns_empty_string_for_none_selection() -> None:
    context = _context_with_deps(DepsWithSelector(lambda _i, _h, _p: None))

    result = run_action_menu(context)

    assert result == ""


def test_run_action_menu_returns_empty_string_for_blank_selection_text() -> None:
    context = _context_with_deps(DepsWithSelector(lambda _i, _h, _p: " \n\t\n"))

    result = run_action_menu(context)

    assert result == ""


def test_run_action_menu_coerces_non_string_selection_to_string() -> None:
    context = _context_with_deps(DepsWithSelector(lambda _i, _h, _p: 7))

    result = run_action_menu(context)

    assert result == "7"


def test_run_action_menu_requires_selector_on_context_deps() -> None:
    context = _context_with_deps(DepsWithoutSelector())

    with pytest.raises(
        TypeError, match="Context deps must expose a callable action_menu_selector"
    ):
        run_action_menu(context)


def test_run_action_menu_requires_callable_selector() -> None:
    context = _context_with_deps(DepsWithSelector("not-callable"))

    with pytest.raises(
        TypeError, match="Context deps must expose a callable action_menu_selector"
    ):
        run_action_menu(context)
