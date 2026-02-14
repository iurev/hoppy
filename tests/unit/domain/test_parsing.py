import pytest

from session_zx.domain.parsing import (
    ensure_trailing_newline,
    extract_session_name,
    parse_lines,
)


@pytest.mark.parametrize("value", [None, ""])
def test_parse_lines_returns_empty_list_for_empty_input(value: str | None) -> None:
    assert parse_lines(value) == []


def test_parse_lines_splits_trims_and_drops_empty_lines() -> None:
    raw = "  alpha  \n\n beta\t\n   \n gamma  "

    assert parse_lines(raw) == ["alpha", "beta", "gamma"]


def test_ensure_trailing_newline_adds_newline_when_missing() -> None:
    assert ensure_trailing_newline("alpha") == "alpha\n"


def test_ensure_trailing_newline_keeps_existing_trailing_newline() -> None:
    assert ensure_trailing_newline("alpha\n") == "alpha\n"


def test_extract_session_name_returns_prefixless_name_with_delimiter() -> None:
    assert extract_session_name("[2] alpha @ 3 windows") == "alpha"


def test_extract_session_name_returns_input_when_delimiter_missing() -> None:
    assert extract_session_name("plain-session") == "plain-session"
