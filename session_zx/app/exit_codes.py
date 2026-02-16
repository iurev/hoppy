"""Canonical exit code helpers for the Python CLI."""

EXIT_SUCCESS = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_INTERRUPTED = 130

NON_FATAL_FZF_EXIT_CODES = frozenset(
    {
        EXIT_SUCCESS,
        EXIT_ERROR,
        EXIT_INTERRUPTED,
    }
)


def is_non_fatal_fzf_exit_code(code: int) -> bool:
    """Return True when an fzf exit code should be treated as non-fatal."""
    return code in NON_FATAL_FZF_EXIT_CODES


def normalize_exit_code(code: int | None) -> int:
    """Normalize an optional process exit code to a valid shell code."""
    if code is None:
        return EXIT_SUCCESS

    if not isinstance(code, int):
        raise TypeError(f"Exit code must be an int or None, got {type(code).__name__}")

    if code < 0 or code > 255:
        return EXIT_ERROR

    return code

