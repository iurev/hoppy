Run child Codex agents sequentially from this parent Codex session.
No shell loops. No parallel runs. Start each run only after the previous run fully exits.

Command template:
`codex exec --dangerously-bypass-approvals-and-sandbox -C /home/yu/my/hoppy - < prompt1.md`
(replace `prompt1.md` with `prompt2.md` for phase 2 runs)

Phase 1:
1. Run `prompt1.md` exactly 5 times (sequentially).

Phase 2:
1. Run `prompt2.md` sequentially, up to 100 times total.
2. After each run, inspect the child agent final token:
   - `CONTINUE_NEXT` -> run `prompt2.md` again
   - `STOP_READY` -> stop immediately (functionality is complete)
   - `BLOCKED_*` -> stop and report the blocker

Global stop rules:
1. If any run exits non-zero, stop and report run index + exit code.
2. If final token is missing/invalid, stop and report output as malformed.
3. Keep per-run logs so each run is auditable.
