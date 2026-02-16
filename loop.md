Run child Codex agents sequentially from this parent Codex session.
No shell loops. No parallel runs. Start each run only after the previous run fully exits.

Phase 1 status:
1. `prompt1.md` iterations are already complete.
2. Do not run `prompt1.md` again in this loop.

Command template:
`codex exec --dangerously-bypass-approvals-and-sandbox -C /home/yu/my/hoppy - < prompt2.md`

Implementation loop:
1. Run `prompt2.md` sequentially, up to 100 times total.
2. After each run, inspect the child agent final token:
   - `CONTINUE_NEXT` -> run `prompt2.md` again
   - `STOP_READY` -> stop immediately (all modules are complete and integration tests pass)
   - `BLOCKED_*` -> stop and report the blocker

Global stop rules:
1. If any run exits non-zero, stop and report run index + exit code.
2. If final token is missing/invalid, stop and report output as malformed.
3. Keep per-run logs so each run is auditable.
