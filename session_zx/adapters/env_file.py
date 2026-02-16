"""Environment loading adapter using the first available env file."""

from collections.abc import Mapping
from pathlib import Path
import os
import subprocess

from session_zx.app.context import EnvPort
from session_zx.domain.parsing import parse_env_output


class EnvFileAdapter(EnvPort):
    """Adapter that loads environment values from a bash-compatible source file."""

    def load_first_existing(self, paths: list[Path]) -> Mapping[str, str]:
        """Return values loaded from the first existing env source."""
        for path in paths:
            if not path.is_file():
                continue

            try:
                # Use bash to source the file and print the resulting environment
                # This ensures we handle bash syntax correctly (like export, etc.)
                cmd = f'source "{path}" >/dev/null 2>&1 && env'
                result = subprocess.run(
                    ["bash", "-lc", cmd],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                if result.returncode == 0:
                    return parse_env_output(result.stdout)
            except Exception:
                continue

        return {}
