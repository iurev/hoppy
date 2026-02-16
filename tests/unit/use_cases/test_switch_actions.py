from types import SimpleNamespace

import pytest

from session_zx.app.context import AppContext
from session_zx.app.exit_codes import EXIT_ERROR, EXIT_SUCCESS
from session_zx.use_cases.switch_actions import (
    CANCEL_ITEM,
    SWITCH_HEADER,
    _build_switch_bindings,
    _build_switch_items,
    run_switch,
)


def _context_with_deps(deps: object) -> AppContext:
    return AppContext(action="switch", argv=(), env={}, deps=deps)


def test_run_switch_calls_selector_with_parity_values_and_switches_target() -> None:
    captured: dict[str, object] = {}
    switched_targets: list[str] = []
    recorded_targets: list[str] = []

    def selector(
        items: list[str],
        header: str,
        include_preview: bool,
        extra_bindings: str,
    ) -> str:
        captured["items"] = items
        captured["header"] = header
        captured["include_preview"] = include_preview
        captured["extra_bindings"] = extra_bindings
        return "[2] beta @ 1 windows"

    deps = SimpleNamespace(
        list_session_rows=lambda: ["beta @ 1 windows", "alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        switch_session_selector=selector,
        switch_client=lambda target: switched_targets.append(target) or True,
        record_frecency=lambda target: recorded_targets.append(target),
        switch_script_path="/app/session-zx.mjs",
    )

    result = run_switch(_context_with_deps(deps))

    assert result == EXIT_SUCCESS
    assert switched_targets == ["beta"]
    assert recorded_targets == ["beta"]
    assert captured == {
        "items": ["[1] alpha @ 2 windows", "[2] beta @ 1 windows", CANCEL_ITEM],
        "header": SWITCH_HEADER,
        "include_preview": True,
        "extra_bindings": (
            "--bind 'del:execute(/app/session-zx.mjs kill-single-from-line {})+reload("
            "/app/session-zx.mjs reload-sessions)' --bind "
            "'ctrl-n:down+execute-silent(/app/session-zx.mjs switch-from-line {})' "
            "--bind 'ctrl-p:up+execute-silent(/app/session-zx.mjs switch-from-line {})' "
            "--bind '1:pos(1)+accept,2:pos(2)+accept,3:pos(3)+accept,4:pos(4)+accept,"
            "5:pos(5)+accept,6:pos(6)+accept,7:pos(7)+accept,8:pos(8)+accept,"
            "9:pos(9)+accept'"
        ),
    }


def test_run_switch_returns_success_when_selection_is_empty() -> None:
    switched_targets: list[str] = []

    deps = SimpleNamespace(
        list_session_rows=lambda: None,
        get_current_session=lambda: 7,
        switch_session_selector=lambda _i, _h, _p, bindings: (
            "" if bindings == "" else "unexpected"
        ),
        switch_client=lambda target: switched_targets.append(target) or True,
        switch_script_path="",
    )

    result = run_switch(_context_with_deps(deps))

    assert result == EXIT_SUCCESS
    assert switched_targets == []


def test_run_switch_returns_error_for_invalid_selected_session_name() -> None:
    switched_targets: list[str] = []

    deps = SimpleNamespace(
        list_session_rows=lambda: ["bad:name @ 1 windows"],
        get_current_session=lambda: "alpha",
        switch_session_selector=lambda _i, _h, _p, _b: "[1] bad:name @ 1 windows",
        switch_client=lambda target: switched_targets.append(target) or True,
    )

    result = run_switch(_context_with_deps(deps))

    assert result == EXIT_ERROR
    assert switched_targets == []


def test_run_switch_maps_false_switch_client_result_to_error() -> None:
    deps = SimpleNamespace(
        list_session_rows=lambda: ["target @ 1 windows"],
        get_current_session=lambda: "alpha",
        switch_session_selector=lambda _i, _h, _p, _b: "[1] target @ 1 windows",
        switch_client=lambda _target: False,
    )

    result = run_switch(_context_with_deps(deps))

    assert result == EXIT_ERROR


def test_run_switch_succeeds_without_optional_frecency_recorder() -> None:
    switched_targets: list[str] = []

    deps = SimpleNamespace(
        list_session_rows=lambda: ["target @ 1 windows"],
        get_current_session=lambda: None,
        switch_session_selector=lambda _i, _h, _p, _b: "[1] target @ 1 windows",
        switch_client=lambda target: switched_targets.append(target) or None,
    )

    result = run_switch(_context_with_deps(deps))

    assert result == EXIT_SUCCESS
    assert switched_targets == ["target"]


def test_run_switch_passes_through_non_zero_int_exit_code() -> None:
    recorded_targets: list[str] = []

    deps = SimpleNamespace(
        list_session_rows=lambda: ["target @ 1 windows"],
        get_current_session=lambda: "alpha",
        switch_session_selector=lambda _i, _h, _p, _b: "[1] target @ 1 windows",
        switch_client=lambda _target: 23,
        record_frecency=lambda target: recorded_targets.append(target),
    )

    result = run_switch(_context_with_deps(deps))

    assert result == 23
    assert recorded_targets == []


def test_run_switch_rejects_invalid_switch_client_return_type() -> None:
    deps = SimpleNamespace(
        list_session_rows=lambda: ["target @ 1 windows"],
        get_current_session=lambda: "alpha",
        switch_session_selector=lambda _i, _h, _p, _b: "[1] target @ 1 windows",
        switch_client=lambda _target: "x",
    )

    with pytest.raises(TypeError, match="switch_client must return an int, bool, or None"):
        run_switch(_context_with_deps(deps))


def test_run_switch_returns_error_for_invalid_script_path() -> None:
    deps = SimpleNamespace(
        list_session_rows=lambda: ["target @ 1 windows"],
        get_current_session=lambda: "alpha",
        switch_session_selector=lambda _i, _h, _p, _b: "should-not-run",
        switch_client=lambda _target: True,
        switch_script_path="bad;path",
    )

    result = run_switch(_context_with_deps(deps))

    assert result == EXIT_ERROR


@pytest.mark.parametrize(
    ("attr_name", "attr_value", "message"),
    (
        ("list_session_rows", None, "Context deps must expose a callable list_session_rows"),
        (
            "get_current_session",
            None,
            "Context deps must expose a callable get_current_session",
        ),
        (
            "switch_session_selector",
            None,
            "Context deps must expose a callable switch_session_selector",
        ),
        ("switch_client", None, "Context deps must expose a callable switch_client"),
        (
            "record_frecency",
            "bad-recorder",
            "Context deps must expose a callable record_frecency when provided",
        ),
    ),
)
def test_run_switch_requires_expected_callable_dependencies(
    attr_name: str,
    attr_value: object,
    message: str,
) -> None:
    deps = SimpleNamespace(
        list_session_rows=lambda: [],
        get_current_session=lambda: "",
        switch_session_selector=lambda _i, _h, _p, _b: "",
        switch_client=lambda _target: True,
    )
    setattr(deps, attr_name, attr_value)

    with pytest.raises(TypeError, match=message):
        run_switch(_context_with_deps(deps))


def test_build_switch_items_handles_missing_current_session_and_not_found_current() -> None:
    without_current = _build_switch_items(["beta @ 1 windows", "alpha @ 2 windows"], "")
    with_missing_current = _build_switch_items(
        ["beta @ 1 windows", "alpha @ 2 windows"], "missing"
    )

    assert without_current == ["[1] beta @ 1 windows", "[2] alpha @ 2 windows", CANCEL_ITEM]
    assert with_missing_current == [
        "[1] beta @ 1 windows",
        "[2] alpha @ 2 windows",
        CANCEL_ITEM,
    ]


def test_build_switch_bindings_handles_empty_values() -> None:
    assert _build_switch_bindings(None) == ""
    assert _build_switch_bindings("   ") == ""


@pytest.mark.parametrize(
    ("script_path", "error_type", "message"),
    (
        (7, TypeError, "switch_script_path must be a string"),
        ("x" * 4097, ValueError, "switch_script_path is too long"),
        ("bad`path", ValueError, "switch_script_path contains unsafe characters"),
    ),
)
def test_build_switch_bindings_validates_script_path(
    script_path: object, error_type: type[Exception], message: str
) -> None:
    with pytest.raises(error_type, match=message):
        _build_switch_bindings(script_path)


def test_build_switch_bindings_returns_expected_bindings() -> None:
    bindings = _build_switch_bindings("/app/session-zx.mjs")

    assert (
        bindings
        == "--bind 'del:execute(/app/session-zx.mjs kill-single-from-line {})+reload("
        "/app/session-zx.mjs reload-sessions)' --bind "
        "'ctrl-n:down+execute-silent(/app/session-zx.mjs switch-from-line {})' "
        "--bind 'ctrl-p:up+execute-silent(/app/session-zx.mjs switch-from-line {})' "
        "--bind '1:pos(1)+accept,2:pos(2)+accept,3:pos(3)+accept,4:pos(4)+accept,"
        "5:pos(5)+accept,6:pos(6)+accept,7:pos(7)+accept,8:pos(8)+accept,"
        "9:pos(9)+accept'"
    )
