"""Typed exceptions for domain and orchestration layers."""

from collections.abc import Sequence


class SessionZxError(Exception):
    """Base typed exception for session_zx."""


class ValidationError(SessionZxError):
    """Raised when user input fails domain validation."""


class ActionRoutingError(SessionZxError):
    """Raised when action routing cannot find a supported action."""

    def __init__(self, action: str) -> None:
        self.action = action
        super().__init__(f"Unhandled action: {action}")


class CommandExecutionError(SessionZxError):
    """Raised when an external process command fails."""

    def __init__(
        self,
        message: str,
        *,
        command: Sequence[str] | None = None,
        exit_code: int | None = None,
        stderr: str | None = None,
    ) -> None:
        self.command = tuple(command or ())
        self.exit_code = exit_code
        self.stderr = stderr

        details: list[str] = []
        if self.command:
            details.append(f"command={' '.join(self.command)}")
        if exit_code is not None:
            details.append(f"exit_code={exit_code}")
        if stderr:
            details.append(f"stderr={stderr}")

        if details:
            rendered_details = "; ".join(details)
            message = f"{message} ({rendered_details})"

        super().__init__(message)
