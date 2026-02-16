"""Mutation-action use cases for session create/rename/kill/detach flows."""

from collections.abc import Callable, Iterable, Sequence
from typing import Final, cast

from session_zx.app.context import AppContext
from session_zx.app.exit_codes import EXIT_ERROR, EXIT_SUCCESS
from session_zx.domain.filtering import dedupe_preserve_order
from session_zx.domain.formatting import add_number_prefixes
from session_zx.domain.parsing import extract_session_name, parse_targets
from session_zx.domain.validation import validate_session_name

SessionRowsLoader = Callable[[], Sequence[object] | None]
CurrentSessionLoader = Callable[[], object | None]
SessionNamePrompter = Callable[[], object | None]
SessionSelector = Callable[[Sequence[str], str, bool], object | None]
SingleTargetMutator = Callable[[str], object | None]
RenameSessionMutator = Callable[[str, str], object | None]
AttachedNamesLoader = Callable[[], object | None]

RENAME_HEADER: Final[str] = "Select target session."
KILL_HEADER: Final[str] = "Select target session(s). Press TAB to mark multiple items."
DETACH_HEADER: Final[str] = "Select target session(s). Press TAB to mark multiple items."
CANCEL_ITEM: Final[str] = "[cancel]"
CURRENT_ITEM: Final[str] = "[current]"


def run_new(ctx: AppContext) -> int:
    """Create and switch to a new session when prompt input is valid."""
    prompt_session_name = cast(
        SessionNamePrompter,
        _require_callable(ctx.deps, "prompt_session_name"),
    )
    create_session = cast(
        SingleTargetMutator,
        _require_callable(ctx.deps, "create_session"),
    )
    switch_client = cast(
        SingleTargetMutator,
        _require_callable(ctx.deps, "switch_client"),
    )

    session_name = _normalize_optional_text(prompt_session_name()).strip()
    if not session_name:
        return EXIT_SUCCESS

    try:
        validate_session_name(session_name)
    except ValueError:
        return EXIT_ERROR

    create_result = _normalize_mutation_result(create_session(session_name), "create_session")
    if create_result != EXIT_SUCCESS:
        return create_result

    return _normalize_mutation_result(switch_client(session_name), "switch_client")


def run_rename(ctx: AppContext) -> int:
    """Rename a selected session to a prompted new session name."""
    prompt_session_name = cast(
        SessionNamePrompter,
        _require_callable(ctx.deps, "prompt_session_name"),
    )
    list_session_rows = cast(
        SessionRowsLoader,
        _require_callable(ctx.deps, "list_session_rows"),
    )
    get_current_session = cast(
        CurrentSessionLoader,
        _require_callable(ctx.deps, "get_current_session"),
    )
    rename_session_selector = cast(
        SessionSelector,
        _require_callable(ctx.deps, "rename_session_selector"),
    )
    rename_session = cast(
        RenameSessionMutator,
        _require_callable(ctx.deps, "rename_session"),
    )

    session_name = _normalize_optional_text(prompt_session_name()).strip()
    if not session_name:
        return EXIT_SUCCESS

    try:
        validate_session_name(session_name)
    except ValueError:
        return EXIT_ERROR

    rows = [str(row) for row in (list_session_rows() or ())]
    current_session = _normalize_optional_text(get_current_session())
    selection_items = _build_selection_items(rows, current_session, include_current=True)
    selection = rename_session_selector(selection_items, RENAME_HEADER, True)
    targets = _parse_selection_targets(selection, current_session)
    if not targets:
        return EXIT_SUCCESS

    target = targets[0]
    try:
        validate_session_name(target)
    except ValueError:
        return EXIT_ERROR

    return _normalize_mutation_result(
        rename_session(target, session_name),
        "rename_session",
    )


def run_kill(ctx: AppContext) -> int:
    """Kill one or more selected sessions after validation."""
    list_session_rows = cast(
        SessionRowsLoader,
        _require_callable(ctx.deps, "list_session_rows"),
    )
    get_current_session = cast(
        CurrentSessionLoader,
        _require_callable(ctx.deps, "get_current_session"),
    )
    kill_session_selector = cast(
        SessionSelector,
        _require_callable(ctx.deps, "kill_session_selector"),
    )
    kill_session = cast(
        SingleTargetMutator,
        _require_callable(ctx.deps, "kill_session"),
    )

    rows = [str(row) for row in (list_session_rows() or ())]
    current_session = _normalize_optional_text(get_current_session())
    selection_items = _build_selection_items(rows, current_session, include_current=True)
    selection = kill_session_selector(selection_items, KILL_HEADER, True)
    targets = _parse_selection_targets(selection, current_session)
    if not targets:
        return EXIT_SUCCESS

    if not _are_valid_session_names(targets):
        return EXIT_ERROR

    for target in sorted(targets, reverse=True):
        result = _normalize_mutation_result(kill_session(target), "kill_session")
        if result != EXIT_SUCCESS:
            return result

    return EXIT_SUCCESS


def run_detach(ctx: AppContext) -> int:
    """Detach selected attached sessions from tmux clients."""
    list_session_rows = cast(
        SessionRowsLoader,
        _require_callable(ctx.deps, "list_session_rows"),
    )
    get_current_session = cast(
        CurrentSessionLoader,
        _require_callable(ctx.deps, "get_current_session"),
    )
    detach_session_selector = cast(
        SessionSelector,
        _require_callable(ctx.deps, "detach_session_selector"),
    )
    get_attached_session_names = cast(
        AttachedNamesLoader,
        _require_callable(ctx.deps, "get_attached_session_names"),
    )
    detach_session = cast(
        SingleTargetMutator,
        _require_callable(ctx.deps, "detach_session"),
    )

    rows = [str(row) for row in (list_session_rows() or ())]
    current_session = _normalize_optional_text(get_current_session())
    attached_session_names = _load_attached_session_names(get_attached_session_names())
    filtered_rows = [
        row for row in rows if extract_session_name(row) in attached_session_names
    ]
    selection_items = dedupe_preserve_order([CURRENT_ITEM, *filtered_rows, CANCEL_ITEM])
    selection = detach_session_selector(selection_items, DETACH_HEADER, True)
    targets = _parse_selection_targets(selection, current_session)
    if not targets:
        return EXIT_SUCCESS

    if not _are_valid_session_names(targets):
        return EXIT_ERROR

    for target in targets:
        result = _normalize_mutation_result(detach_session(target), "detach_session")
        if result != EXIT_SUCCESS:
            return result

    return EXIT_SUCCESS


def _build_selection_items(
    rows: Sequence[str],
    current_session: str,
    *,
    include_current: bool,
) -> list[str]:
    if current_session:
        ordered_rows = _prioritize_current_session(rows, current_session)
    else:
        ordered_rows = [CURRENT_ITEM, *rows] if include_current else list(rows)

    numbered_rows = add_number_prefixes(ordered_rows)
    return [*numbered_rows, CANCEL_ITEM]


def _prioritize_current_session(rows: Sequence[str], current_session: str) -> list[str]:
    ordered_rows = list(rows)
    current_row = next(
        (row for row in ordered_rows if row.startswith(f"{current_session} @ ")),
        None,
    )
    if current_row is None:
        return ordered_rows

    return [current_row, *[row for row in ordered_rows if row != current_row]]


def _parse_selection_targets(selection: object | None, current_session: str) -> list[str]:
    return parse_targets(None if selection is None else str(selection), current_session)


def _normalize_optional_text(raw_value: object | None) -> str:
    if raw_value is None:
        return ""

    return str(raw_value)


def _load_attached_session_names(raw_value: object | None) -> set[str]:
    if raw_value is None:
        return set()

    if isinstance(raw_value, (str, bytes)):
        return {str(raw_value)}

    if not isinstance(raw_value, Iterable):
        raise TypeError("get_attached_session_names must return an iterable or None")

    return {str(name) for name in raw_value}


def _are_valid_session_names(targets: Sequence[str]) -> bool:
    for target in targets:
        try:
            validate_session_name(target)
        except ValueError:
            return False

    return True


def _normalize_mutation_result(result: object | None, label: str) -> int:
    if result is None or result is True:
        return EXIT_SUCCESS

    if result is False:
        return EXIT_ERROR

    if isinstance(result, int):
        return result

    raise TypeError(f"{label} must return an int, bool, or None")


def _require_callable(deps: object, attr_name: str) -> Callable[..., object]:
    value = getattr(deps, attr_name, None)
    if not callable(value):
        raise TypeError(f"Context deps must expose a callable {attr_name}")

    return value
