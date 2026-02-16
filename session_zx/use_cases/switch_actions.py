"""Switch-action use-case helpers."""

from collections.abc import Callable, Sequence
import re
from typing import Final, cast

from session_zx.app.context import AppContext
from session_zx.app.exit_codes import EXIT_ERROR, EXIT_SUCCESS
from session_zx.domain.formatting import add_number_prefixes
from session_zx.domain.parsing import parse_targets
from session_zx.domain.validation import validate_session_name

SessionRowsLoader = Callable[[], Sequence[object] | None]
CurrentSessionLoader = Callable[[], object | None]
SwitchSessionSelector = Callable[[Sequence[str], str, bool, str], object | None]
SwitchClient = Callable[[str], object | None]
FrecencyRecorder = Callable[[str], object | None]

SWITCH_HEADER: Final[str] = (
    "Select target session. Press 1-9 for quick switch. DEL to kill. Ctrl+N/P to "
    "preview."
)
CANCEL_ITEM: Final[str] = "[cancel]"
SCRIPT_PATH_MAX_LENGTH: Final[int] = 4096
_UNSAFE_SCRIPT_PATH_PATTERN = re.compile(r"[`$;|&<>(){}\[\]!\\]")
_NUMBER_BINDINGS: Final[tuple[str, ...]] = (
    "1:pos(1)+accept",
    "2:pos(2)+accept",
    "3:pos(3)+accept",
    "4:pos(4)+accept",
    "5:pos(5)+accept",
    "6:pos(6)+accept",
    "7:pos(7)+accept",
    "8:pos(8)+accept",
    "9:pos(9)+accept",
)


def run_switch(ctx: AppContext) -> int:
    """Run the interactive switch flow and return an exit code."""
    list_session_rows = _get_session_rows_loader(ctx.deps)
    get_current_session = _get_current_session_loader(ctx.deps)
    switch_session_selector = _get_switch_session_selector(ctx.deps)
    switch_client = _get_switch_client(ctx.deps)
    record_frecency = _get_optional_frecency_recorder(ctx.deps)

    rows = [str(row) for row in (list_session_rows() or ())]
    current_session = _normalize_optional_text(get_current_session())
    items = _build_switch_items(rows, current_session)
    try:
        extra_bindings = _build_switch_bindings(_get_switch_script_path(ctx.deps))
    except (TypeError, ValueError):
        return EXIT_ERROR

    selection = switch_session_selector(items, SWITCH_HEADER, True, extra_bindings)
    targets = parse_targets(None if selection is None else str(selection), current_session)
    if not targets:
        return EXIT_SUCCESS

    target = targets[0]
    try:
        validate_session_name(target)
    except ValueError:
        return EXIT_ERROR

    switch_result = _normalize_switch_result(switch_client(target))
    if switch_result != EXIT_SUCCESS:
        return switch_result

    if record_frecency is not None:
        record_frecency(target)

    return EXIT_SUCCESS


def run_worktree_switch(ctx: AppContext) -> int:
    """Run the filtered worktree switch flow."""
    from session_zx.domain.filtering import filter_sessions_by_worktrees

    list_session_rows = _get_session_rows_loader(ctx.deps)
    get_current_session = _get_current_session_loader(ctx.deps)
    switch_session_selector = _get_switch_session_selector(ctx.deps)
    switch_client = _get_switch_client(ctx.deps)
    record_frecency = _get_optional_frecency_recorder(ctx.deps)

    # We need additional loaders for worktrees
    get_git_worktrees = cast(Callable[[str], Sequence[str]], _require_callable(ctx.deps, "get_git_worktrees"))
    get_all_pane_paths = cast(Callable[[], dict[str, set[str]]], _require_callable(ctx.deps, "get_all_pane_paths"))
    get_pane_current_path = cast(Callable[[], str], _require_callable(ctx.deps, "get_pane_current_path"))

    current_path = get_pane_current_path()
    worktrees = list(get_git_worktrees(current_path))
    if not worktrees:
        return EXIT_SUCCESS

    all_rows = [str(row) for row in (list_session_rows() or ())]
    pane_paths = get_all_pane_paths()
    filtered_rows = filter_sessions_by_worktrees(all_rows, worktrees, pane_paths)

    if not filtered_rows:
        return EXIT_SUCCESS

    current_session = _normalize_optional_text(get_current_session())
    items = _build_switch_items(filtered_rows, current_session)
    try:
        extra_bindings = _build_switch_bindings(_get_switch_script_path(ctx.deps))
    except (TypeError, ValueError):
        return EXIT_ERROR

    header = f"Worktree sessions ({len(filtered_rows)}/{len(all_rows)}). Ctrl+N/P to preview."
    selection = switch_session_selector(items, header, True, extra_bindings)
    targets = parse_targets(None if selection is None else str(selection), current_session)
    if not targets:
        return EXIT_SUCCESS

    target = targets[0]
    switch_result = _normalize_switch_result(switch_client(target))
    if switch_result != EXIT_SUCCESS:
        return switch_result

    if record_frecency is not None:
        record_frecency(target)

    return EXIT_SUCCESS


def run_capital_switch(ctx: AppContext) -> int:
    """Run the filtered capital-session switch flow."""
    from session_zx.domain.filtering import filter_capital_sessions

    list_session_rows = _get_session_rows_loader(ctx.deps)
    get_current_session = _get_current_session_loader(ctx.deps)
    switch_session_selector = _get_switch_session_selector(ctx.deps)
    switch_client = _get_switch_client(ctx.deps)
    record_frecency = _get_optional_frecency_recorder(ctx.deps)

    all_rows = [str(row) for row in (list_session_rows() or ())]
    filtered_rows = filter_capital_sessions(all_rows)

    if not filtered_rows:
        return EXIT_SUCCESS

    current_session = _normalize_optional_text(get_current_session())
    items = _build_switch_items(filtered_rows, current_session)
    try:
        extra_bindings = _build_switch_bindings(_get_switch_script_path(ctx.deps))
    except (TypeError, ValueError):
        return EXIT_ERROR

    header = f"CAPITAL sessions ({len(filtered_rows)}/{len(all_rows)}). Ctrl+N/P to preview."
    selection = switch_session_selector(items, header, True, extra_bindings)
    targets = parse_targets(None if selection is None else str(selection), current_session)
    if not targets:
        return EXIT_SUCCESS

    target = targets[0]
    switch_result = _normalize_switch_result(switch_client(target))
    if switch_result != EXIT_SUCCESS:
        return switch_result

    if record_frecency is not None:
        record_frecency(target)

    return EXIT_SUCCESS


def _get_session_rows_loader(deps: object) -> SessionRowsLoader:
    list_session_rows = getattr(deps, "list_session_rows", None)
    if not callable(list_session_rows):
        raise TypeError("Context deps must expose a callable list_session_rows")

    return cast(SessionRowsLoader, list_session_rows)


def _get_current_session_loader(deps: object) -> CurrentSessionLoader:
    get_current_session = getattr(deps, "get_current_session", None)
    if not callable(get_current_session):
        raise TypeError("Context deps must expose a callable get_current_session")

    return cast(CurrentSessionLoader, get_current_session)


def _get_switch_session_selector(deps: object) -> SwitchSessionSelector:
    switch_session_selector = getattr(deps, "switch_session_selector", None)
    if not callable(switch_session_selector):
        raise TypeError("Context deps must expose a callable switch_session_selector")

    return cast(SwitchSessionSelector, switch_session_selector)


def _get_switch_client(deps: object) -> SwitchClient:
    switch_client = getattr(deps, "switch_client", None)
    if not callable(switch_client):
        raise TypeError("Context deps must expose a callable switch_client")

    return cast(SwitchClient, switch_client)


def _get_optional_frecency_recorder(deps: object) -> FrecencyRecorder | None:
    record_frecency = getattr(deps, "record_frecency", None)
    if record_frecency is None:
        return None

    if not callable(record_frecency):
        raise TypeError(
            "Context deps must expose a callable record_frecency when provided"
        )

    return cast(FrecencyRecorder, record_frecency)


def _get_switch_script_path(deps: object) -> object:
    return getattr(deps, "switch_script_path", "")


def _normalize_optional_text(raw_value: object | None) -> str:
    if raw_value is None:
        return ""

    return str(raw_value)


def _build_switch_items(rows: Sequence[str], current_session: str) -> list[str]:
    ordered_rows = _prioritize_current_session(rows, current_session)
    numbered_rows = add_number_prefixes(ordered_rows)
    return [*numbered_rows, CANCEL_ITEM]


def _prioritize_current_session(rows: Sequence[str], current_session: str) -> list[str]:
    ordered_rows = list(rows)
    if not current_session:
        return ordered_rows

    current_row = next(
        (row for row in ordered_rows if row.startswith(f"{current_session} @ ")),
        None,
    )
    if current_row is None:
        return ordered_rows

    return [current_row, *[row for row in ordered_rows if row != current_row]]


def _build_switch_bindings(script_path: object) -> str:
    if script_path is None:
        return ""

    if not isinstance(script_path, str):
        raise TypeError("switch_script_path must be a string")

    normalized_path = script_path.strip()
    if not normalized_path:
        return ""

    if len(normalized_path) > SCRIPT_PATH_MAX_LENGTH:
        raise ValueError("switch_script_path is too long")

    if _UNSAFE_SCRIPT_PATH_PATTERN.search(normalized_path):
        raise ValueError("switch_script_path contains unsafe characters")

    del_binding = (
        "--bind 'del:execute("
        f"{normalized_path} kill-single-from-line {{}}"
        f")+reload({normalized_path} reload-sessions)'"
    )
    ctrl_n_binding = (
        "--bind 'ctrl-n:down+execute-silent("
        f"{normalized_path} switch-from-line {{}}"
        ")'"
    )
    ctrl_p_binding = (
        "--bind 'ctrl-p:up+execute-silent("
        f"{normalized_path} switch-from-line {{}}"
        ")'"
    )
    number_binding = f"--bind '{','.join(_NUMBER_BINDINGS)}'"
    return " ".join((del_binding, ctrl_n_binding, ctrl_p_binding, number_binding))


def _normalize_switch_result(result: object | None) -> int:
    if result is None or result is True:
        return EXIT_SUCCESS

    if result is False:
        return EXIT_ERROR

    if isinstance(result, int):
        return result

    raise TypeError("switch_client must return an int, bool, or None")
