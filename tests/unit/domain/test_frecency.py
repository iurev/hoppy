import pytest

from session_zx.domain.frecency import (
    bucket_frecency_weight,
    score_selection_timestamps,
)


@pytest.mark.parametrize(
    ("age_hours", "expected_weight"),
    [
        (-1.0, 100),
        (0.0, 100),
        (0.999, 100),
        (1.0, 50),
        (23.999, 50),
        (24.0, 10),
        (167.999, 10),
        (168.0, 1),
        (9999.0, 1),
    ],
)
def test_bucket_frecency_weight_returns_expected_bucket_weight(
    age_hours: float, expected_weight: int
) -> None:
    assert bucket_frecency_weight(age_hours) == expected_weight


def test_score_selection_timestamps_returns_zero_for_empty_list() -> None:
    assert score_selection_timestamps([], now_ms=1_000_000) == 0


def test_score_selection_timestamps_sums_weights_for_mixed_ages() -> None:
    now_ms = 10 * 60 * 60 * 1000
    timestamps_ms = [
        now_ms - 30 * 60 * 1000,
        now_ms - 5 * 60 * 60 * 1000,
        now_ms - 48 * 60 * 60 * 1000,
        now_ms - 10 * 24 * 60 * 60 * 1000,
    ]

    assert score_selection_timestamps(timestamps_ms, now_ms=now_ms) == 161
