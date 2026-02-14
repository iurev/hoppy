"""Frecency scoring helpers."""

from session_zx.domain.parsing import extract_session_name


def bucket_frecency_weight(age_hours: float) -> int:
    """Return the score contribution for a selection age in hours."""
    if age_hours < 1:
        return 100
    if age_hours < 24:
        return 50
    if age_hours < 24 * 7:
        return 10
    return 1


def score_selection_timestamps(timestamps_ms: list[int], now_ms: int) -> int:
    """Return the combined frecency score for selection timestamps."""
    if not timestamps_ms:
        return 0
    return sum(
        bucket_frecency_weight((now_ms - timestamp_ms) / (1000 * 60 * 60))
        for timestamp_ms in timestamps_ms
    )


def sort_rows_by_frecency(
    rows: list[str], frecency_payload: dict[str, object], now_ms: int
) -> list[str]:
    """Return rows sorted by descending frecency score."""
    selections = frecency_payload.get("selections", {})
    if not isinstance(selections, dict):
        selections = {}

    return sorted(
        rows,
        key=lambda row: score_selection_timestamps(
            (
                selection_data.get("selectedAt", [])
                if isinstance(selection_data := selections.get(extract_session_name(row)), dict)
                else []
            ),
            now_ms=now_ms,
        ),
        reverse=True,
    )
