import pytest

from session_zx.app.composition import AppDependencies, build_app_dependencies
from session_zx.app.context import AppContext


def _ok_handler(_: AppContext) -> int:
    return 0


def test_build_app_dependencies_returns_empty_mapping_for_none_input() -> None:
    deps = build_app_dependencies()

    assert isinstance(deps, AppDependencies)
    assert deps.action_handlers == {}


def test_build_app_dependencies_accepts_empty_mapping() -> None:
    deps = build_app_dependencies({})

    assert deps.action_handlers == {}


def test_build_app_dependencies_requires_mapping() -> None:
    with pytest.raises(TypeError, match="action_handlers must be a mapping"):
        build_app_dependencies(["switch"])  # type: ignore[arg-type]


def test_build_app_dependencies_requires_callable_handlers() -> None:
    with pytest.raises(TypeError, match="Handler for action 3 must be callable"):
        build_app_dependencies({3: "not-callable"})


def test_build_app_dependencies_normalizes_action_keys_and_copies_mapping() -> None:
    handlers: dict[object, object] = {9: _ok_handler}

    deps = build_app_dependencies(handlers)
    handlers["switch"] = _ok_handler

    assert set(deps.action_handlers) == {"9"}
    assert deps.action_handlers["9"] is _ok_handler
