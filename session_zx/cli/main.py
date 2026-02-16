"""CLI entry orchestration helpers."""

from collections.abc import Callable, Sequence
from pathlib import Path

from session_zx.app.context import (
    AppContext,
    EnvPort,
    apply_env_defaults,
    build_app_context,
    load_runtime_env,
)
from session_zx.app.exit_codes import EXIT_SUCCESS
from session_zx.app.router import dispatch_action
from session_zx.cli.args import parse_cli_args

ActionSelector = Callable[[], object | None]
ActionDispatcher = Callable[[str, AppContext], int]

DEFAULT_PREVIEW_TEXT = "(^_^)"


def resolve_action(
    parsed_args: tuple[str | None, list[str]],
    select_action_uc: ActionSelector,
) -> str:
    """Resolve action from argv, falling back to action menu selection."""
    action, _ = parsed_args
    if action:
        return action

    selected = select_action_uc()
    return "" if selected is None else str(selected)


def main(
    argv: Sequence[object],
    *,
    deps: object,
    env_port: EnvPort,
    select_action_uc: ActionSelector,
    candidate_env_paths: Sequence[Path] = (),
    preview_text: str = DEFAULT_PREVIEW_TEXT,
    dispatch: ActionDispatcher = dispatch_action,
) -> int:
    """Run CLI orchestration and return process exit code."""
    parsed_action, parsed_argv = parse_cli_args(list(argv))
    action = resolve_action((parsed_action, parsed_argv), select_action_uc)

    if not action or action == "[cancel]":
        return EXIT_SUCCESS

    loaded_env = load_runtime_env(env_port, list(candidate_env_paths))
    resolved_env = apply_env_defaults(loaded_env, preview_text)
    context = build_app_context((action, parsed_argv), deps, resolved_env)
    return dispatch(action, context)
