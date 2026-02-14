import pytest

from session_zx.domain.parsing import (
    ensure_trailing_newline,
    extract_session_name,
    parse_targets,
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


def test_parse_targets_returns_empty_list_for_empty_selection() -> None:
    assert parse_targets("", "current") == []


def test_parse_targets_returns_empty_list_when_cancel_present() -> None:
    selection = "alpha @ 2 windows\n[cancel]"

    assert parse_targets(selection, "current") == []


def test_parse_targets_replaces_current_marker_and_extracts_names() -> None:
    selection = "[current]\n[2] alpha @ 3 windows\nplain-session"

    assert parse_targets(selection, "base") == ["base", "alpha", "plain-session"]


def test_parse_targets_filters_empty_targets_after_current_replacement() -> None:
    assert parse_targets("[current]", "") == []
