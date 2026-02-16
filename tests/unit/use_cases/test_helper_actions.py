from types import SimpleNamespace
import os

import pytest

from session_zx.app.context import AppContext
from session_zx.app.exit_codes import EXIT_SUCCESS
from session_zx.use_cases.helper_actions import (
    DEFAULT_SESSION_SWITCH_DEBOUNCE_MS,
    TOKEN_SUFFIX_LENGTH,
    _load_now_ms,
    _resolve_debounce_delay_ms,
    run_delayed_switch,
    run_kill_single_from_line,
    run_reload_sessions,
    run_switch_from_line,
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


def test_run_reload_sessions_writes_numbered_rows_with_trailing_newline() -> None:
    writes: list[str] = []
    deps = SimpleNamespace(
        list_session_rows=lambda: ["alpha @ 2 windows", "beta @ 1 windows"],
        write_stdout=lambda text: writes.append(text),
    )

    result = run_reload_sessions(_context(action="reload-sessions", deps=deps))

    assert result == EXIT_SUCCESS
    assert writes == ["[1] alpha @ 2 windows\n[2] beta @ 1 windows\n"]


def test_run_reload_sessions_outputs_single_newline_when_rows_missing() -> None:
    writes: list[str] = []
    deps = SimpleNamespace(
        list_session_rows=lambda: None,
        write_stdout=lambda text: writes.append(text),
    )

    result = run_reload_sessions(_context(action="reload-sessions", deps=deps))

    assert result == EXIT_SUCCESS
    assert writes == ["\n"]


@pytest.mark.parametrize("attr_name", ("list_session_rows", "write_stdout"))
def test_run_reload_sessions_requires_expected_callables(attr_name: str) -> None:
    deps = SimpleNamespace(
        list_session_rows=lambda: [],
        write_stdout=lambda _text: None,
    )
    setattr(deps, attr_name, None)

    with pytest.raises(
        TypeError, match=f"Context deps must expose a callable {attr_name}"
    ):
        run_reload_sessions(_context(action="reload-sessions", deps=deps))


def test_run_kill_single_from_line_noops_when_session_name_is_empty() -> None:
    result = run_kill_single_from_line(_context(action="kill-single-from-line"), "")
    assert result == EXIT_SUCCESS


def test_run_kill_single_from_line_extracts_target_from_context_argv() -> None:
    killed: list[str] = []
    deps = SimpleNamespace(kill_session=lambda target: killed.append(target))

    result = run_kill_single_from_line(
        _context(
            action="kill-single-from-line",
            argv=("[7] target @ 3 windows",),
            deps=deps,
        )
    )

    assert result == EXIT_SUCCESS
    assert killed == ["target"]


def test_run_kill_single_from_line_ignores_kill_errors() -> None:
    deps = SimpleNamespace(
        kill_session=lambda _target: (_ for _ in ()).throw(RuntimeError("tmux failed"))
    )

    result = run_kill_single_from_line(
        _context(action="kill-single-from-line", deps=deps),
        "[1] bad @ 1 windows",
    )

    assert result == EXIT_SUCCESS


@pytest.mark.parametrize("line", ("", "[cancel]"))
def test_run_switch_from_line_noops_for_empty_or_cancel_rows(line: str) -> None:
    result = run_switch_from_line(_context(action="switch-from-line"), line)
    assert result == EXIT_SUCCESS


def test_run_switch_from_line_schedules_delayed_helper_when_write_and_spawn_succeed() -> None:
    writes: list[dict[str, object]] = []
    spawned_tokens: list[str] = []
    switched_targets: list[str] = []

    def write_debounce_state(state: dict[str, object]) -> bool:
        writes.append(dict(state))
        return True

    deps = SimpleNamespace(
        now_ms=lambda: 123,
        random_suffix=lambda length: "suffixxy" if length == TOKEN_SUFFIX_LENGTH else "bad",
        write_debounce_state=write_debounce_state,
        spawn_delayed_switch=lambda token: spawned_tokens.append(token) or None,
        switch_client=lambda target: switched_targets.append(target) or True,
    )

    result = run_switch_from_line(
        _context(action="switch-from-line", deps=deps),
        "[1] alpha @ 2 windows",
    )

    token = writes[0]["token"]
    assert result == EXIT_SUCCESS
    assert writes == [
        {
            "lastWrite": 123,
            "lastTarget": "alpha",
            "token": token,
        }
    ]
    assert token == f"123-{os.getpid()}-suffixxy"
    assert spawned_tokens == [token]
    assert switched_targets == []


def test_run_switch_from_line_falls_back_to_immediate_switch_when_state_write_fails() -> None:
    writes: list[dict[str, object]] = []
    switched_targets: list[str] = []
    timestamps = iter((200, 201))

    def write_debounce_state(state: dict[str, object]) -> bool:
        writes.append(dict(state))
        return len(writes) > 1

    deps = SimpleNamespace(
        now_ms=lambda: next(timestamps),
        random_suffix=lambda _length: "suffixzz",
        process_id=7,
        write_debounce_state=write_debounce_state,
        switch_client=lambda target: switched_targets.append(target) or True,
    )

    result = run_switch_from_line(
        _context(action="switch-from-line", deps=deps),
        "[2] beta @ 1 windows",
    )

    assert result == EXIT_SUCCESS
    assert switched_targets == ["beta"]
    assert writes == [
        {
            "lastWrite": 200,
            "lastTarget": "beta",
            "token": "200-7-suffixzz",
        },
        {
            "lastWrite": 201,
            "lastTarget": "beta",
            "token": None,
        },
    ]


def test_run_switch_from_line_falls_back_when_spawn_returns_false() -> None:
    writes: list[dict[str, object]] = []
    switched_targets: list[str] = []
    spawned_tokens: list[str] = []
    timestamps = iter((300, 301))

    def write_debounce_state(state: dict[str, object]) -> bool:
        writes.append(dict(state))
        return True

    deps = SimpleNamespace(
        now_ms=lambda: next(timestamps),
        random_suffix=lambda _length: "suffixab",
        process_id=9,
        write_debounce_state=write_debounce_state,
        spawn_delayed_switch=lambda token: spawned_tokens.append(token) or False,
        switch_client=lambda target: switched_targets.append(target) or True,
    )

    result = run_switch_from_line(
        _context(action="switch-from-line", deps=deps),
        "[1] gamma @ 9 windows",
    )

    assert result == EXIT_SUCCESS
    assert switched_targets == ["gamma"]
    assert spawned_tokens == ["300-9-suffixab"]
    assert writes == [
        {
            "lastWrite": 300,
            "lastTarget": "gamma",
            "token": "300-9-suffixab",
        },
        {
            "lastWrite": 301,
            "lastTarget": "gamma",
            "token": None,
        },
    ]


def test_run_switch_from_line_does_not_clear_token_when_immediate_switch_fails() -> None:
    writes: list[dict[str, object]] = []

    def write_debounce_state(state: dict[str, object]) -> bool:
        writes.append(dict(state))
        return False

    deps = SimpleNamespace(
        now_ms=lambda: 400,
        random_suffix=lambda _length: "suffixxy",
        process_id=12,
        write_debounce_state=write_debounce_state,
        switch_client=lambda _target: False,
    )

    result = run_switch_from_line(
        _context(action="switch-from-line", deps=deps),
        "[1] delta @ 1 windows",
    )

    assert result == EXIT_SUCCESS
    assert writes == [
        {
            "lastWrite": 400,
            "lastTarget": "delta",
            "token": "400-12-suffixxy",
        }
    ]


def test_run_switch_from_line_swallows_scheduling_exceptions() -> None:
    deps = SimpleNamespace(
        now_ms=lambda: 1,
        random_suffix=lambda _length: "suffixxy",
        process_id="not-an-int",
        write_debounce_state=lambda _state: True,
    )

    result = run_switch_from_line(
        _context(action="switch-from-line", deps=deps),
        "[1] epsilon @ 1 windows",
    )

    assert result == EXIT_SUCCESS


def test_run_delayed_switch_noops_when_token_is_empty() -> None:
    result = run_delayed_switch(_context(action="delayed-switch"))
    assert result == EXIT_SUCCESS


def test_run_delayed_switch_executes_and_clears_token_for_matching_state() -> None:
    sleep_calls: list[int] = []
    switched_targets: list[str] = []
    writes: list[dict[str, object]] = []

    deps = SimpleNamespace(
        sleep_ms=lambda delay: sleep_calls.append(delay),
        read_debounce_state=lambda: {
            "lastWrite": 1,
            "lastTarget": " alpha ",
            "token": "tok-1",
        },
        switch_client=lambda target: switched_targets.append(target) or True,
        write_debounce_state=lambda state: writes.append(dict(state)) or True,
        now_ms=lambda: 900,
    )

    result = run_delayed_switch(
        _context(
            action="delayed-switch",
            argv=("tok-1",),
            env={"SESSION_SWITCH_DEBOUNCE_MS": "450"},
            deps=deps,
        )
    )

    assert result == EXIT_SUCCESS
    assert sleep_calls == [450]
    assert switched_targets == ["alpha"]
    assert writes == [{"lastWrite": 900, "lastTarget": "alpha", "token": None}]


def test_run_delayed_switch_noops_when_token_does_not_match_state() -> None:
    switched_targets: list[str] = []
    writes: list[dict[str, object]] = []

    deps = SimpleNamespace(
        sleep_ms=lambda _delay: None,
        read_debounce_state=lambda: {"lastWrite": 1, "lastTarget": "alpha", "token": "other"},
        switch_client=lambda target: switched_targets.append(target) or True,
        write_debounce_state=lambda state: writes.append(dict(state)) or True,
        now_ms=lambda: 901,
    )

    result = run_delayed_switch(
        _context(action="delayed-switch", argv=("tok-1",), deps=deps)
    )

    assert result == EXIT_SUCCESS
    assert switched_targets == []
    assert writes == []


def test_run_delayed_switch_noops_when_state_is_not_a_mapping() -> None:
    switched_targets: list[str] = []

    deps = SimpleNamespace(
        sleep_ms=lambda _delay: None,
        read_debounce_state=lambda: "invalid-json-string",
        switch_client=lambda target: switched_targets.append(target) or True,
        write_debounce_state=lambda _state: True,
        now_ms=lambda: 902,
    )

    result = run_delayed_switch(
        _context(action="delayed-switch", argv=("tok-1",), deps=deps)
    )

    assert result == EXIT_SUCCESS
    assert switched_targets == []


def test_run_delayed_switch_does_not_clear_token_when_switch_fails() -> None:
    writes: list[dict[str, object]] = []

    deps = SimpleNamespace(
        sleep_ms=lambda _delay: None,
        read_debounce_state=lambda: {"lastWrite": 1, "lastTarget": "alpha", "token": "tok-2"},
        switch_client=lambda _target: False,
        write_debounce_state=lambda state: writes.append(dict(state)) or True,
        now_ms=lambda: 903,
    )

    result = run_delayed_switch(
        _context(action="delayed-switch", argv=("tok-2",), deps=deps)
    )

    assert result == EXIT_SUCCESS
    assert writes == []


def test_run_delayed_switch_swallows_internal_errors() -> None:
    deps = SimpleNamespace(
        sleep_ms=lambda _delay: (_ for _ in ()).throw(RuntimeError("sleep failed")),
    )

    result = run_delayed_switch(
        _context(action="delayed-switch", argv=("tok-3",), deps=deps)
    )

    assert result == EXIT_SUCCESS


@pytest.mark.parametrize(
    ("env", "expected"),
    (
        ({}, DEFAULT_SESSION_SWITCH_DEBOUNCE_MS),
        ({"SESSION_SWITCH_DEBOUNCE_MS": "0"}, DEFAULT_SESSION_SWITCH_DEBOUNCE_MS),
        ({"SESSION_SWITCH_DEBOUNCE_MS": "bad"}, DEFAULT_SESSION_SWITCH_DEBOUNCE_MS),
        ({"SESSION_SWITCH_DEBOUNCE_MS": "25"}, 25),
        ({"SESSION_SWITCH_DEBOUNCE_MS": "-3"}, -3),
    ),
)
def test_resolve_debounce_delay_ms_matches_expected_rules(
    env: dict[str, str], expected: int
) -> None:
    assert _resolve_debounce_delay_ms(env) == expected


def test_load_now_ms_normalizes_non_numeric_values_to_zero() -> None:
    assert _load_now_ms(SimpleNamespace(now_ms=lambda: 17)) == 17
    assert _load_now_ms(SimpleNamespace(now_ms=lambda: "not-a-number")) == 0
