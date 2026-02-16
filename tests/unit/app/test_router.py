import pytest

from session_zx.app.context import AppContext
from session_zx.app.exit_codes import EXIT_ERROR, EXIT_SUCCESS
from session_zx.app.router import dispatch_action
import session_zx.app.router as router


class DepsWithHandlers:
    def __init__(self, action_handlers: object) -> None:
        self.action_handlers = action_handlers


class DepsWithoutHandlers:
    pass


def _context_with_deps(deps: object) -> AppContext:
    return AppContext(action=None, argv=(), env={}, deps=deps)


def test_dispatch_action_skips_validation_for_pre_validation_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        router,
        "validate_action",
        lambda action: (_ for _ in ()).throw(AssertionError(action)),
    )
    context = _context_with_deps(
        DepsWithHandlers({"kill-single-from-line": lambda ctx: 7})
    )

    result = dispatch_action("kill-single-from-line", context)

    assert result == 7


def test_dispatch_action_validates_non_helper_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(router, "validate_action", lambda action: calls.append(action))
    context = _context_with_deps(DepsWithHandlers({"switch": lambda ctx: 42}))

    result = dispatch_action("switch", context)

    assert calls == ["switch"]
    assert result == 42


def test_dispatch_action_propagates_validation_errors_before_handler_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def handler(_: AppContext) -> int:
        nonlocal called
        called = True
        return 0

    def raise_invalid(action: str) -> None:
        raise ValueError(f"invalid {action}")

    monkeypatch.setattr(router, "validate_action", raise_invalid)
    context = _context_with_deps(DepsWithHandlers({"switch": handler}))

    with pytest.raises(ValueError, match="invalid switch"):
        dispatch_action("switch", context)

    assert called is False


def test_dispatch_action_requires_handler_mapping_on_deps() -> None:
    context = _context_with_deps(DepsWithoutHandlers())

    with pytest.raises(
        TypeError, match="Context deps must expose an action_handlers mapping"
    ):
        dispatch_action("switch", context)


def test_dispatch_action_requires_registered_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(router, "validate_action", lambda action: None)
    context = _context_with_deps(DepsWithHandlers({}))

    with pytest.raises(ValueError, match="No handler registered for action: switch"):
        dispatch_action("switch", context)


def test_dispatch_action_requires_callable_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(router, "validate_action", lambda action: None)
    context = _context_with_deps(DepsWithHandlers({"switch": "not-callable"}))

    with pytest.raises(TypeError, match="Handler for action switch must be callable"):
        dispatch_action("switch", context)


def test_dispatch_action_normalizes_none_handler_result_to_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(router, "validate_action", lambda action: None)
    context = _context_with_deps(DepsWithHandlers({"switch": lambda ctx: None}))

    result = dispatch_action("switch", context)

    assert result == EXIT_SUCCESS


def test_dispatch_action_normalizes_out_of_range_handler_result_to_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(router, "validate_action", lambda action: None)
    context = _context_with_deps(DepsWithHandlers({"switch": lambda ctx: -1}))

    result = dispatch_action("switch", context)

    assert result == EXIT_ERROR
