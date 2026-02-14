import pytest

from session_zx.domain.frecency import bucket_frecency_weight


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
