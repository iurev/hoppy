"""Fzf orchestration adapter using the fzf CLI."""

from collections.abc import Mapping, Sequence
import os
import subprocess
import shlex

from session_zx.domain.models import FzfOptions, FzfResult
from session_zx.ports.process import ProcessPort


class FzfCliAdapter:
    """Adapter that executes fzf via a ProcessPort."""

    def __init__(self, process_port: ProcessPort) -> None:
        self.process = process_port

    def run(
        self,
        items: Sequence[str],
        options: FzfOptions,
        env: Mapping[str, str],
    ) -> FzfResult:
        """Execute fzf with provided items and options."""
        if not items:
            return FzfResult(exit_code=1)

        fzf_bin = env.get("TMUX_FZF_BIN", "fzf")
        fzf_opts = env.get("FZF_DEFAULT_OPTS", "")
        
        # Prepare environment
        run_env = dict(os.environ)
        run_env.update(env)
        run_env["FZF_DEFAULT_OPTS"] = fzf_opts

        # Build command string
        args = [fzf_bin] + options.as_argv()
        cmd_str = " ".join(shlex.quote(arg) for arg in args)
        
        items_body = "\n".join(items) + "\n"
        
        # In Docker tests, pexpect needs fzf to be connected to the terminal.
        # fzf detects terminal via /dev/tty if stdout is a pipe.
        # We MUST use bash -ls -c to match JS parity.
        
        try:
            # Command that pipes heredoc into fzf
            # We don't redirect stdout in the shell script yet
            shell_script = f"cat <<'__FZF_INPUT__' | {cmd_str}\n{items_body}__FZF_INPUT__\n"
            
            # Using Popen with stdout=PIPE and stderr=None (inherit)
            # This should let fzf use /dev/tty for its UI.
            process = subprocess.Popen(
                ["bash", "-ls", "-c", shell_script],
                stdout=subprocess.PIPE,
                stderr=None, 
                text=True,
                env=run_env,
            )
            
            # communicate() waits for process to finish
            stdout, _ = process.communicate()
            
            return FzfResult(
                exit_code=process.returncode,
                selection=stdout.strip(),
                error="",
            )
        except Exception as e:
            return FzfResult(exit_code=1, error=str(e))
