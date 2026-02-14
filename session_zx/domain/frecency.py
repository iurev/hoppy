"""Frecency scoring helpers."""


def bucket_frecency_weight(age_hours: float) -> int:
    """Return the score contribution for a selection age in hours."""
    if age_hours < 1:
        return 100
    if age_hours < 24:
        return 50
    if age_hours < 24 * 7:
        return 10
    return 1
