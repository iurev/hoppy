"""Application context construction helpers."""

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol


class EnvPort(Protocol):
    """Port contract for loading environment values from candidate files."""

    def load_first_existing(self, paths: list[Path]) -> Mapping[str, str]:
        """Return values loaded from the first existing env source."""


@dataclass(frozen=True, slots=True)
class AppContext:
    """Immutable runtime context for CLI dispatch."""

    action: str | None
    argv: tuple[str, ...]
    env: dict[str, str]
    deps: object


def load_runtime_env(env_port: EnvPort, candidate_paths: list[Path]) -> dict[str, str]:
    """Load environment from the first available candidate path."""
    loaded = env_port.load_first_existing(candidate_paths)
    if not loaded:
        return {}

    return {str(key): str(value) for key, value in loaded.items()}


def apply_env_defaults(env: Mapping[str, str], preview_text: str) -> dict[str, str]:
    """Return a copy of env with parity defaults applied."""
    resolved_env = {str(key): str(value) for key, value in env.items()}

    if not resolved_env.get("TMUX_FZF_BIN"):
        resolved_env["TMUX_FZF_BIN"] = "fzf"

    if not resolved_env.get("TMUX_FZF_OPTIONS"):
        resolved_env["TMUX_FZF_OPTIONS"] = ""

    if not resolved_env.get("FZF_DEFAULT_OPTS"):
        resolved_env["FZF_DEFAULT_OPTS"] = ""

    if not resolved_env.get("TMUX_FZF_PREVIEW_OPTIONS"):
        resolved_env["KAOMOJI_PREVIEW_TEXT"] = preview_text

    return resolved_env


def build_app_context(
    parsed_args: tuple[str | None, list[str]],
    deps: object,
    env: Mapping[str, str],
) -> AppContext:
    """Build an immutable application context from parsed args and dependencies."""
    action, argv = parsed_args
    return AppContext(action=action, argv=tuple(argv), env=dict(env), deps=deps)
