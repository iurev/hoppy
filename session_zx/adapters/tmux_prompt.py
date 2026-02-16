"""Tmux-based interactive prompt adapter."""

import os
import subprocess
from pathlib import Path


class TmuxPromptAdapter:
    """Adapter that uses tmux splits to prompt for text input."""

    def prompt(self) -> str | None:
        """Open a tmux split with a prompt and return the entered text."""
        # Match the path used by the JS script and tests
        fifo_path = Path("/tmp/tmux_fzf_session_name")
        
        try:
            # Clean up existing
            if fifo_path.exists():
                fifo_path.unlink()
            
            # Create FIFO
            os.mkfifo(fifo_path)
            
            # Prepare command
            prompt_cmd = (
                f'printf "Session Name: " && '
                f'read session_name && '
                f'echo "$session_name" > "{fifo_path}"'
            )
            
            tmux_cmd = [
                "tmux", "split-window", "-v", "-l", "30%", "-b",
                f"bash -c '{prompt_cmd}'"
            ]
            
            # Open split window (this is non-blocking)
            subprocess.run(["bash", "-lc", " ".join(tmux_cmd)], check=True)
            
            # Read from FIFO (this will block until something is written)
            # We use a timeout to avoid hanging forever
            import select
            
            with open(fifo_path, "r") as fifo:
                # Use select to wait for data with timeout
                r, _, _ = select.select([fifo], [], [], 30)
                if r:
                    result = fifo.read().strip()
                    return result
                    
        except Exception:
            return None
        finally:
            if fifo_path.exists():
                try:
                    fifo_path.unlink()
                except Exception:
                    pass
                
        return None
