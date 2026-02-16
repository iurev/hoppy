"""Unit tests for the subprocess adapter."""

from unittest.mock import MagicMock, patch
import subprocess

import pytest

from session_zx.adapters.process_subprocess import SubprocessAdapter


def test_run_executes_subprocess_run_and_returns_results() -> None:
    adapter = SubprocessAdapter()
    mock_result = MagicMock(spec=subprocess.CompletedProcess)
    mock_result.returncode = 0
    mock_result.stdout = "output\n"
    mock_result.stderr = ""

    with patch("subprocess.run", return_value=mock_result) as mock_run:
        code, stdout, stderr = adapter.run(["ls", "-l"], env={"K": "V"})

        assert code == 0
        assert stdout == "output\n"
        assert stderr == ""
        mock_run.assert_called_once_with(
            ["ls", "-l"],
            env={"K": "V"},
            capture_output=True,
            text=True,
            check=False,
        )


def test_run_handles_file_not_found_error() -> None:
    adapter = SubprocessAdapter()

    with patch("subprocess.run", side_effect=FileNotFoundError):
        code, stdout, stderr = adapter.run(["nonexistent"])

        assert code == 127
        assert stdout == ""
        assert "Command not found" in stderr


def test_run_handles_generic_exception() -> None:
    adapter = SubprocessAdapter()

    with patch("subprocess.run", side_effect=RuntimeError("boom")):
        code, stdout, stderr = adapter.run(["ls"])

        assert code == 1
        assert stdout == ""
        assert stderr == "boom"


def test_spawn_detached_uses_popen_with_start_new_session() -> None:
    adapter = SubprocessAdapter()

    with patch("subprocess.Popen") as mock_popen:
        result = adapter.spawn_detached(["sleep", "10"], env={"E": "V"})

        assert result is True
        mock_popen.assert_called_once_with(
            ["sleep", "10"],
            env={"E": "V"},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )


def test_spawn_detached_returns_false_on_exception() -> None:
    adapter = SubprocessAdapter()

    with patch("subprocess.Popen", side_effect=RuntimeError):
        result = adapter.spawn_detached(["bad"])

        assert result is False
