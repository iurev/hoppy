import pytest

from session_zx.app.exit_codes import (
    EXIT_ERROR,
    EXIT_INTERRUPTED,
    EXIT_SUCCESS,
    NON_FATAL_FZF_EXIT_CODES,
    is_non_fatal_fzf_exit_code,
    normalize_exit_code,
)


def test_non_fatal_fzf_exit_codes_match_expected_values() -> None:
    assert NON_FATAL_FZF_EXIT_CODES == frozenset({0, 1, 130})


@pytest.mark.parametrize("code", [EXIT_SUCCESS, EXIT_ERROR, EXIT_INTERRUPTED])
def test_is_non_fatal_fzf_exit_code_accepts_known_codes(code: int) -> None:
    assert is_non_fatal_fzf_exit_code(code) is True


@pytest.mark.parametrize("code", [-1, 2, 255])
def test_is_non_fatal_fzf_exit_code_rejects_unknown_codes(code: int) -> None:
    assert is_non_fatal_fzf_exit_code(code) is False


def test_normalize_exit_code_returns_success_for_none() -> None:
    assert normalize_exit_code(None) == EXIT_SUCCESS


def test_normalize_exit_code_raises_for_non_int_types() -> None:
    with pytest.raises(TypeError, match="Exit code must be an int or None, got str"):
        normalize_exit_code("1")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (-1, EXIT_ERROR),
        (256, EXIT_ERROR),
        (0, 0),
        (42, 42),
        (255, 255),
    ],
)
def test_normalize_exit_code_handles_range_bounds(code: int, expected: int) -> None:
    assert normalize_exit_code(code) == expected

