import pytest

from session_zx.domain.validation import validate_action


@pytest.mark.parametrize(
    "action",
    [
        "switch",
        "new",
        "rename",
        "detach",
        "kill",
        "kill-single",
        "reload-sessions",
        "popup-switch",
        "worktree-switch",
        "popup-worktree-switch",
        "capital-switch",
        "popup-capital-switch",
    ],
)
def test_validate_action_accepts_supported_actions(action: str) -> None:
    validate_action(action)


def test_validate_action_rejects_non_string_value() -> None:
    with pytest.raises(ValueError, match="Action must be a string, got int"):
        validate_action(123)  # type: ignore[arg-type]


def test_validate_action_rejects_unsupported_action() -> None:
    with pytest.raises(ValueError, match=r"Invalid action: nope\. Must be one of: "):
        validate_action("nope")
