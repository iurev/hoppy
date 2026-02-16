#!/usr/bin/env python3
import sys
from pathlib import Path

from session_zx.cli.main import main
from session_zx.app.main_composition import compose_app
from session_zx.use_cases.action_menu import run_action_menu

if __name__ == "__main__":
    # 1. Initialize basic infrastructure
    script_path = Path(sys.argv[0]).resolve()
    script_dir = script_path.parent
    
    # 2. Load and resolve environment
    from session_zx.adapters.env_file import EnvFileAdapter
    from session_zx.app.context import load_runtime_env, apply_env_defaults
    
    import os

    env_port = EnvFileAdapter()
    file_env = load_runtime_env(env_port, [
        script_dir / ".envs",
        Path.home() / ".tmux" / "plugins" / "tmux-fzf" / "scripts" / ".envs",
    ])
    # Start from os.environ so shell/tmux env vars are preserved,
    # then overlay with file values, then apply defaults for missing keys.
    merged_env = dict(os.environ)
    merged_env.update(file_env)
    resolved_env = apply_env_defaults(merged_env, "(^_^)")

    # Update process environment so all subprocesses inherit it
    os.environ.update(resolved_env)
    
    # 3. Compose application with resolved environment
    from session_zx.app.main_composition import AppDeps
    deps = AppDeps(script_dir, resolved_env)
    
    # Define how to select action if none provided via CLI
    def select_action():
        from session_zx.app.context import build_app_context
        from session_zx.use_cases.action_menu import run_action_menu
        ctx = build_app_context((None, []), deps, resolved_env)
        return run_action_menu(ctx)

    # 4. Run main entry point
    sys.exit(main(
        sys.argv[1:],
        deps=deps,
        env_port=env_port,
        select_action_uc=select_action,
        candidate_env_paths=[
            script_dir / ".envs",
            Path.home() / ".tmux" / "plugins" / "tmux-fzf" / "scripts" / ".envs",
        ]
    ))
