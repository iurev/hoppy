from types import SimpleNamespace

import pytest

from session_zx.app.context import AppContext
from session_zx.app.exit_codes import EXIT_ERROR, EXIT_SUCCESS
from session_zx.use_cases.mutation_actions import (
    CANCEL_ITEM,
    CURRENT_ITEM,
    DETACH_HEADER,
    KILL_HEADER,
    RENAME_HEADER,
    _build_selection_items,
    run_detach,
    run_kill,
    run_new,
    run_rename,
)


def _context(
    *,
    action: str | None = None,
    argv: tuple[str, ...] = (),
    env: dict[str, str] | None = None,
    deps: object | None = None,
) -> AppContext:
    return AppContext(
        action=action,
        argv=argv,
        env={} if env is None else dict(env),
        deps=SimpleNamespace() if deps is None else deps,
    )


def test_run_new_creates_and_switches_for_valid_session_name() -> None:
    created: list[str] = []
    switched: list[str] = []
    deps = SimpleNamespace(
        prompt_session_name=lambda: "fresh_session",
        create_session=lambda name: created.append(name) or None,
        switch_client=lambda name: switched.append(name) or True,
    )

    result = run_new(_context(action="new", deps=deps))

    assert result == EXIT_SUCCESS
    assert created == ["fresh_session"]
    assert switched == ["fresh_session"]


def test_run_new_returns_success_when_prompt_is_empty() -> None:
    deps = SimpleNamespace(
        prompt_session_name=lambda: "",
        create_session=lambda _name: (_ for _ in ()).throw(AssertionError("create")),
        switch_client=lambda _name: (_ for _ in ()).throw(AssertionError("switch")),
    )

    result = run_new(_context(action="new", deps=deps))

    assert result == EXIT_SUCCESS


def test_run_new_returns_error_for_invalid_session_name() -> None:
    deps = SimpleNamespace(
        prompt_session_name=lambda: "bad:name",
        create_session=lambda _name: (_ for _ in ()).throw(AssertionError("create")),
        switch_client=lambda _name: (_ for _ in ()).throw(AssertionError("switch")),
    )

    result = run_new(_context(action="new", deps=deps))

    assert result == EXIT_ERROR


def test_run_new_returns_error_when_create_returns_false() -> None:
    switched: list[str] = []
    deps = SimpleNamespace(
        prompt_session_name=lambda: "fresh_session",
        create_session=lambda _name: False,
        switch_client=lambda name: switched.append(name) or True,
    )

    result = run_new(_context(action="new", deps=deps))

    assert result == EXIT_ERROR
    assert switched == []


def test_run_new_passes_through_int_exit_code_from_switch() -> None:
    deps = SimpleNamespace(
        prompt_session_name=lambda: "fresh_session",
        create_session=lambda _name: None,
        switch_client=lambda _name: 23,
    )

    result = run_new(_context(action="new", deps=deps))

    assert result == 23


def test_run_new_rejects_invalid_create_return_type() -> None:
    deps = SimpleNamespace(
        prompt_session_name=lambda: "fresh_session",
        create_session=lambda _name: "bad",
        switch_client=lambda _name: True,
    )

    with pytest.raises(TypeError, match="create_session must return an int, bool, or None"):
        run_new(_context(action="new", deps=deps))


@pytest.mark.parametrize(
    "attr_name",
    ("prompt_session_name", "create_session", "switch_client"),
)
def test_run_new_requires_expected_callable_dependencies(attr_name: str) -> None:
    deps = SimpleNamespace(
        prompt_session_name=lambda: "x",
        create_session=lambda _name: None,
        switch_client=lambda _name: None,
    )
    setattr(deps, attr_name, None)

    with pytest.raises(
        TypeError, match=f"Context deps must expose a callable {attr_name}"
    ):
        run_new(_context(action="new", deps=deps))


def test_run_rename_prompts_selects_and_renames_target() -> None:
    captured: dict[str, object] = {}
    renamed: list[tuple[str, str]] = []

    def selector(items: list[str], header: str, include_preview: bool) -> str:
        captured["items"] = list(items)
        captured["header"] = header
        captured["include_preview"] = include_preview
        return "[2] beta @ 1 windows"

    deps = SimpleNamespace(
        prompt_session_name=lambda: "renamed_sess",
        list_session_rows=lambda: ["beta @ 1 windows", "alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        rename_session_selector=selector,
        rename_session=lambda target, session_name: renamed.append((target, session_name))
        or None,
    )

    result = run_rename(_context(action="rename", deps=deps))

    assert result == EXIT_SUCCESS
    assert renamed == [("beta", "renamed_sess")]
    assert captured == {
        "items": ["[1] alpha @ 2 windows", "[2] beta @ 1 windows", CANCEL_ITEM],
        "header": RENAME_HEADER,
        "include_preview": True,
    }


def test_run_rename_returns_success_when_prompt_is_empty() -> None:
    deps = SimpleNamespace(
        prompt_session_name=lambda: "",
        list_session_rows=lambda: [],
        get_current_session=lambda: "alpha",
        rename_session_selector=lambda _items, _header, _include_preview: (
            (_ for _ in ()).throw(AssertionError("selector"))
        ),
        rename_session=lambda _target, _name: (_ for _ in ()).throw(
            AssertionError("rename")
        ),
    )

    result = run_rename(_context(action="rename", deps=deps))

    assert result == EXIT_SUCCESS


def test_run_rename_returns_error_for_invalid_new_name() -> None:
    deps = SimpleNamespace(
        prompt_session_name=lambda: "bad:name",
        list_session_rows=lambda: [],
        get_current_session=lambda: "alpha",
        rename_session_selector=lambda _items, _header, _include_preview: (
            (_ for _ in ()).throw(AssertionError("selector"))
        ),
        rename_session=lambda _target, _name: (_ for _ in ()).throw(
            AssertionError("rename")
        ),
    )

    result = run_rename(_context(action="rename", deps=deps))

    assert result == EXIT_ERROR


def test_run_rename_returns_success_when_no_target_selected() -> None:
    renamed: list[tuple[str, str]] = []
    deps = SimpleNamespace(
        prompt_session_name=lambda: "renamed",
        list_session_rows=lambda: ["alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        rename_session_selector=lambda _items, _header, _include_preview: None,
        rename_session=lambda target, session_name: renamed.append((target, session_name))
        or None,
    )

    result = run_rename(_context(action="rename", deps=deps))

    assert result == EXIT_SUCCESS
    assert renamed == []


def test_run_rename_returns_error_for_invalid_target() -> None:
    renamed: list[tuple[str, str]] = []
    deps = SimpleNamespace(
        prompt_session_name=lambda: "renamed",
        list_session_rows=lambda: ["bad:name @ 1 windows"],
        get_current_session=lambda: "alpha",
        rename_session_selector=lambda _items, _header, _include_preview: (
            "[1] bad:name @ 1 windows"
        ),
        rename_session=lambda target, session_name: renamed.append((target, session_name))
        or None,
    )

    result = run_rename(_context(action="rename", deps=deps))

    assert result == EXIT_ERROR
    assert renamed == []


def test_run_rename_maps_false_rename_result_to_error() -> None:
    deps = SimpleNamespace(
        prompt_session_name=lambda: "renamed",
        list_session_rows=lambda: ["alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        rename_session_selector=lambda _items, _header, _include_preview: (
            "[1] alpha @ 2 windows"
        ),
        rename_session=lambda _target, _name: False,
    )

    result = run_rename(_context(action="rename", deps=deps))

    assert result == EXIT_ERROR


@pytest.mark.parametrize(
    "attr_name",
    (
        "prompt_session_name",
        "list_session_rows",
        "get_current_session",
        "rename_session_selector",
        "rename_session",
    ),
)
def test_run_rename_requires_expected_callable_dependencies(attr_name: str) -> None:
    deps = SimpleNamespace(
        prompt_session_name=lambda: "renamed",
        list_session_rows=lambda: [],
        get_current_session=lambda: "",
        rename_session_selector=lambda _items, _header, _include_preview: "",
        rename_session=lambda _target, _name: None,
    )
    setattr(deps, attr_name, None)

    with pytest.raises(
        TypeError, match=f"Context deps must expose a callable {attr_name}"
    ):
        run_rename(_context(action="rename", deps=deps))


def test_run_kill_selects_and_kills_multiple_targets() -> None:
    captured: dict[str, object] = {}
    killed: list[str] = []

    def selector(items: list[str], header: str, include_preview: bool) -> str:
        captured["items"] = list(items)
        captured["header"] = header
        captured["include_preview"] = include_preview
        return "[1] beta @ 1 windows\n[2] alpha @ 2 windows"

    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows", "beta @ 1 windows"],
        get_current_session=lambda: "alpha",
        kill_session_selector=selector,
        kill_session=lambda target: killed.append(target) or None,
    )

    result = run_kill(_context(action="kill", deps=deps))

    assert result == EXIT_SUCCESS
    # Targets are killed in reverse order to avoid index shifts if we had any,
    # and to ensure deterministic behavior.
    assert sorted(killed) == ["alpha", "beta"]
    assert captured == {
        "items": ["[1] alpha @ 2 windows", "[2] beta @ 1 windows", CANCEL_ITEM],
        "header": KILL_HEADER,
        "include_preview": True,
    }


def test_run_kill_returns_success_when_no_targets_selected() -> None:
    killed: list[str] = []
    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        kill_session_selector=lambda _items, _header, _include_preview: None,
        kill_session=lambda target: killed.append(target) or None,
    )

    result = run_kill(_context(action="kill", deps=deps))

    assert result == EXIT_SUCCESS
    assert killed == []


def test_run_kill_returns_error_for_invalid_target_name() -> None:
    killed: list[str] = []
    deps = SimpleNamespace(
        list_session_rows=lambda: ["bad:name @ 1 windows"],
        get_current_session=lambda: "alpha",
        kill_session_selector=lambda _items, _header, _include_preview: (
            "[1] bad:name @ 1 windows"
        ),
        kill_session=lambda target: killed.append(target) or None,
    )

    result = run_kill(_context(action="kill", deps=deps))

    assert result == EXIT_ERROR
    assert killed == []


def test_run_kill_stops_and_returns_error_if_mutation_fails() -> None:
    killed: list[str] = []

    def fail_on_beta(target: str) -> bool:
        if target == "beta":
            return False
        killed.append(target)
        return True

    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows", "beta @ 1 windows"],
        get_current_session=lambda: "gamma",
        kill_session_selector=lambda _items, _header, _include_preview: (
            "[1] alpha @ 2 windows\n[2] beta @ 1 windows"
        ),
        kill_session=fail_on_beta,
    )

    result = run_kill(_context(action="kill", deps=deps))

    assert result == EXIT_ERROR
    # sorted(targets, reverse=True) -> ["beta", "alpha"]
    # It fails on "beta" first.
    assert killed == []


@pytest.mark.parametrize(
    "attr_name",
    (
        "list_session_rows",
        "get_current_session",
        "kill_session_selector",
        "kill_session",
    ),
)
def test_run_kill_requires_expected_callable_dependencies(attr_name: str) -> None:
    deps = SimpleNamespace(
        list_session_rows=lambda: [],
        get_current_session=lambda: "",
        kill_session_selector=lambda _items, _header, _include_preview: "",
        kill_session=lambda _target: None,
    )
    setattr(deps, attr_name, None)

    with pytest.raises(
        TypeError, match=f"Context deps must expose a callable {attr_name}"
    ):
        run_kill(_context(action="kill", deps=deps))


def test_run_detach_selects_and_detaches_attached_sessions() -> None:
    captured: dict[str, object] = {}
    detached: list[str] = []

    def selector(items: list[str], header: str, include_preview: bool) -> str:
        captured["items"] = list(items)
        captured["header"] = header
        captured["include_preview"] = include_preview
        return "[current]"

    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows", "beta @ 1 windows"],
        get_current_session=lambda: "alpha",
        get_attached_session_names=lambda: ["alpha"],
        detach_session_selector=selector,
        detach_session=lambda target: detached.append(target) or None,
    )

    result = run_detach(_context(action="detach", deps=deps))

    assert result == EXIT_SUCCESS
    assert detached == ["alpha"]
    assert captured == {
        "items": [CURRENT_ITEM, "alpha @ 2 windows", CANCEL_ITEM],
        "header": DETACH_HEADER,
        "include_preview": True,
    }


def test_run_detach_returns_success_when_no_targets_selected() -> None:
    detached: list[str] = []
    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        get_attached_session_names=lambda: ["alpha"],
        detach_session_selector=lambda _items, _header, _include_preview: None,
        detach_session=lambda target: detached.append(target) or None,
    )

    result = run_detach(_context(action="detach", deps=deps))

    assert result == EXIT_SUCCESS
    assert detached == []


def test_run_detach_returns_error_for_invalid_target_name() -> None:
    detached: list[str] = []
    deps = SimpleNamespace(
        list_session_rows=lambda: ["bad:name @ 1 windows"],
        get_current_session=lambda: "alpha",
        get_attached_session_names=lambda: ["bad:name"],
        detach_session_selector=lambda _items, _header, _include_preview: (
            "[1] bad:name @ 1 windows"
        ),
        detach_session=lambda target: detached.append(target) or None,
    )

    result = run_detach(_context(action="detach", deps=deps))

    assert result == EXIT_ERROR
    assert detached == []


def test_run_detach_stops_and_returns_error_if_mutation_fails() -> None:
    detached: list[str] = []
    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        get_attached_session_names=lambda: ["alpha"],
        detach_session_selector=lambda _items, _header, _include_preview: "[current]",
        detach_session=lambda _target: False,
    )

    result = run_detach(_context(action="detach", deps=deps))

    assert result == EXIT_ERROR
    assert detached == []


def test_run_detach_handles_attached_names_as_string() -> None:
    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        get_attached_session_names=lambda: "alpha",
        detach_session_selector=lambda items, _h, _p: items[0],
        detach_session=lambda _target: None,
    )

    result = run_detach(_context(action="detach", deps=deps))

    assert result == EXIT_SUCCESS


def test_run_detach_returns_success_for_none_attached_names() -> None:
    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        get_attached_session_names=lambda: None,
        detach_session_selector=lambda items, _h, _p: items[0],
        detach_session=lambda _target: None,
    )

    result = run_detach(_context(action="detach", deps=deps))

    assert result == EXIT_SUCCESS


def test_run_detach_raises_type_error_for_invalid_attached_names_type() -> None:
    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        get_attached_session_names=lambda: 123,
        detach_session_selector=lambda _i, _h, _p: "",
        detach_session=lambda _target: None,
    )

    with pytest.raises(
        TypeError, match="get_attached_session_names must return an iterable or None"
    ):
        run_detach(_context(action="detach", deps=deps))


@pytest.mark.parametrize(
    "attr_name",
    (
        "list_session_rows",
        "get_current_session",
        "detach_session_selector",
        "get_attached_session_names",
        "detach_session",
    ),
)
def test_run_detach_requires_expected_callable_dependencies(attr_name: str) -> None:
    deps = SimpleNamespace(
        list_session_rows=lambda: [],
        get_current_session=lambda: "",
        detach_session_selector=lambda _items, _header, _include_preview: "",
        get_attached_session_names=lambda: [],
        detach_session=lambda _target: None,
    )
    setattr(deps, attr_name, None)

    with pytest.raises(
        TypeError, match=f"Context deps must expose a callable {attr_name}"
    ):
        run_detach(_context(action="detach", deps=deps))


def test_build_selection_items_handles_no_current_session() -> None:
    rows = ["alpha @ 1 windows", "beta @ 2 windows"]
    result = _build_selection_items(rows, "", include_current=True)
    assert result == [
        CURRENT_ITEM,
        "[1] alpha @ 1 windows",
        "[2] beta @ 2 windows",
        CANCEL_ITEM,
    ]


def test_build_selection_items_handles_no_current_session_exclude_current() -> None:
    rows = ["alpha @ 1 windows", "beta @ 2 windows"]
    result = _build_selection_items(rows, "", include_current=False)
    assert result == [
        "[1] alpha @ 1 windows",
        "[2] beta @ 2 windows",
        CANCEL_ITEM,
    ]


def test_run_kill_kills_targets_in_reverse_sorted_order() -> None:
    captured: dict[str, object] = {}
    killed: list[str] = []

    def selector(items: list[str], header: str, include_preview: bool) -> str:
        captured["items"] = list(items)
        captured["header"] = header
        captured["include_preview"] = include_preview
        return "[1] alpha @ 2 windows\n[2] beta @ 1 windows"

    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows", "beta @ 1 windows"],
        get_current_session=lambda: None,
        kill_session_selector=selector,
        kill_session=lambda target: killed.append(target) or None,
    )

    result = run_kill(_context(action="kill", deps=deps))

    assert result == EXIT_SUCCESS
    assert killed == ["beta", "alpha"]
    assert captured == {
        "items": [
            CURRENT_ITEM,
            "[1] alpha @ 2 windows",
            "[2] beta @ 1 windows",
            CANCEL_ITEM,
        ],
        "header": KILL_HEADER,
        "include_preview": True,
    }


def test_run_kill_returns_success_when_no_target_selected() -> None:
    killed: list[str] = []
    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        kill_session_selector=lambda _items, _header, _include_preview: "[cancel]",
        kill_session=lambda target: killed.append(target) or None,
    )

    result = run_kill(_context(action="kill", deps=deps))

    assert result == EXIT_SUCCESS
    assert killed == []


def test_run_kill_returns_error_for_invalid_target() -> None:
    killed: list[str] = []
    deps = SimpleNamespace(
        list_session_rows=lambda: ["bad:name @ 1 windows"],
        get_current_session=lambda: "alpha",
        kill_session_selector=lambda _items, _header, _include_preview: (
            "[1] bad:name @ 1 windows"
        ),
        kill_session=lambda target: killed.append(target) or None,
    )

    result = run_kill(_context(action="kill", deps=deps))

    assert result == EXIT_ERROR
    assert killed == []


def test_run_kill_passes_through_non_zero_int_and_stops_remaining_kills() -> None:
    killed: list[str] = []

    def kill_session(target: str) -> object:
        killed.append(target)
        return 23 if target == "beta" else None

    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows", "beta @ 1 windows"],
        get_current_session=lambda: "alpha",
        kill_session_selector=lambda _items, _header, _include_preview: (
            "[1] alpha @ 2 windows\n[2] beta @ 1 windows"
        ),
        kill_session=kill_session,
    )

    result = run_kill(_context(action="kill", deps=deps))

    assert result == 23
    assert killed == ["beta"]


@pytest.mark.parametrize(
    "attr_name",
    (
        "list_session_rows",
        "get_current_session",
        "kill_session_selector",
        "kill_session",
    ),
)
def test_run_kill_requires_expected_callable_dependencies(attr_name: str) -> None:
    deps = SimpleNamespace(
        list_session_rows=lambda: [],
        get_current_session=lambda: "",
        kill_session_selector=lambda _items, _header, _include_preview: "",
        kill_session=lambda _target: None,
    )
    setattr(deps, attr_name, None)

    with pytest.raises(
        TypeError, match=f"Context deps must expose a callable {attr_name}"
    ):
        run_kill(_context(action="kill", deps=deps))


def test_run_detach_filters_to_attached_sessions_and_dedupes_selector_items() -> None:
    captured: dict[str, object] = {}
    detached: list[str] = []

    def selector(items: list[str], header: str, include_preview: bool) -> str:
        captured["items"] = list(items)
        captured["header"] = header
        captured["include_preview"] = include_preview
        return "beta @ 1 windows"

    deps = SimpleNamespace(
        list_session_rows=lambda: [
            "alpha @ 2 windows",
            "beta @ 1 windows",
            "alpha @ 2 windows",
            "gamma @ 4 windows",
        ],
        get_current_session=lambda: "alpha",
        detach_session_selector=selector,
        get_attached_session_names=lambda: {"alpha", "beta"},
        detach_session=lambda target: detached.append(target) or None,
    )

    result = run_detach(_context(action="detach", deps=deps))

    assert result == EXIT_SUCCESS
    assert detached == ["beta"]
    assert captured == {
        "items": [CURRENT_ITEM, "alpha @ 2 windows", "beta @ 1 windows", CANCEL_ITEM],
        "header": DETACH_HEADER,
        "include_preview": True,
    }


def test_run_detach_allows_selecting_current_item() -> None:
    detached: list[str] = []
    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        detach_session_selector=lambda _items, _header, _include_preview: CURRENT_ITEM,
        get_attached_session_names=lambda: {"alpha"},
        detach_session=lambda target: detached.append(target) or None,
    )

    result = run_detach(_context(action="detach", deps=deps))

    assert result == EXIT_SUCCESS
    assert detached == ["alpha"]


def test_run_detach_returns_success_when_no_target_selected() -> None:
    detached: list[str] = []
    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        detach_session_selector=lambda _items, _header, _include_preview: "[cancel]",
        get_attached_session_names=lambda: None,
        detach_session=lambda target: detached.append(target) or None,
    )

    result = run_detach(_context(action="detach", deps=deps))

    assert result == EXIT_SUCCESS
    assert detached == []


def test_run_detach_returns_error_for_invalid_target() -> None:
    detached: list[str] = []
    deps = SimpleNamespace(
        list_session_rows=lambda: ["bad:name @ 1 windows"],
        get_current_session=lambda: "alpha",
        detach_session_selector=lambda _items, _header, _include_preview: (
            "bad:name @ 1 windows"
        ),
        get_attached_session_names=lambda: {"bad:name"},
        detach_session=lambda target: detached.append(target) or None,
    )

    result = run_detach(_context(action="detach", deps=deps))

    assert result == EXIT_ERROR
    assert detached == []


def test_run_detach_maps_false_detach_result_to_error() -> None:
    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        detach_session_selector=lambda _items, _header, _include_preview: (
            "alpha @ 2 windows"
        ),
        get_attached_session_names=lambda: {"alpha"},
        detach_session=lambda _target: False,
    )

    result = run_detach(_context(action="detach", deps=deps))

    assert result == EXIT_ERROR


def test_run_detach_accepts_string_from_attached_session_loader() -> None:
    detached: list[str] = []
    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows", "beta @ 1 windows"],
        get_current_session=lambda: "alpha",
        detach_session_selector=lambda _items, _header, _include_preview: (
            "beta @ 1 windows"
        ),
        get_attached_session_names=lambda: "beta",
        detach_session=lambda target: detached.append(target) or None,
    )

    result = run_detach(_context(action="detach", deps=deps))

    assert result == EXIT_SUCCESS
    assert detached == ["beta"]


def test_run_detach_rejects_non_iterable_attached_session_values() -> None:
    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows"],
        get_current_session=lambda: "alpha",
        detach_session_selector=lambda _items, _header, _include_preview: "[cancel]",
        get_attached_session_names=lambda: 7,
        detach_session=lambda _target: None,
    )

    with pytest.raises(
        TypeError,
        match="get_attached_session_names must return an iterable or None",
    ):
        run_detach(_context(action="detach", deps=deps))


@pytest.mark.parametrize(
    "attr_name",
    (
        "list_session_rows",
        "get_current_session",
        "detach_session_selector",
        "get_attached_session_names",
        "detach_session",
    ),
)
def test_run_detach_requires_expected_callable_dependencies(attr_name: str) -> None:
    deps = SimpleNamespace(
        list_session_rows=lambda: [],
        get_current_session=lambda: "",
        detach_session_selector=lambda _items, _header, _include_preview: "",
        get_attached_session_names=lambda: set(),
        detach_session=lambda _target: None,
    )
    setattr(deps, attr_name, None)

    with pytest.raises(
        TypeError, match=f"Context deps must expose a callable {attr_name}"
    ):
        run_detach(_context(action="detach", deps=deps))


def test_build_selection_items_without_current_session_and_without_include_current() -> None:
    result = _build_selection_items(
        ["beta @ 1 windows", "alpha @ 2 windows"],
        "",
        include_current=False,
    )

    assert result == ["[1] beta @ 1 windows", "[2] alpha @ 2 windows", CANCEL_ITEM]


def test_build_selection_items_preserves_order_when_current_session_not_found() -> None:
    result = _build_selection_items(
        ["beta @ 1 windows", "alpha @ 2 windows"],
        "missing",
        include_current=True,
    )

    assert result == ["[1] beta @ 1 windows", "[2] alpha @ 2 windows", CANCEL_ITEM]
