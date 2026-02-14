import pytest

from session_zx.domain.filtering import (
    dedupe_preserve_order,
    filter_capital_sessions,
    filter_sessions_by_worktrees,
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


def test_filter_sessions_by_worktrees_returns_only_sessions_with_matching_panes() -> None:
    rows = ["alpha @ 1 windows", "beta @ 2 windows", "gamma @ 3 windows"]
    worktrees = ["/repo/main///", "/repo/other"]
    pane_paths = {
        "alpha": {"/repo/main", "/tmp/elsewhere"},
        "beta": {"/unrelated/path"},
        "gamma": {"/repo/other/pkg"},
    }

    assert filter_sessions_by_worktrees(rows, worktrees, pane_paths) == [
        "alpha @ 1 windows",
        "gamma @ 3 windows",
    ]


def test_filter_sessions_by_worktrees_excludes_sessions_without_pane_paths() -> None:
    rows = ["alpha @ 1 windows", "beta @ 2 windows"]
    worktrees = ["/repo/main"]
    pane_paths = {"alpha": set()}

    assert filter_sessions_by_worktrees(rows, worktrees, pane_paths) == []


def test_filter_capital_sessions_returns_empty_list_for_empty_rows() -> None:
    assert filter_capital_sessions([]) == []


def test_filter_capital_sessions_keeps_only_matching_names() -> None:
    rows = [
        "ABC @ 1 windows",
        "ALPHA_2-OK @ 1 windows",
        "UPPER CASE @ 1 windows",
        "alpha @ 1 windows",
        "MiXeD @ 1 windows",
        "12345 @ 1 windows",
        "WITH.DOT @ 1 windows",
    ]

    assert filter_capital_sessions(rows) == [
        "ABC @ 1 windows",
        "ALPHA_2-OK @ 1 windows",
        "UPPER CASE @ 1 windows",
    ]


def test_filter_capital_sessions_uses_extracted_name_from_prefixed_rows() -> None:
    rows = ["[1] MAIN @ 2 windows", "[2] dev @ 3 windows"]

    assert filter_capital_sessions(rows) == ["[1] MAIN @ 2 windows"]
