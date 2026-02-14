import pytest

from session_zx.domain.frecency import (
    bucket_frecency_weight,
    score_selection_timestamps,
    sort_rows_by_frecency,
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


def test_sort_rows_by_frecency_orders_rows_by_descending_score() -> None:
    now_ms = 10 * 24 * 60 * 60 * 1000
    rows = [
        "alpha @ 1 windows",
        "beta @ 2 windows",
        "gamma @ 3 windows",
        "delta @ 4 windows",
    ]
    payload = {
        "selections": {
            "alpha": {"selectedAt": [now_ms - 30 * 60 * 1000]},
            "beta": {"selectedAt": [now_ms - 2 * 24 * 60 * 60 * 1000]},
            "delta": {
                "selectedAt": [
                    now_ms - 20 * 60 * 1000,
                    now_ms - 3 * 60 * 60 * 1000,
                ]
            },
        }
    }

    assert sort_rows_by_frecency(rows, payload, now_ms=now_ms) == [
        "delta @ 4 windows",
        "alpha @ 1 windows",
        "beta @ 2 windows",
        "gamma @ 3 windows",
    ]


def test_sort_rows_by_frecency_preserves_order_for_score_ties() -> None:
    now_ms = 10 * 24 * 60 * 60 * 1000
    rows = [
        "first @ 1 windows",
        "second @ 1 windows",
        "third @ 1 windows",
    ]
    payload = {
        "selections": {
            "first": {"selectedAt": [now_ms - 3 * 24 * 60 * 60 * 1000]},
            "second": {"selectedAt": [now_ms - 2 * 24 * 60 * 60 * 1000]},
            "third": {"selectedAt": [now_ms - 20 * 24 * 60 * 60 * 1000]},
        }
    }

    assert sort_rows_by_frecency(rows, payload, now_ms=now_ms) == rows


def test_sort_rows_by_frecency_treats_invalid_selection_mapping_as_zero() -> None:
    rows = ["one @ 1 windows", "two @ 1 windows"]

    assert sort_rows_by_frecency(rows, {"selections": []}, now_ms=1_000) == rows
