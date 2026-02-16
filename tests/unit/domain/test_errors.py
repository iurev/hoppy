from session_zx.domain.errors import (
    ActionRoutingError,
    CommandExecutionError,
    SessionZxError,
    ValidationError,
)


def test_validation_error_is_typed_session_error() -> None:
    error = ValidationError("invalid session name")

    assert isinstance(error, SessionZxError)
    assert str(error) == "invalid session name"


def test_action_routing_error_includes_action_value() -> None:
    error = ActionRoutingError("popup-switch")

    assert error.action == "popup-switch"
    assert str(error) == "Unhandled action: popup-switch"


def test_command_execution_error_formats_message_with_all_details() -> None:
    error = CommandExecutionError(
        "command failed",
        command=["tmux", "list-sessions"],
        exit_code=127,
        stderr="not found",
    )

    assert error.command == ("tmux", "list-sessions")
    assert error.exit_code == 127
    assert error.stderr == "not found"
    assert (
        str(error)
        == "command failed (command=tmux list-sessions; exit_code=127; stderr=not found)"
    )


def test_command_execution_error_keeps_original_message_without_optional_details() -> None:
    error = CommandExecutionError("command failed")

    assert error.command == ()
    assert error.exit_code is None
    assert error.stderr is None
    assert str(error) == "command failed"
