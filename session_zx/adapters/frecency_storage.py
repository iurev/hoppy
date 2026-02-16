"""Frecency storage adapter using local JSON files."""

import json
import os
from pathlib import Path


class JsonFrecencyStorage:
    """Storage adapter that persists frecency data to a JSON file."""

    def __init__(self, storage_dir: Path) -> None:
        self.storage_dir = storage_dir
        self.file_path = storage_dir / "frecency_tmux-sessions"

    def load(self) -> dict[str, object]:
        """Load frecency data from disk."""
        if not self.file_path.is_file():
            return {"selections": {}}

        try:
            with open(self.file_path, "r") as f:
                return json.load(f)
        except Exception:
            return {"selections": {}}

    def save_selection(self, selected_id: str, now_ms: int) -> None:
        """Record a new selection in the frecency data."""
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        data = self.load()
        selections = data.setdefault("selections", {})
        
        # Ensure it's a dict
        if not isinstance(selections, dict):
            selections = {}
            data["selections"] = selections
            
        selection_data = selections.setdefault(selected_id, {"selectedAt": []})
        if not isinstance(selection_data, dict):
            selection_data = {"selectedAt": []}
            selections[selected_id] = selection_data
            
        timestamps = selection_data.setdefault("selectedAt", [])
        if not isinstance(timestamps, list):
            timestamps = []
            selection_data["selectedAt"] = timestamps
            
        timestamps.append(now_ms)
        
        try:
            with open(self.file_path, "w") as f:
                json.dump(data, f)
        except Exception:
            pass
