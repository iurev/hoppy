"""Process execution adapter using the standard library subprocess module."""

from collections.abc import Mapping, Sequence
import os
import subprocess

from session_zx.ports.process import ProcessPort


class SubprocessAdapter(ProcessPort):
    """Adapter that executes commands via subprocess.run and Popen."""

    def run(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
        capture_output: bool = True,
    ) -> tuple[int, str, str]:
        """Execute command synchronously."""
        try:
            result = subprocess.run(
                [str(arg) for arg in argv],
                env=env,
                capture_output=capture_output,
                text=True,
                check=False,
            )
            return result.returncode, result.stdout, result.stderr
        except FileNotFoundError:
            return 127, "", f"Command not found: {argv[0]}"
        except Exception as e:
            return 1, "", str(e)

    def spawn_detached(
        self,
        argv: Sequence[str],
        *,
        env: Mapping[str, str] | None = None,
    ) -> bool:
        """Spawn command in background without waiting."""
        try:
            # Use os.setsid to create a new process group for detachment
            # This is closer to how zx/shell scripts handle backgrounding
            subprocess.Popen(
                [str(arg) for arg in argv],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except Exception:
            return False
