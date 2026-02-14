You are implementing the Python rewrite iteratively with strict atomic slices.

Context:
- Source behavior reference: `session-zx.mjs`
- Planning source of truth: `plan.md`
- Test guidance: `tests_guide.md`

Objective for this run:
- Complete exactly ONE atomic slice, then stop.
- Preferred slice: one small production function + its unit tests.
- Allowed alternative: one isolated bug fix + its tests.

Hard rules:
1. Read `plan.md` and pick one highest-priority pending function/slice only.
2. Do not implement multiple production functions in one run.
3. Do not batch unrelated fixes/refactors.
4. Create at most one commit in this run.
5. Use Docker-based commands only (no direct `python`/`uv` execution in this repo).
6. Keep functions tiny, clearly named, and with minimal branching (prefer composition/guard clauses).
7. Unit tests may use mocks at external boundaries (tmux/fzf/subprocess/fs/time/env).

Execution checklist:
1. Validate baseline in Docker (relevant tests) before edits.
2. If baseline fails for unrelated reasons, stop with `BLOCKED_BASELINE` (no commit).
3. Implement the selected slice.
4. Add/update unit tests for the selected slice.
5. Prove 100% line + branch coverage for the touched module/function in Docker.
6. Run relevant regression tests for impacted behavior.
7. Commit exactly once:
   - `feat(py): implement <function_name> with tests`
   - or `fix(py): fix <behavior> with tests`
8. Update `plan.md` progress for this single completed slice (same commit), then stop.

Output contract (final line must be exactly one token):
- `CONTINUE_NEXT` -> more work remains
- `STOP_READY` -> all planned functionality is complete and passing
- `BLOCKED_<REASON>` -> cannot proceed safely

Before the final token, print a short run report with:
- selected slice/function
- files changed
- tests executed
- coverage proof summary
- commit hash (or `none` if blocked)
