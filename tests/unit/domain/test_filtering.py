from session_zx.domain.filtering import dedupe_preserve_order


def test_dedupe_preserve_order_returns_empty_list_for_empty_input() -> None:
    assert dedupe_preserve_order([]) == []


def test_dedupe_preserve_order_removes_duplicates_and_preserves_first_seen_order() -> None:
    items = ["alpha", "beta", "alpha", "gamma", "beta", "delta"]

    assert dedupe_preserve_order(items) == ["alpha", "beta", "gamma", "delta"]
