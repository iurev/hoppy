"""Filtering helpers."""


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
