from session_zx.domain.formatting import (
    add_number_prefixes,
    normalize_session_row,
    normalize_session_rows,
)


def test_normalize_session_row_trims_plain_row_without_delimiter() -> None:
    assert normalize_session_row("  plain-session  ") == "plain-session"


def test_normalize_session_row_normalizes_spacing_around_delimiter() -> None:
    row = "ADC  @  3 windows"

    assert normalize_session_row(row) == "ADC @ 3 windows"


def test_normalize_session_row_normalizes_all_delimiter_segments() -> None:
    row = "A @ 1 @ tail"

    assert normalize_session_row(row) == "A @ 1 @ tail"


def test_normalize_session_rows_returns_empty_list_for_empty_input() -> None:
    assert normalize_session_rows([]) == []


def test_normalize_session_rows_normalizes_each_row_in_order() -> None:
    rows = ["  plain  ", " ADC  @  3 windows ", "A @ 1 @ tail"]

    assert normalize_session_rows(rows) == ["plain", "ADC @ 3 windows", "A @ 1 @ tail"]


def test_add_number_prefixes_returns_empty_list_for_empty_input() -> None:
    assert add_number_prefixes([]) == []


def test_add_number_prefixes_numbers_non_special_rows_up_to_default_limit() -> None:
    rows = [f"session-{idx}" for idx in range(1, 11)]

    assert add_number_prefixes(rows) == [
        "[1] session-1",
        "[2] session-2",
        "[3] session-3",
        "[4] session-4",
        "[5] session-5",
        "[6] session-6",
        "[7] session-7",
        "[8] session-8",
        "[9] session-9",
        "session-10",
    ]


def test_add_number_prefixes_skips_special_rows_without_consuming_number_slots() -> None:
    rows = ["[current]", "alpha", "[cancel]", "beta"]

    assert add_number_prefixes(rows) == ["[current]", "[1] alpha", "[cancel]", "[2] beta"]


def test_add_number_prefixes_respects_custom_limit() -> None:
    rows = ["alpha", "beta", "gamma"]

    assert add_number_prefixes(rows, limit=0) == ["alpha", "beta", "gamma"]
