FINAL goal: we MUST rewrite *.mjs file into python; we're partially did this; Now we're somewhere in the middle;
We MUST not execute this mjs script at all during ANY steps (it's kept only as a working reference);

CRUCIAL: we have nvim hoppy.py, but this is SHITTY solution, it's ABSOLUTELY unacceptable to run it in the integration tests cause it calls mjs script; mjs script MUST Not be called; we already have the full python implementation. or if we don't have something: we MUST implement it.


Run child Gemini agents sequentially from this parent Gemini session.
No shell loops. No parallel runs. Start each run only after the previous run fully exits.

Phase 1 status:
1. `prompt1.md` iterations are already complete.
2. Do not run `prompt1.md` again in this loop.

Logging policy (must stay consistent for every run):
1. Log directory: `/home/yu/my/hoppy/child-agent-logs`
2. Filename format: `prompt2-run-XXX.log` (zero-padded 3-digit index, e.g. `001`, `002`, ...)
3. Capture both stdout and stderr in the same file.
4. Append `EXIT_CODE:<code>` to the end of that same file.
5. `tee` is allowed and preferred for live console + file logs, but only with `2>&1`.
6. Assume log directory already exists before starting the loop.

Runner contract (must match the working style that preserves blocked/error logs):
1. Invoke with `/bin/zsh -lc`.
2. Run from `/home/yu/my/hoppy`.
3. Use absolute paths for prompt and log file.
4. Keep `stdout`/`stderr` merged (`2>&1`) so Docker errors are logged.
5. If using `tee`, capture Gemini exit code from zsh `pipestatus[1]` (not `$?` after pipeline).

Coverage policy for Python unit tests (Docker-only):
1. Never run `python`/`uv` directly on host for coverage.
2. For every changed module, run module-scoped coverage proof.
3. Log the exact coverage command in the run report.

Coverage command template (per changed module):
`docker compose run --rm test pytest -q <unit_test_path> --cov=<python_module_import_path> --cov-branch --cov-report=term-missing`

Coverage command example:
`docker compose run --rm test pytest -q tests/unit/app/test_exit_codes.py --cov=hoppy.app.exit_codes --cov-branch --cov-report=term-missing`

Command template (preferred, with live output via tee, example run 001):
`/bin/zsh -lc 'gemini --yolo --no-sandbox --prompt "" < /home/yu/my/hoppy/prompt2.md 2>&1 | tee /home/yu/my/hoppy/child-agent-logs/prompt2-run-001.log; rc=${pipestatus[1]}; printf "\nEXIT_CODE:%s\n" "$rc" | tee -a /home/yu/my/hoppy/child-agent-logs/prompt2-run-001.log; exit "$rc"'`

Command template (file-only, no live stream, example run 001):
`/bin/zsh -lc 'gemini --yolo --no-sandbox --prompt "" < /home/yu/my/hoppy/prompt2.md > /home/yu/my/hoppy/child-agent-logs/prompt2-run-001.log 2>&1; rc=$?; printf "\nEXIT_CODE:%s\n" "$rc" >> /home/yu/my/hoppy/child-agent-logs/prompt2-run-001.log; exit "$rc"'`

Implementation loop:
1. Before each iteration, re-read `/home/yu/my/hoppy/loop.md` from disk (do not rely on cached instructions).
2. Run `prompt2.md` sequentially, up to 100 times total.
3. After each run, inspect the child agent final token:
   - `CONTINUE_NEXT` -> run `prompt2.md` again
   - `STOP_READY` -> stop immediately (all modules are complete and integration tests pass)
   - `BLOCKED_*` -> stop and report the blocker

Global stop rules:
1. If any run exits non-zero, stop and report run index + exit code.
2. If final token is missing/invalid, stop and report output as malformed.
3. Keep per-run logs so each run is auditable.

FINAL stop rules:
you should run integration tests in the "tests/*.py" and they all should pass; note: change mjs script to py script which you wrote
