"""Filtering helpers."""

from session_zx.domain.parsing import extract_session_name


def dedupe_preserve_order(items: list[str]) -> list[str]:
    """Return a list with duplicate items removed, preserving first-seen order."""
    seen: set[str] = set()
    deduped_items: list[str] = []

    for item in items:
        if item in seen:
            continue

        seen.add(item)
        deduped_items.append(item)

    return deduped_items


def normalize_worktree_path(path: str) -> str:
    """Normalize a git worktree path by trimming trailing slashes."""
    return path.rstrip("/")


def is_path_in_worktree(pane_path: str, worktree_path: str) -> bool:
    """Return whether a pane path is exactly in or nested under a worktree."""
    normalized_worktree = normalize_worktree_path(worktree_path)
    return pane_path == normalized_worktree or pane_path.startswith(f"{normalized_worktree}/")


def filter_sessions_by_worktrees(
    rows: list[str],
    worktrees: list[str],
    pane_paths: dict[str, set[str]],
) -> list[str]:
    """Return session rows that have at least one pane path inside any worktree."""
    normalized_worktrees = [normalize_worktree_path(path) for path in worktrees]
    return [
        row
        for row in rows
        if any(
            is_path_in_worktree(pane_path, worktree_path)
            for pane_path in pane_paths.get(extract_session_name(row), set())
            for worktree_path in normalized_worktrees
        )
    ]
