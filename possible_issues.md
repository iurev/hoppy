# Plan: Fix and Improve Integration Tests

## Context

The tests for `session-zx.mjs` have sanity issues (wrong/misleading code) and coverage gaps (missing workflows). This plan fixes existing problems and adds missing tests.

---

## Part 1: Fix Existing Tests

### Fix 1 — Remove useless `export` lines in popup tests

**Problem:** 5 tests have `tmux.run_command("export FZF_DEFAULT_OPTS='--reverse'")` which does nothing. Popup-switch creates a new subprocess that only inherits tmux global env (via `tmux set-environment -g`). The shell `export` only affects the test_session pane.

**Files:**
- `tests/test_real_behavior.py` — lines 95, 134-135, 169-170, 200-201
- `tests/test_mini_mechanics.py` — lines 92-93

**Action:** Remove the `tmux.run_command("export ...")` lines. Keep `os.system("tmux set-environment -g ...")`.

### Fix 2 — Strengthen filter assertion in `test_typing_filters_fzf_list`

**Problem:** After typing "beta", the test only checks "beta" is visible. It never checks that other items were filtered out.

**File:** `tests/test_real_behavior.py`, line 247-251

**Action:** After filtering, assert fzf shows `1/` in the match count line.

### Fix 3 — Strengthen arrow test in `test_arrow_keys_work_in_fzf`

**Problem:** Only checks "content is non-empty" before and after arrow press. Does not check cursor moved.

**File:** `tests/test_mini_mechanics.py`, line 167-168

**Action:** Assert `content_before != content_after`.

### Fix 4 — Add comment to `test_ctrl_n_debounce_only_switches_once`

**File:** `tests/test_real_behavior.py`, line 218

**Action:** Add comment explaining why we only assert `!= test_session` (cannot observe intermediate switches).

---

## Part 2: Add New Tests

All new tests go in `tests/test_real_behavior.py`.

### Test 1 — `test_ctrl_p_previews_session`

**Gap:** Zero tests for Ctrl+P. Only Ctrl+N is tested.

```
Setup: create "preview_p_target". Set --reverse + debounce=2000.
Open popup-switch. Press Ctrl+N (down), then Ctrl+P (back up).
Wait debounce. Check client returned to original or moved as expected.
Escape to close.
```

### Test 2 — `test_arrow_down_then_enter_switches`

**Gap:** No test for plain arrow keys + Enter (without live preview).

```
Setup: create "arrow_sess". Use switch (direct, not popup) with --reverse.
Arrow down to arrow_sess. Press Enter. Verify switched.
```

Arrow keys move cursor but do NOT trigger live preview (unlike Ctrl+N/P).

### Test 3 — `test_del_then_switch_another`

**Gap:** Current DEL test just checks session is gone. Does not test the reload + continued interaction flow.

```
Setup: create "victim" and "survivor".
Open popup-switch. Filter to "victim", press Delete, wait for kill + reload.
Clear filter (backspaces), type "survivor", Enter.
Verify: victim is gone AND switched to survivor.
```

### Test 4 — `test_clear_filter_with_backspaces`

**Gap:** Only 2 backspaces tested. No test for clearing full filter.

```
Setup: create "alpha", "beta".
Use switch (direct). Type "xxxxx" (no match). Backspace 5 times.
Verify all sessions visible again (check match count).
Type "alpha", Enter, verify switch.
```

### Test 5 — `test_kill_multiple_sessions_with_tab`

**Gap:** No test for TAB multi-select in kill action.

```
Setup: create "kill_a", "kill_b", "keep_c".
Run kill action (direct). Arrow to kill_a, Tab. Arrow to kill_b, Tab. Enter.
Verify: kill_a and kill_b gone, keep_c remains.
```

### Test 6 — `test_ctrl_n_then_ctrl_p_bounce`

**Gap:** No test that debounce cancellation works when N then P pressed quickly.

```
Setup: create session. Set --reverse + debounce=2000.
Open popup-switch. Ctrl+N, then immediately Ctrl+P.
Wait debounce. Verify client stayed at starting session (P cancelled N).
Escape to close.
```

### Test 7 — `test_filter_then_arrow_selects_second_match`

**Gap:** No test for filter + arrow composition.

```
Setup: create "proj_alpha", "proj_beta", "other".
Use switch (direct) with --reverse. Type "proj" (2 matches).
Arrow down once. Enter.
Verify switched to second match (proj_beta or proj_alpha depending on order).
```

### Test 8 — `test_arrow_up_then_enter_switches`

**Gap:** No arrow UP + Enter test.

```
Setup: create "up_a", "up_b", "up_c".
Use switch (direct) with --reverse. Arrow down twice, arrow up once.
Enter. Verify switched to correct session.
```

---

## Part 3: Not Testing (per user request)

- Number keys 1-9
- Frecency sorting
- Capital/worktree switch endpoints
- Detach (already skipped with documented reason)

---

## Verification

After all changes:
```bash
docker compose build
docker compose run --rm test pytest -v
```

All existing tests must still pass. New tests must pass.

---

## Files to Modify

| File | Changes |
|------|---------|
| `tests/test_real_behavior.py` | Fix 1,2,4 + add 8 new tests |
| `tests/test_mini_mechanics.py` | Fix 1,3 |
