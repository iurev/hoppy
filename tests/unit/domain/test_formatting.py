from session_zx.domain.formatting import normalize_session_row, normalize_session_rows


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
