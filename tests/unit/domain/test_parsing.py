import pytest

from session_zx.domain.parsing import parse_lines


@pytest.mark.parametrize("value", [None, ""])
def test_parse_lines_returns_empty_list_for_empty_input(value: str | None) -> None:
    assert parse_lines(value) == []


def test_parse_lines_splits_trims_and_drops_empty_lines() -> None:
    raw = "  alpha  \n\n beta\t\n   \n gamma  "

    assert parse_lines(raw) == ["alpha", "beta", "gamma"]

