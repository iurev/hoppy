from dataclasses import FrozenInstanceError

import pytest

from session_zx.domain.models import (
    CommandResult,
    DebounceState,
    FzfOptions,
    FzfResult,
    ParsedArgs,
)


def test_parsed_args_from_sequence_returns_empty_values_for_empty_input() -> None:
    parsed = ParsedArgs.from_sequence([])

    assert parsed == ParsedArgs(action=None, argv=())


def test_parsed_args_from_sequence_normalizes_action_and_argv_to_strings() -> None:
    parsed = ParsedArgs.from_sequence(["switch", 7, False])

    assert parsed == ParsedArgs(action="switch", argv=("7", "False"))


def test_parsed_args_is_frozen() -> None:
    parsed = ParsedArgs(action="switch", argv=("a",))

    with pytest.raises(FrozenInstanceError):
        parsed.action = "rename"


def test_command_result_ok_for_success_and_failure() -> None:
    assert CommandResult(code=0).ok() is True
    assert CommandResult(code=9).ok() is False


def test_fzf_options_as_argv_returns_empty_for_default_values() -> None:
    assert FzfOptions().as_argv() == []


def test_fzf_options_as_argv_emits_all_configured_flags_in_order() -> None:
    options = FzfOptions(
        header="SESSIONS",
        prompt="Session> ",
        multi=True,
        extra_args=("--ansi", "--no-sort"),
    )

    assert options.as_argv() == [
        "--header",
        "SESSIONS",
        "--prompt",
        "Session> ",
        "--multi",
        "--ansi",
        "--no-sort",
    ]


@pytest.mark.parametrize(
    ("exit_code", "expected"),
    [
        (1, True),
        (130, True),
        (0, False),
        (2, False),
    ],
)
def test_fzf_result_is_cancelled(exit_code: int, expected: bool) -> None:
    assert FzfResult(exit_code=exit_code).is_cancelled() is expected


@pytest.mark.parametrize(
    ("exit_code", "expected"),
    [
        (0, False),
        (1, False),
        (130, False),
        (2, True),
    ],
)
def test_fzf_result_is_error(exit_code: int, expected: bool) -> None:
    assert FzfResult(exit_code=exit_code).is_error() is expected


def test_debounce_state_from_mapping_defaults_when_none_or_non_mapping_input() -> None:
    assert DebounceState.from_mapping(None) == DebounceState()
    assert DebounceState.from_mapping("bad") == DebounceState()


def test_debounce_state_from_mapping_normalizes_finite_last_write_and_string_fields() -> None:
    state = DebounceState.from_mapping(
        {
            "lastWrite": "10.5",
            "lastTarget": "alpha",
            "token": "tok",
        }
    )

    assert state == DebounceState(last_write=10.5, last_target="alpha", token="tok")


@pytest.mark.parametrize("raw_last_write", ["bad", float("inf"), float("nan")])
def test_debounce_state_from_mapping_falls_back_to_zero_for_invalid_last_write(
    raw_last_write: object,
) -> None:
    state = DebounceState.from_mapping({"lastWrite": raw_last_write})

    assert state.last_write == 0


def test_debounce_state_from_mapping_drops_non_string_target_and_token() -> None:
    state = DebounceState.from_mapping({"lastTarget": 42, "token": True})

    assert state.last_target is None
    assert state.token is None


def test_debounce_state_as_mapping_uses_storage_keys() -> None:
    state = DebounceState(last_write=12.0, last_target="beta", token="t-1")

    assert state.as_mapping() == {
        "lastWrite": 12.0,
        "lastTarget": "beta",
        "token": "t-1",
    }
