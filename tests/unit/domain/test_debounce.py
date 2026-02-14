from session_zx.domain.debounce import make_debounce_token, normalize_debounce_state


def test_make_debounce_token_formats_all_parts_in_order() -> None:
    assert make_debounce_token(1_700_000_000_123, 4242, "ab12cd") == (
        "1700000000123-4242-ab12cd"
    )


def test_make_debounce_token_preserves_non_alnum_suffix_content() -> None:
    assert make_debounce_token(10, 2, "x_y-z") == "10-2-x_y-z"


def test_normalize_debounce_state_returns_defaults_for_none() -> None:
    assert normalize_debounce_state(None) == {
        "lastWrite": 0,
        "lastTarget": None,
        "token": None,
    }


def test_normalize_debounce_state_coerces_last_write_and_keeps_strings() -> None:
    assert normalize_debounce_state(
        {"lastWrite": "123", "lastTarget": "dev", "token": "1700-10-abcd"}
    ) == {
        "lastWrite": 123.0,
        "lastTarget": "dev",
        "token": "1700-10-abcd",
    }


def test_normalize_debounce_state_resets_invalid_values() -> None:
    assert normalize_debounce_state(
        {"lastWrite": "bad", "lastTarget": 42, "token": object()}
    ) == {
        "lastWrite": 0,
        "lastTarget": None,
        "token": None,
    }


def test_normalize_debounce_state_resets_non_finite_numbers() -> None:
    assert normalize_debounce_state({"lastWrite": "NaN"}) == {
        "lastWrite": 0,
        "lastTarget": None,
        "token": None,
    }
