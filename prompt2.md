You are implementing the Python rewrite iteratively with strict atomic slices.

Context:
- Source behavior reference: `session-zx.mjs`
- Planning source of truth: `plan.md`
- Test guidance: `tests_guide.md`

Objective for this run:
- Complete exactly ONE change package, then stop.
- This run MUST do one (and only one) of the following:
  1. Implement one new not-yet-implemented Python module with working unit tests.
  2. Implement one isolated fix for broken or changed behavior.
  3. If all modules are already implemented, run integration tests and make the Python script pass end-to-end.

Hard rules:
1. Start every run by executing unit tests in Docker and do a short code review of the touched area.
2. If baseline fails for unrelated reasons, stop with `BLOCKED_BASELINE` (no commit).
3. Use Docker-based commands only (no direct `python`/`uv` execution in this repo).
4. Do not batch unrelated modules/fixes/refactors in one run.
5. Create exactly one commit in this run.
6. Commits are module-sized (one whole module is allowed), not only function-sized.
7. Tests are required for every code change.
8. Unit-test coverage for every new or modified Python module must be 100% (line + branch).
9. Unit tests may use mocks at external boundaries (tmux/fzf/subprocess/fs/time/env).

Execution checklist:
1. Read `plan.md` and current implementation status.
2. Run unit-test baseline in Docker before edits.
3. Choose exactly one path:
   - Path A (new module): implement one missing module and its unit tests.
   - Path B (fix): implement one behavior fix and related tests.
   - Path C (integration): when all modules exist, run integration tests and fix integration issues until passing.
4. Run tests until they pass.
5. Prove 100% unit-test coverage (line + branch) for any module changed in this run.
6. Run relevant regression tests for impacted behavior.
7. Commit exactly once:
   - `feat(py): implement <module_name> with tests`
   - or `fix(py): fix <behavior> with tests`
   - or `fix(py): make integration flow pass`
8. Update `plan.md` progress for this single completed change package (same commit), then stop.

Output contract (final line must be exactly one token):
- `CONTINUE_NEXT` -> more work remains
- `STOP_READY` -> all modules are implemented and integration tests are passing
- `BLOCKED_<REASON>` -> cannot proceed safely

Before the final token, print a short run report with:
- selected path (`A`, `B`, or `C`) and slice/module
- files changed
- tests executed
- coverage proof summary
- commit hash (or `none` if blocked)
