"""Fzf-based selector implementations for CLI interaction."""

import time
from collections.abc import Sequence

from session_zx.adapters.fzf_cli import FzfCliAdapter
from session_zx.domain.models import FzfOptions


class FzfSelectors:
    """Selectors that use fzf for interactive choosing."""

    def __init__(self, fzf_adapter: FzfCliAdapter, env: dict[str, str]) -> None:
        self.fzf = fzf_adapter
        self.env = env

    def select_action(self, items: Sequence[str], header: str, multi: bool) -> str | None:
        """Show action menu and return selection."""
        options = FzfOptions(header=header, multi=multi)
        result = self.fzf.run(items, options, self.env)
        
        if result.is_cancelled() or result.is_error():
            return None
            
        return result.selection

    def select_switch(
        self, items: Sequence[str], header: str, multi: bool, extra_bindings: str
    ) -> str | None:
        """Show session switch fzf and return selection."""
        import shlex
        
        # Reliably parse extra bindings like --bind '...' --bind '...'
        extra_args = shlex.split(extra_bindings) if extra_bindings else []
            
        # Add hardcoded switch options to match JS parity
        # --no-sort --delimiter=" @ " --with-nth=1.. --nth=1
        extra_args.extend([
            "--no-sort",
            "--delimiter", " @ ",
            "--with-nth", "1..",
            "--nth", "1"
        ])
        
        # Add preview if requested (JS does it via TMUX_FZF_PREVIEW_OPTIONS)
        preview_opts = self.env.get("TMUX_FZF_PREVIEW_OPTIONS", "")
        if preview_opts:
            extra_args.extend(shlex.split(preview_opts))
        
        options = FzfOptions(
            header=header,
            multi=multi,
            extra_args=tuple(extra_args),
        )
        
        result = self.fzf.run(items, options, self.env)
        
        if result.is_cancelled() or result.is_error():
            return None
            
        return result.selection
