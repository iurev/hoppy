"""Domain value objects used across CLI, ports, and use cases."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class ParsedArgs:
    """Parsed positional CLI values."""

    action: str | None
    argv: tuple[str, ...]

    @classmethod
    def from_sequence(cls, argv: Sequence[object]) -> "ParsedArgs":
        """Build parsed args from raw argv-like values."""
        if not argv:
            return cls(action=None, argv=())

        return cls(action=str(argv[0]), argv=tuple(str(value) for value in argv[1:]))


@dataclass(frozen=True, slots=True)
class CommandResult:
    """Standardized subprocess result payload."""

    code: int
    stdout: str = ""
    stderr: str = ""

    def ok(self) -> bool:
        """Return whether command exited with success status."""
        return self.code == 0


@dataclass(frozen=True, slots=True)
class FzfOptions:
    """Structured options used to invoke fzf."""

    header: str | None = None
    prompt: str | None = None
    multi: bool = False
    extra_args: tuple[str, ...] = ()

    def as_argv(self) -> list[str]:
        """Convert options to argv fragments in deterministic order."""
        args: list[str] = []

        if self.header:
            args.extend(["--header", self.header])

        if self.prompt:
            args.extend(["--prompt", self.prompt])

        if self.multi:
            args.append("--multi")

        if self.extra_args:
            args.extend(self.extra_args)

        return args


@dataclass(frozen=True, slots=True)
class FzfResult:
    """Result of a single fzf invocation."""

    exit_code: int
    selection: str = ""
    error: str = ""

    def is_cancelled(self) -> bool:
        """Return whether fzf ended via expected cancel pathways."""
        return self.exit_code in {1, 130}

    def is_error(self) -> bool:
        """Return whether fzf ended with an unexpected exit code."""
        return self.exit_code not in {0, 1, 130}


@dataclass(frozen=True, slots=True)
class DebounceState:
    """Persisted debounce guard state."""

    last_write: float = 0
    last_target: str | None = None
    token: str | None = None

    @classmethod
    def from_mapping(cls, raw_state: Mapping[str, object] | None) -> "DebounceState":
        """Normalize persisted state into a safe dataclass representation."""
        state = raw_state if isinstance(raw_state, Mapping) else {}
        last_write = _parse_last_write(state.get("lastWrite", 0))
        last_target = _coerce_optional_string(state.get("lastTarget"))
        token = _coerce_optional_string(state.get("token"))
        return cls(last_write=last_write, last_target=last_target, token=token)

    def as_mapping(self) -> dict[str, object]:
        """Serialize the state using storage-compatible key names."""
        return {
            "lastWrite": self.last_write,
            "lastTarget": self.last_target,
            "token": self.token,
        }


def _parse_last_write(raw_value: object) -> float:
    try:
        last_write = float(raw_value)
    except (TypeError, ValueError):
        return 0

    return last_write if math.isfinite(last_write) else 0


def _coerce_optional_string(raw_value: object) -> str | None:
    if isinstance(raw_value, str):
        return raw_value

    return None
