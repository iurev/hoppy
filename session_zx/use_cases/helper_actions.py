"""Helper-action use cases for fzf bindings and debounce switching."""

from collections.abc import Callable, Mapping, Sequence
import os
from typing import Any, Final, cast

from session_zx.app.context import AppContext
from session_zx.app.exit_codes import EXIT_SUCCESS
from session_zx.domain.debounce import (
    make_debounce_token,
    normalize_debounce_state,
    should_execute_delayed_switch,
)
from session_zx.domain.formatting import add_number_prefixes
from session_zx.domain.parsing import ensure_trailing_newline, extract_session_name

DEFAULT_SESSION_SWITCH_DEBOUNCE_MS: Final[int] = 300
TOKEN_SUFFIX_LENGTH: Final[int] = 8


def run_reload_sessions(ctx: AppContext) -> int:
    """Output the current session list in fzf-reload format."""
    list_session_rows = cast(
        Callable[[], Sequence[object] | None],
        _require_callable(ctx.deps, "list_session_rows"),
    )
    write_stdout = cast(
        Callable[[str], object | None],
        _require_callable(ctx.deps, "write_stdout"),
    )

    rows = [str(row) for row in (list_session_rows() or ())]
    payload = ensure_trailing_newline("\n".join(add_number_prefixes(rows)))
    write_stdout(payload)
    return EXIT_SUCCESS


def run_kill_single_from_line(ctx: AppContext, line: object | None = None) -> int:
    """Best-effort single-session kill for fzf delete binding."""
    session_name = extract_session_name(_resolve_helper_argument(ctx, line))
    if not session_name:
        return EXIT_SUCCESS

    kill_session = cast(
        Callable[[str], object | None],
        _require_callable(ctx.deps, "kill_session"),
    )
    try:
        kill_session(session_name)
    except Exception:
        return EXIT_SUCCESS

    return EXIT_SUCCESS


def run_switch_from_line(ctx: AppContext, line: object | None = None) -> int:
    """Schedule a debounced switch from the currently highlighted fzf line."""
    session_name = extract_session_name(_resolve_helper_argument(ctx, line)).strip()
    if not session_name or session_name == "[cancel]":
        return EXIT_SUCCESS

    try:
        _schedule_switch(ctx, session_name)
    except Exception:
        return EXIT_SUCCESS

    return EXIT_SUCCESS


def run_delayed_switch(ctx: AppContext, token: object | None = None) -> int:
    """Run the delayed switch helper that applies debounce-token guards."""
    debounce_token = _resolve_helper_argument(ctx, token).strip()
    if not debounce_token:
        return EXIT_SUCCESS

    try:
        sleep_ms = cast(
            Callable[[int], object | None],
            _require_callable(ctx.deps, "sleep_ms"),
        )
        sleep_ms(_resolve_debounce_delay_ms(ctx.env))

        read_debounce_state = cast(
            Callable[[], Mapping[str, Any] | None],
            _require_callable(ctx.deps, "read_debounce_state"),
        )
        raw_state = read_debounce_state()
        state = normalize_debounce_state(raw_state if isinstance(raw_state, Mapping) else None)
        if not should_execute_delayed_switch(debounce_token, state):
            return EXIT_SUCCESS

        target = str(state.get("lastTarget") or "").strip()
        switch_client = cast(
            Callable[[str], object | None],
            _require_callable(ctx.deps, "switch_client"),
        )
        if not _did_switch_succeed(switch_client(target)):
            return EXIT_SUCCESS

        write_debounce_state = cast(
            Callable[[dict[str, object]], object | None],
            _require_callable(ctx.deps, "write_debounce_state"),
        )
        _write_debounce_state(
            write_debounce_state,
            last_write=_load_now_ms(ctx.deps),
            last_target=target,
            token=None,
        )
    except Exception:
        return EXIT_SUCCESS

    return EXIT_SUCCESS


def _schedule_switch(ctx: AppContext, session_name: str) -> None:
    now_ms = _load_now_ms(ctx.deps)
    random_suffix = cast(
        Callable[[int], object],
        _require_callable(ctx.deps, "random_suffix"),
    )
    token = make_debounce_token(
        now_ms=now_ms,
        pid=_resolve_process_id(ctx.deps),
        suffix=str(random_suffix(TOKEN_SUFFIX_LENGTH)),
    )

    write_debounce_state = cast(
        Callable[[dict[str, object]], object | None],
        _require_callable(ctx.deps, "write_debounce_state"),
    )
    if _write_debounce_state(
        write_debounce_state,
        last_write=now_ms,
        last_target=session_name,
        token=token,
    ):
        spawn_delayed_switch = cast(
            Callable[[str], object | None],
            _require_callable(ctx.deps, "spawn_delayed_switch"),
        )
        if spawn_delayed_switch(token) is not False:
            return

    _fallback_immediate_switch(ctx, session_name)


def _fallback_immediate_switch(ctx: AppContext, session_name: str) -> None:
    switch_client = cast(
        Callable[[str], object | None],
        _require_callable(ctx.deps, "switch_client"),
    )
    if not _did_switch_succeed(switch_client(session_name)):
        return

    write_debounce_state = cast(
        Callable[[dict[str, object]], object | None],
        _require_callable(ctx.deps, "write_debounce_state"),
    )
    _write_debounce_state(
        write_debounce_state,
        last_write=_load_now_ms(ctx.deps),
        last_target=session_name,
        token=None,
    )


def _did_switch_succeed(result: object | None) -> bool:
    return result is not False


def _write_debounce_state(
    write_debounce_state: Callable[[dict[str, object]], object | None],
    *,
    last_write: int,
    last_target: str,
    token: str | None,
) -> bool:
    payload: dict[str, object] = {
        "lastWrite": last_write,
        "lastTarget": last_target,
        "token": token,
    }
    return bool(write_debounce_state(payload))


def _load_now_ms(deps: object) -> int:
    now_ms = cast(Callable[[], object], _require_callable(deps, "now_ms"))
    try:
        return int(now_ms())
    except (TypeError, ValueError):
        return 0


def _resolve_process_id(deps: object) -> int:
    raw_pid = getattr(deps, "process_id", os.getpid())
    try:
        return int(raw_pid)
    except (TypeError, ValueError) as exc:
        raise TypeError("process_id must be int-compatible") from exc


def _resolve_debounce_delay_ms(env: Mapping[str, str]) -> int:
    raw_value = env.get("SESSION_SWITCH_DEBOUNCE_MS")
    if raw_value is None:
        return DEFAULT_SESSION_SWITCH_DEBOUNCE_MS

    try:
        parsed = int(raw_value)
    except (TypeError, ValueError):
        return DEFAULT_SESSION_SWITCH_DEBOUNCE_MS

    return DEFAULT_SESSION_SWITCH_DEBOUNCE_MS if parsed == 0 else parsed


def _resolve_helper_argument(ctx: AppContext, value: object | None) -> str:
    if value is not None:
        return str(value)

    if not ctx.argv:
        return ""

    return str(ctx.argv[0])


def _require_callable(deps: object, attr_name: str) -> Callable[..., object]:
    value = getattr(deps, attr_name, None)
    if not callable(value):
        raise TypeError(f"Context deps must expose a callable {attr_name}")

    return value
