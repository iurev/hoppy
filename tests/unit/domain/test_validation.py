import pytest

from session_zx.domain.validation import (
    validate_action,
    validate_fzf_options,
    validate_header,
    validate_session_name,
)


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


@pytest.mark.parametrize(
    "session_name",
    [
        "abc",
        "abc-123",
        "abc_def",
        "Name With Spaces",
        "Z",
        "0",
    ],
)
def test_validate_session_name_accepts_supported_values(session_name: str) -> None:
    validate_session_name(session_name)


def test_validate_session_name_rejects_non_string_value() -> None:
    with pytest.raises(ValueError, match="Session name must be a string, got int"):
        validate_session_name(123)  # type: ignore[arg-type]


def test_validate_session_name_rejects_empty_name() -> None:
    with pytest.raises(ValueError, match="Session name cannot be empty"):
        validate_session_name("")


def test_validate_session_name_rejects_too_long_name() -> None:
    too_long = "a" * 101
    with pytest.raises(
        ValueError, match=r"Session name exceeds max length of 100 \(got 101\)"
    ):
        validate_session_name(too_long)


@pytest.mark.parametrize(
    ("session_name", "error_message"),
    [
        ("bad:name", r"Session name cannot contain colons \(:\)"),
        ("bad.name", r"Session name cannot contain periods \(\.\)"),
        ("bad\nname", "Session name cannot contain newlines"),
        ("bad\rname", "Session name cannot contain newlines"),
        ("bad\0name", "Session name cannot contain null bytes"),
        ("bad\x1fname", "Session name cannot contain control characters"),
        ("bad@name", "Session name can only contain letters, numbers, underscore, hyphen, and spaces"),
    ],
)
def test_validate_session_name_rejects_forbidden_content(
    session_name: str, error_message: str
) -> None:
    with pytest.raises(ValueError, match=error_message):
        validate_session_name(session_name)


@pytest.mark.parametrize(
    "options",
    [
        "",
        "--ansi --layout=reverse",
        "--bind 'ctrl-n:down+accept'",
    ],
)
def test_validate_fzf_options_accepts_valid_strings(options: str) -> None:
    validate_fzf_options(options, "FZF_DEFAULT_OPTS")


def test_validate_fzf_options_rejects_non_string_value() -> None:
    with pytest.raises(ValueError, match="TMUX_FZF_RUN must be a string, got int"):
        validate_fzf_options(123, "TMUX_FZF_RUN")  # type: ignore[arg-type]


def test_validate_fzf_options_rejects_too_long_value() -> None:
    too_long = "x" * 10001
    with pytest.raises(
        ValueError, match=r"Built FZF_DEFAULT_OPTS exceeds max length of 10000 characters"
    ):
        validate_fzf_options(too_long, "Built FZF_DEFAULT_OPTS")


def test_validate_fzf_options_rejects_null_bytes() -> None:
    with pytest.raises(ValueError, match="TMUX_FZF_OPTIONS cannot contain null bytes"):
        validate_fzf_options("safe\0unsafe", "TMUX_FZF_OPTIONS")


@pytest.mark.parametrize("header", [None, "", "Select target session."])
def test_validate_header_accepts_none_and_strings(header: str | None) -> None:
    validate_header(header)


def test_validate_header_rejects_non_string_value() -> None:
    with pytest.raises(ValueError, match="Header must be a string, got int"):
        validate_header(123)  # type: ignore[arg-type]


def test_validate_header_rejects_too_long_value() -> None:
    with pytest.raises(ValueError, match="Header exceeds max length of 500 characters"):
        validate_header("x" * 501)


def test_validate_header_rejects_newlines() -> None:
    with pytest.raises(ValueError, match="Header cannot contain newlines"):
        validate_header("line1\nline2")
