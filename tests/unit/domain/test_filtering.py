import pytest

from session_zx.domain.filtering import (
    dedupe_preserve_order,
    is_path_in_worktree,
    normalize_worktree_path,
)


def test_dedupe_preserve_order_returns_empty_list_for_empty_input() -> None:
    assert dedupe_preserve_order([]) == []


def test_dedupe_preserve_order_removes_duplicates_and_preserves_first_seen_order() -> None:
    items = ["alpha", "beta", "alpha", "gamma", "beta", "delta"]

    assert dedupe_preserve_order(items) == ["alpha", "beta", "gamma", "delta"]


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("", ""),
        ("/repo/worktree", "/repo/worktree"),
        ("/repo/worktree///", "/repo/worktree"),
        ("/", ""),
    ],
)
def test_normalize_worktree_path_trims_trailing_slashes(path: str, expected: str) -> None:
    assert normalize_worktree_path(path) == expected


@pytest.mark.parametrize(
    ("pane_path", "worktree_path"),
    [
        ("/repo/main", "/repo/main"),
        ("/repo/main", "/repo/main///"),
    ],
)
def test_is_path_in_worktree_returns_true_for_exact_match(
    pane_path: str, worktree_path: str
) -> None:
    assert is_path_in_worktree(pane_path, worktree_path) is True


def test_is_path_in_worktree_returns_true_for_nested_path() -> None:
    assert is_path_in_worktree("/repo/main/pkg/subdir", "/repo/main") is True


def test_is_path_in_worktree_returns_false_for_sibling_path() -> None:
    assert is_path_in_worktree("/repo/main-other", "/repo/main") is False
