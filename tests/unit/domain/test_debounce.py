from session_zx.domain.debounce import make_debounce_token


def test_make_debounce_token_formats_all_parts_in_order() -> None:
    assert make_debounce_token(1_700_000_000_123, 4242, "ab12cd") == (
        "1700000000123-4242-ab12cd"
    )


def test_make_debounce_token_preserves_non_alnum_suffix_content() -> None:
    assert make_debounce_token(10, 2, "x_y-z") == "10-2-x_y-z"
