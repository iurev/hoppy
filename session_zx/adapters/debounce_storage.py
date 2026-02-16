"""Debounce state storage adapter using local JSON files."""

import json
import os
from pathlib import Path


class JsonDebounceStorage:
    """Storage adapter that persists debounce state to a JSON file."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def read(self) -> dict[str, object] | None:
        """Read debounce state from disk."""
        if not self.file_path.is_file():
            return None

        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def write(self, state: dict[str, object]) -> bool:
        """Write debounce state to disk."""
        try:
            # Ensure directory exists
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.file_path, "w") as f:
                json.dump(state, f)
            return True
        except Exception:
            return False
