"""Unit tests for the tmux CLI adapter."""

from unittest.mock import MagicMock

import pytest

from session_zx.adapters.tmux_cli import TmuxCliAdapter
from session_zx.ports.process import ProcessPort


@pytest.fixture
def mock_process() -> MagicMock:
    return MagicMock(spec=ProcessPort)


@pytest.fixture
def adapter(mock_process: MagicMock) -> TmuxCliAdapter:
    return TmuxCliAdapter(mock_process)


def test_list_session_rows_parses_tmux_output(
    adapter: TmuxCliAdapter, mock_process: MagicMock
) -> None:
    mock_process.run.return_value = (0, "s1 @ 1 windows\ns2 @ 2 windows\n", "")

    rows = adapter.list_session_rows()

    assert rows == ["s1 @ 1 windows", "s2 @ 2 windows"]
    mock_process.run.assert_called_once_with(
        ["tmux", "list-sessions", "-F", "#S @ #{session_windows} windows"]
    )


def test_list_session_rows_returns_empty_on_failure(
    adapter: TmuxCliAdapter, mock_process: MagicMock
) -> None:
    mock_process.run.return_value = (1, "", "error")

    rows = adapter.list_session_rows()

    assert rows == []


def test_get_current_session_returns_stripped_stdout(
    adapter: TmuxCliAdapter, mock_process: MagicMock
) -> None:
    mock_process.run.return_value = (0, "current_sess\n", "")

    name = adapter.get_current_session()

    assert name == "current_sess"
    mock_process.run.assert_called_once_with(["tmux", "display-message", "-p", "#S"])


def test_get_current_session_returns_none_on_failure(
    adapter: TmuxCliAdapter, mock_process: MagicMock
) -> None:
    mock_process.run.return_value = (1, "", "error")

    name = adapter.get_current_session()

    assert name is None


def test_get_attached_session_names_filters_attached(
    adapter: TmuxCliAdapter, mock_process: MagicMock
) -> None:
    mock_process.run.return_value = (0, "s1 1\ns2 0\ns3 2\n", "")

    attached = adapter.get_attached_session_names()

    assert attached == ["s1", "s3"]


def test_get_attached_session_names_returns_empty_on_failure(
    adapter: TmuxCliAdapter, mock_process: MagicMock
) -> None:
    mock_process.run.return_value = (1, "", "error")

    attached = adapter.get_attached_session_names()

    assert attached == []


def test_create_session_returns_true_on_success(
    adapter: TmuxCliAdapter, mock_process: MagicMock
) -> None:
    mock_process.run.return_value = (0, "", "")

    result = adapter.create_session("new_sess")

    assert result is True
    mock_process.run.assert_called_once_with(["tmux", "new-session", "-d", "-s", "new_sess"])


def test_switch_client_returns_true_on_success(
    adapter: TmuxCliAdapter, mock_process: MagicMock
) -> None:
    mock_process.run.return_value = (0, "", "")

    result = adapter.switch_client("target")

    assert result is True
    mock_process.run.assert_called_once_with(["tmux", "switch-client", "-t", "target"])


def test_rename_session_returns_true_on_success(
    adapter: TmuxCliAdapter, mock_process: MagicMock
) -> None:
    mock_process.run.return_value = (0, "", "")

    result = adapter.rename_session("old", "new")

    assert result is True
    mock_process.run.assert_called_once_with(
        ["tmux", "rename-session", "-t", "old", "new"]
    )


def test_kill_session_returns_true_on_success(
    adapter: TmuxCliAdapter, mock_process: MagicMock
) -> None:
    mock_process.run.return_value = (0, "", "")

    result = adapter.kill_session("target")

    assert result is True
    mock_process.run.assert_called_once_with(["tmux", "kill-session", "-t", "target"])


def test_detach_session_returns_true_on_success(
    adapter: TmuxCliAdapter, mock_process: MagicMock
) -> None:
    mock_process.run.return_value = (0, "", "")

    result = adapter.detach_session("target")

    assert result is True
    mock_process.run.assert_called_once_with(["tmux", "detach-client", "-s", "target"])
