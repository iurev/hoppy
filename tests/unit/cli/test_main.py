from pathlib import Path

from session_zx.app.context import AppContext
from session_zx.app.exit_codes import EXIT_SUCCESS
from session_zx.cli.main import main, resolve_action


class StubEnvPort:
    def __init__(self, values: dict[object, object]) -> None:
        self.values = values
        self.calls: list[list[Path]] = []

    def load_first_existing(self, paths: list[Path]) -> dict[object, object]:
        self.calls.append(list(paths))
        return self.values


def test_resolve_action_prefers_non_empty_cli_action() -> None:
    selector_called = False

    def selector() -> str:
        nonlocal selector_called
        selector_called = True
        return "new"

    action = resolve_action(("switch", ["line"]), selector)

    assert action == "switch"
    assert selector_called is False


def test_resolve_action_uses_selector_for_empty_cli_action() -> None:
    action = resolve_action(("", []), lambda: 42)

    assert action == "42"


def test_resolve_action_returns_empty_string_when_selector_returns_none() -> None:
    action = resolve_action((None, []), lambda: None)

    assert action == ""


def test_main_returns_success_for_empty_resolved_action_without_dispatch() -> None:
    env_port = StubEnvPort({})
    dispatch_called = False

    def dispatch(_: str, __: AppContext) -> int:
        nonlocal dispatch_called
        dispatch_called = True
        return 9

    result = main(
        [],
        deps=object(),
        env_port=env_port,
        select_action_uc=lambda: None,
        candidate_env_paths=[Path("/tmp/.envs")],
        dispatch=dispatch,
    )

    assert result == EXIT_SUCCESS
    assert env_port.calls == []
    assert dispatch_called is False


def test_main_returns_success_for_cancel_action_without_dispatch() -> None:
    env_port = StubEnvPort({})

    result = main(
        [],
        deps=object(),
        env_port=env_port,
        select_action_uc=lambda: "[cancel]",
        candidate_env_paths=[Path("/tmp/.envs")],
        dispatch=lambda _action, _ctx: (_ for _ in ()).throw(AssertionError("dispatch")),
    )

    assert result == EXIT_SUCCESS
    assert env_port.calls == []


def test_main_loads_env_builds_context_and_dispatches_action() -> None:
    deps = object()
    env_port = StubEnvPort({"TMUX_FZF_BIN": "sk", "TMUX_FZF_PREVIEW_OPTIONS": "--preview"})
    candidate_paths = [Path("/tmp/.envs"), Path("/tmp/fallback")]
    received: list[tuple[str, AppContext]] = []

    def dispatch(action: str, context: AppContext) -> int:
        received.append((action, context))
        return 23

    result = main(
        ["switch", "line", 7],
        deps=deps,
        env_port=env_port,
        select_action_uc=lambda: (_ for _ in ()).throw(AssertionError("selector")),
        candidate_env_paths=candidate_paths,
        preview_text="(x_x)",
        dispatch=dispatch,
    )

    assert result == 23
    assert env_port.calls == [candidate_paths]
    assert len(received) == 1
    action, context = received[0]
    assert action == "switch"
    assert context.action == "switch"
    assert context.argv == ("line", "7")
    assert context.deps is deps
    assert context.env == {
        "TMUX_FZF_BIN": "sk",
        "TMUX_FZF_PREVIEW_OPTIONS": "--preview",
        "TMUX_FZF_OPTIONS": "",
        "FZF_DEFAULT_OPTS": "",
    }
