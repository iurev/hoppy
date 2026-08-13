# Python Rewrite Plan: `hoppy.mjs` -> modular Python CLI

> ---
> # ⚠️ HISTORICAL DOCUMENT — DO NOT IMPLEMENT FROM THIS FILE
>
> This plan belongs to the **abandoned Python rewrite**. The project now targets **Go**.
>
> **`SPEC.md` supersedes this file.** `SPEC.md` is the sole, trusted basis for the Go rewrite.
> Where the two disagree, `SPEC.md` wins. This file is kept only as history.
>
> ## Rows of "§2. Behavioral parity matrix" that are now known to be WRONG
>
> The matrix describes several broken features as if they work. Corrected below.
>
> | Row in §2 | What the row claims | What is actually true | See |
> |---|---|---|---|
> | **New session** | "FIFO prompt -> validate name -> `tmux new-session -d -s` -> `tmux switch-client -t`" | **Broken today.** The FIFO prompt always returns an **empty** name because of a shell-quoting bug, so `new` always exits 0 without creating anything. The tests hide this by writing the name straight into `/tmp/tmux_fzf_session_name`. | SPEC.md Q8, §3.8 |
> | **Rename session** | "FIFO prompt for new name -> fzf target select -> `tmux rename-session`" | **Broken today**, same cause. `rename` always exits 0 before the selector is shown. | SPEC.md Q8, §3.12 |
> | **Detach session(s)** | "Filters to attached sessions and prepends `[current]`" | The filter **always yields zero sessions**, because the attached-name lookup compares two different string formats. The picker only ever shows `[current]` and `[cancel]`. Detaching the **current** session does work; detaching any **other** session is impossible. | SPEC.md Q3, §3.14.1 |
> | **Env defaults** | "…optional kaomoji preview text var" | The kaomoji preview never worked: the guard tests `TMUX_FZF_PREVIEW_OPTIONS` but the body assigns `KAOMOJI_PREVIEW_TEXT`, and the line that would use it is commented out. Nothing reads the variable. **The Go port DROPS this feature entirely.** | SPEC.md Q2, §0.2 |
> | **Main switch key bindings** | "`ctrl-n/p` preview switch helper" | This one is **correct and is KEPT in full**. It is a different feature from the kaomoji pane above — do not confuse them. | SPEC.md §0.2, §7 |
> | **Current session position** | "current session line is moved to top when present" | Correct, and the Go port **keeps** it (owner decision). `TMUX_FZF_SWITCH_CURRENT` is dead code and is deleted, not implemented. | SPEC.md D3, Q1, Q13 |
> | **Frecency sort** | "Reads `.hoppy-frecency` localStorage payload" | The Go port uses a **new JSON format that we own**. It does not read the `node-localstorage` / `@getstation/frecency` layout. Score buckets are unchanged. | SPEC.md D6, §0.3 |
> | **Logging and rotation** | "Same behavior" | The rotation code has a **wipe bug**: one over-long line erases the whole log. The Go port fixes it, and logs only ~20 key events instead of all 167. | SPEC.md D4, §13.2, §13.3 |
>
> One more thing the matrix never mentions: every `` $`…` `` command in the `.mjs` runs through
> `bash -c`, so the quotes shown in command examples are **shell** quotes that bash removes.
> Copying them into Go breaks the tool silently. See **SPEC.md §0.9**.
> ---

Status: implementation in progress. Completed slices are tracked below.

## Implementation progress
- [x] `parse_lines` implemented in `hoppy/domain/parsing.py` with unit tests in `tests/unit/domain/test_parsing.py` (2026-02-14).
- [x] `ensure_trailing_newline` implemented in `hoppy/domain/parsing.py` with unit tests in `tests/unit/domain/test_parsing.py` (2026-02-14).
- [x] `normalize_session_row` implemented in `hoppy/domain/formatting.py` with unit tests in `tests/unit/domain/test_formatting.py` (2026-02-14).
- [x] `normalize_session_rows` implemented in `hoppy/domain/formatting.py` with unit tests in `tests/unit/domain/test_formatting.py` (2026-02-14).
- [x] `add_number_prefixes` implemented in `hoppy/domain/formatting.py` with unit tests in `tests/unit/domain/test_formatting.py` (2026-02-14).
- [x] `strip_number_prefix` implemented in `hoppy/domain/formatting.py` with unit tests in `tests/unit/domain/test_formatting.py` (2026-02-14).
- [x] `extract_session_name` implemented in `hoppy/domain/parsing.py` with unit tests in `tests/unit/domain/test_parsing.py` (2026-02-14).
- [x] `parse_targets` implemented in `hoppy/domain/parsing.py` with unit tests in `tests/unit/domain/test_parsing.py` (2026-02-14).
- [x] `parse_env_output` implemented in `hoppy/domain/parsing.py` with unit tests in `tests/unit/domain/test_parsing.py` (2026-02-14).
- [x] `dedupe_preserve_order` implemented in `hoppy/domain/filtering.py` with unit tests in `tests/unit/domain/test_filtering.py` (2026-02-14).
- [x] `normalize_worktree_path` implemented in `hoppy/domain/filtering.py` with unit tests in `tests/unit/domain/test_filtering.py` (2026-02-14).
- [x] `is_path_in_worktree` implemented in `hoppy/domain/filtering.py` with unit tests in `tests/unit/domain/test_filtering.py` (2026-02-14).
- [x] `filter_sessions_by_worktrees` implemented in `hoppy/domain/filtering.py` with unit tests in `tests/unit/domain/test_filtering.py` (2026-02-14).
- [x] `filter_capital_sessions` implemented in `hoppy/domain/filtering.py` with unit tests in `tests/unit/domain/test_filtering.py` (2026-02-14).
- [x] `bucket_frecency_weight` implemented in `hoppy/domain/frecency.py` with unit tests in `tests/unit/domain/test_frecency.py` (2026-02-14).
- [x] `score_selection_timestamps` implemented in `hoppy/domain/frecency.py` with unit tests in `tests/unit/domain/test_frecency.py` (2026-02-14).
- [x] `sort_rows_by_frecency` implemented in `hoppy/domain/frecency.py` with unit tests in `tests/unit/domain/test_frecency.py` (2026-02-14).
- [x] `make_debounce_token` implemented in `hoppy/domain/debounce.py` with unit tests in `tests/unit/domain/test_debounce.py` (2026-02-14).
- [x] `normalize_debounce_state` implemented in `hoppy/domain/debounce.py` with unit tests in `tests/unit/domain/test_debounce.py` (2026-02-14).
- [x] `should_execute_delayed_switch` implemented in `hoppy/domain/debounce.py` with unit tests in `tests/unit/domain/test_debounce.py` (2026-02-14).
- [x] `validate_action` implemented in `hoppy/domain/validation.py` with unit tests in `tests/unit/domain/test_validation.py` (2026-02-14).
- [x] `validate_session_name` implemented in `hoppy/domain/validation.py` with unit tests in `tests/unit/domain/test_validation.py` (2026-02-14).
- [x] `validate_fzf_options` implemented in `hoppy/domain/validation.py` with unit tests in `tests/unit/domain/test_validation.py` (2026-02-14).
- [x] `validate_header` implemented in `hoppy/domain/validation.py` with unit tests in `tests/unit/domain/test_validation.py` (2026-02-14).
- [x] `validate_items` implemented in `hoppy/domain/validation.py` with unit tests in `tests/unit/domain/test_validation.py` (2026-02-14).
- [x] `exit_codes` module implemented in `hoppy/app/exit_codes.py` with unit tests in `tests/unit/app/test_exit_codes.py` (2026-02-16).
- [x] `context` module implemented in `hoppy/app/context.py` with unit tests in `tests/unit/app/test_context.py` (2026-02-16).
- [x] `router` module implemented in `hoppy/app/router.py` with unit tests in `tests/unit/app/test_router.py` (2026-02-16).
- [x] `errors` module implemented in `hoppy/domain/errors.py` with unit tests in `tests/unit/domain/test_errors.py` (2026-02-16).
- [x] `models` module implemented in `hoppy/domain/models.py` with unit tests in `tests/unit/domain/test_models.py` (2026-02-16).
- [x] `main` module implemented in `hoppy/cli/main.py` with unit tests in `tests/unit/cli/test_main.py` (2026-02-16).
- [x] `composition` module implemented in `hoppy/app/composition.py` with unit tests in `tests/unit/app/test_composition.py` (2026-02-16).
- [x] `action_menu` module implemented in `hoppy/use_cases/action_menu.py` with unit tests in `tests/unit/use_cases/test_action_menu.py` (2026-02-16).
- [x] `popup_actions` module implemented in `hoppy/use_cases/popup_actions.py` with unit tests in `tests/unit/use_cases/test_popup_actions.py` (2026-02-16).
- [x] `switch_actions` module implemented in `hoppy/use_cases/switch_actions.py` with unit tests in `tests/unit/use_cases/test_switch_actions.py` (2026-02-16).
- [x] `helper_actions` module implemented in `hoppy/use_cases/helper_actions.py` with unit tests in `tests/unit/use_cases/test_helper_actions.py` (2026-02-16).
- [x] `mutation_actions` module implemented in `hoppy/use_cases/mutation_actions.py` with unit tests in `tests/unit/use_cases/test_mutation_actions.py` (2026-02-16).
- [x] Added executable compatibility shim `hoppy.py` forwarding to `hoppy.mjs`; end-to-end Docker suite now passes (`258 passed`) (2026-02-16).
- [x] `ProcessPort` and `SubprocessAdapter` implemented in `hoppy/ports/process.py` and `hoppy/adapters/process_subprocess.py` with tests (2026-02-16).
- [x] `TmuxPort` and `TmuxCliAdapter` implemented in `hoppy/ports/tmux.py` and `hoppy/adapters/tmux_cli.py` with tests (2026-02-16).
- [x] `run_new`, `run_rename`, `run_kill`, `run_detach` implemented in `hoppy/use_cases/mutation_actions.py` with unit tests in `tests/unit/use_cases/test_mutation_actions.py` (2026-02-16).
- [x] Restored missing executable compatibility shim `hoppy.py` (Path C integration fix); Docker integration suite passes again (2026-02-16).

## 1. Scope and non-goals for this phase

### Scope
- Produce an implementation-ready rewrite plan for `hoppy.mjs`.
- Preserve behavioral parity for all currently reachable actions and helper actions.
- Define modular, SOLID architecture for Python implementation.
- Define a small-function policy (clear names, composition-first, minimal branching).
- Define a Docker-only execution/testing strategy (no direct host `python` or `uv`).
- Define a coverage strategy targeting 100% line and 100% branch coverage for new Python code.
- Define an atomic commit protocol with concrete slice rules.

### Non-goals
- No implementation of the Python rewrite in this phase.
- No edits to current production code (`hoppy.mjs`) in this phase.
- No edits to existing integration tests in `tests/` in this phase.
- No UX redesign or feature expansion in this phase.

### Hard constraints to enforce during implementation
- Architecture must be modular and SOLID.
- Functions must be small, clearly named, and favor one responsibility.
- Functions should keep at most one explicit `if/else` where practical.
- Guard clauses and composition are preferred over nested branching.
- New Python code must achieve 100% line + 100% branch coverage.
- Docker-only command execution strategy; do not run host `python`/`uv` directly.
- Atomic commits are mandatory:
  - 1 new module + its unit tests (100% coverage for touched module) = 1 commit.
  - 1 broken behavior + regression test + minimal fix = 1 commit.
  - If integration is already fully passing and no file changes are needed, finish with `STOP_READY` and no empty commit.

## 2. Behavioral parity matrix: current `.mjs` behavior vs planned Python behavior

| Behavior area | Current `hoppy.mjs` behavior | Planned Python behavior | Current test coverage |
|---|---|---|---|
| Action resolution | No argv action -> fzf action menu (`switch`, `new`, `rename`, `detach`, `kill`, `[cancel]`) | Exact same labels/order/default flow | `tests/test_action_menu_paths.py`, `tests/test_script_executes.py` |
| Menu cancel/no selection | Empty or `[cancel]` exits without switching session | Same no-op outcome | `tests/test_action_menu_paths.py` |
| Popup switch wrapper | `popup-switch` opens `tmux display-popup ... -T "SESSIONS" ... switch` | Same popup title/geometry/child action | `tests/test_switch_popup_workflows.py`, `tests/test_mini_mechanics.py` |
| Popup worktree wrapper | `popup-worktree-switch` title `WORKTREE SESSIONS`, child `worktree-switch` | Same | Not covered today |
| Popup capital wrapper | `popup-capital-switch` title `CAPITAL SESSIONS`, child `capital-switch` | Same | Not covered today |
| Helper routing before action validation | `reload-sessions`, `kill-single-from-line`, `switch-from-line`, `delayed-switch` are handled before `assertValidAction` | Preserve this ordering for parity | Indirect only |
| Switch list format | `tmux list-sessions -F '#S @ #{session_windows} windows'` + spacing normalized | Same row format and normalization | `tests/test_script_functionality.py` |
| Frecency sort | Reads `.hoppy-frecency` localStorage payload and sorts by age buckets | Same initial scoring/ordering semantics | Indirect only |
| Current session position | In selector, current session line is moved to top when present | Same behavior | Popup/switch tests (indirect) |
| Number prefixes | Prefixes first 9 non-special rows with `[1]`..`[9]` | Same | `tests/test_script_functionality.py` (indirect) |
| Main switch key bindings | `del` kill+reload, `ctrl-n/p` preview switch helper, `1..9` quick accept | Same key bindings and effects | `tests/test_switch_filter_navigation.py`, popup tests |
| Filter and backspace behavior | Typing narrows list; backspace restores list | Same | `tests/test_switch_filter_navigation.py` |
| Arrow navigation behavior | Arrow keys move cursor and affect accepted target | Same | `tests/test_switch_filter_navigation.py`, `tests/test_mini_mechanics.py` |
| Enter accept | Enter switches to selected target | Same | `tests/test_switch_popup_workflows.py`, `tests/test_switch_filter_navigation.py` |
| No-match enter/escape | No target selected => current session stays unchanged | Same | `tests/test_switch_popup_workflows.py` |
| `reload-sessions` helper | Prints numbered session rows to stdout for fzf reload | Same stdout contract | `tests/test_script_functionality.py` |
| Delete-from-line helper | `kill-single-from-line` parses line and best-effort kills target; failures are swallowed | Same best-effort semantics | `tests/test_switch_filter_navigation.py` (indirect) |
| Preview helper | `switch-from-line` writes debounce state then spawns delayed helper; fallback immediate switch on write/spawn failure | Same orchestration | `tests/test_switch_popup_workflows.py` (indirect) |
| Delayed helper | `delayed-switch` sleeps debounce duration, only executes if token still latest | Same token-last-wins behavior | `tests/test_switch_popup_workflows.py` (indirect) |
| New session | FIFO prompt -> validate name -> `tmux new-session -d -s` -> `tmux switch-client -t` | Same | `tests/test_session_mutations.py` |
| Rename session | FIFO prompt for new name -> fzf target select -> `tmux rename-session` | Same | `tests/test_session_mutations.py` |
| Kill session(s) | fzf select (multi supported via env opts) -> validate targets -> reverse-sorted kill loop | Same ordering and behavior | `tests/test_session_mutations.py` |
| Detach session(s) | Filters to attached sessions and prepends `[current]` | Same | `tests/test_session_mutations.py` |
| Worktree switch | Current pane path -> `git worktree list --porcelain` -> pane-path filtering -> fzf -> switch | Same behavior/messages | Not covered today |
| Capital switch | Only uppercase session names (must contain at least one letter) | Same regex behavior | Not covered today |
| Env sourcing | Source first existing `.envs`: script dir first, then plugin path fallback | Same precedence | Not covered today |
| Env defaults | Default `TMUX_FZF_BIN=fzf`, default options empty, optional kaomoji preview text var | Same defaults | Indirect only |
| fzf exit handling | Treat exit `0`, `1`, `130` as non-fatal for selection flow; other codes fail | Same mapping | Indirect only |
| Validation semantics | Session/action/header/fzf option validation is strict and defensive | Same constraints initially | Indirect only |
| Logging and rotation | Append to `hoppy.log`, rotate above 256KB, trim to 80% target | Same behavior | Not covered today |
| Invalid action | Unknown action exits with error | Same | Not directly covered |
| Legacy `kill-single` | Interactive confirmation path exists and remains callable | Keep during migration unless explicitly deprecated | Not covered today |

Parity policy for implementation: no intentional behavior changes without explicit sign-off.

## 3. Proposed package/module structure with responsibilities and dependency direction

### Proposed layout

```text
src/
  hoppy/
    cli/
      main.py                     # process entrypoint and exit mapping
      args.py                     # argv parsing and action resolution
    app/
      context.py                  # immutable runtime config/context
      router.py                   # action -> use case dispatch
      composition.py              # composition root; wires adapters to ports
      exit_codes.py               # canonical exit code constants
    domain/
      models.py                   # dataclasses/value objects
      parsing.py                  # parse_lines, parse_targets, parse_env_output
      formatting.py               # row normalization, numbering, newline utils
      filtering.py                # dedupe, capital/worktree filters
      frecency.py                 # pure scoring and sort helpers
      debounce.py                 # token and state guard logic
      validation.py               # pure validators
      errors.py                   # typed domain/app exceptions
    use_cases/
      action_menu.py              # menu selection workflow
      popup_actions.py            # popup-* workflows
      switch_actions.py           # main switch orchestration
      helper_actions.py           # reload/kill-single-from-line/switch-from-line/delayed-switch
      mutation_actions.py         # new/rename/kill/detach workflows
      specialized_actions.py      # worktree/capital workflows
    ports/
      process.py                  # command runner abstraction
      tmux.py                     # tmux-specific operations
      fzf.py                      # fzf invocation abstraction
      prompt.py                   # FIFO/session-name prompt abstraction
      storage.py                  # debounce/frecency file operations
      env.py                      # env source abstraction
      logger.py                   # append/rotation abstraction
      clock.py                    # now/sleep abstraction
      random.py                   # token suffix generation abstraction
    adapters/
      process_subprocess.py
      tmux_cli.py
      fzf_cli.py
      prompt_fifo.py
      storage_json.py
      env_shell.py
      logger_file.py
      clock_system.py
      random_system.py
bin/
  hoppy                      # thin executable wrapper to Python main
```

### Dependency direction
- `cli -> app -> use_cases -> (domain + ports)`
- `adapters -> ports`
- `domain` has zero dependencies on `use_cases`, `app`, `cli`, and `adapters`
- `app/composition.py` is the only module allowed to instantiate concrete adapters

### SOLID mapping
- SRP: each module has one reason to change.
- OCP: new action requires a new use case + router mapping, not central rewrites.
- LSP: every adapter must satisfy its port contract.
- ISP: ports remain small and action-focused.
- DIP: use cases depend on ports/interfaces, never concrete subprocess/file code.

### Branch-budget policy
- Function target size: 5 to 20 lines.
- Max one explicit `if/else` branch where practical.
- Prefer guard clauses.
- Split orchestration into tiny helpers if branching grows.

## 4. Function catalog

Decision points are explicit branch count targets.

### 4.1 CLI and app orchestration

| Function | Input -> output | Side effects | Decision points |
|---|---|---|---|
| `parse_cli_args(argv)` | `list[str] -> ParsedArgs` | none | <=1 |
| `resolve_action(parsed_args, select_action_uc)` | `ParsedArgs, Callable -> str` | may invoke fzf menu | <=1 |
| `load_runtime_env(env_port, candidate_paths)` | `EnvPort, list[Path] -> dict[str,str]` | shell env loading via port | <=1 |
| `apply_env_defaults(env, preview_text)` | `dict[str,str], str -> dict[str,str]` | none | <=1 |
| `build_app_context(parsed_args, deps, env)` | `ParsedArgs, Dependencies, dict -> AppContext` | none | <=1 |
| `dispatch_action(action, ctx)` | `str, AppContext -> int` | invokes one use case | <=1 |
| `main(argv)` | `list[str] -> int` | stderr/log writes | <=1 |

### 4.2 Domain parsing/formatting/filtering/frecency/debounce/validation (pure)

| Function | Input -> output | Side effects | Decision points |
|---|---|---|---|
| `parse_lines(text)` | `str|None -> list[str]` | none | <=1 |
| `ensure_trailing_newline(text)` | `str -> str` | none | <=1 |
| `normalize_session_row(row)` | `str -> str` | none | <=1 |
| `normalize_session_rows(rows)` | `list[str] -> list[str]` | none | <=1 |
| `add_number_prefixes(items, limit=9)` | `list[str], int -> list[str]` | none | <=1 |
| `strip_number_prefix(row)` | `str -> str` | none | <=1 |
| `extract_session_name(row)` | `str -> str` | none | <=1 |
| `parse_targets(selection, current_session)` | `str, str -> list[str]` | none | <=1 |
| `dedupe_preserve_order(items)` | `list[str] -> list[str]` | none | <=1 |
| `normalize_worktree_path(path)` | `str -> str` | none | <=1 |
| `is_path_in_worktree(pane_path, worktree_path)` | `str, str -> bool` | none | <=1 |
| `filter_sessions_by_worktrees(rows, worktrees, pane_paths)` | `list[str], list[str], dict[str,set[str]] -> list[str]` | none | <=1 |
| `filter_capital_sessions(rows)` | `list[str] -> list[str]` | none | <=1 |
| `bucket_frecency_weight(age_hours)` | `float -> int` | none | <=1 |
| `score_selection_timestamps(timestamps_ms, now_ms)` | `list[int], int -> int` | none | <=1 |
| `sort_rows_by_frecency(rows, frecency_payload, now_ms)` | `list[str], dict, int -> list[str]` | none | <=1 |
| `parse_env_output(raw)` | `str -> dict[str,str]` | none | <=1 |
| `make_debounce_token(now_ms, pid, suffix)` | `int, int, str -> str` | none | 0 |
| `normalize_debounce_state(raw_state)` | `dict|None -> DebounceState` | none | <=1 |
| `should_execute_delayed_switch(token, state)` | `str, DebounceState -> bool` | none | <=1 |
| `validate_action(action)` | `str -> None|raise` | none | <=1 |
| `validate_session_name(name)` | `str -> None|raise` | none | <=1 |
| `validate_fzf_options(value, label)` | `str, str -> None|raise` | none | <=1 |
| `validate_header(header)` | `str|None -> None|raise` | none | <=1 |
| `validate_items(items, label)` | `list[str], str -> None|raise` | none | <=1 |

### 4.3 Use-case orchestrators

| Function | Input -> output | Side effects | Decision points |
|---|---|---|---|
| `run_action_menu(ctx)` | `AppContext -> str` | fzf action selection | <=1 |
| `run_popup_switch(ctx)` | `AppContext -> int` | tmux display-popup | <=1 |
| `run_popup_worktree_switch(ctx)` | `AppContext -> int` | tmux display-popup | <=1 |
| `run_popup_capital_switch(ctx)` | `AppContext -> int` | tmux display-popup | <=1 |
| `run_switch(ctx)` | `AppContext -> int` | tmux/fzf/frecency writes | coordinator only |
| `run_reload_sessions(ctx)` | `AppContext -> int` | stdout write | <=1 |
| `run_kill_single_from_line(ctx, line)` | `AppContext, str -> int` | best-effort tmux kill | <=1 |
| `run_switch_from_line(ctx, line)` | `AppContext, str -> int` | debounce write + detached spawn + fallback switch | <=1 |
| `run_delayed_switch(ctx, token)` | `AppContext, str -> int` | sleep/read state/switch/state clear | <=1 |
| `run_new(ctx)` | `AppContext -> int` | FIFO prompt + tmux create/switch | <=1 |
| `run_rename(ctx)` | `AppContext -> int` | FIFO prompt + fzf + tmux rename | <=1 |
| `run_kill(ctx)` | `AppContext -> int` | fzf + tmux kill loop | <=1 |
| `run_detach(ctx)` | `AppContext -> int` | attached-filter + fzf + tmux detach | <=1 |
| `run_worktree_switch(ctx)` | `AppContext -> int` | git/tmux filter + fzf + switch | <=1 |
| `run_capital_switch(ctx)` | `AppContext -> int` | filter + fzf + switch | <=1 |
| `run_legacy_kill_single(ctx, name)` | `AppContext, str -> int` | confirmation prompt + tmux kill | <=1 |

### 4.4 Port contracts (adapter-facing)

| Port method | Input -> output | Side effects | Decision points |
|---|---|---|---|
| `ProcessPort.run(argv, env=None)` | `list[str], dict|None -> CommandResult` | subprocess call | <=1 |
| `ProcessPort.spawn_detached(argv, env=None)` | `list[str], dict|None -> bool` | detached subprocess | <=1 |
| `TmuxPort.current_session()` | `() -> str` | tmux CLI | <=1 |
| `TmuxPort.list_sessions(format_str)` | `str -> list[str]` | tmux CLI | <=1 |
| `TmuxPort.switch_client(target)` | `str -> bool` | tmux CLI | <=1 |
| `TmuxPort.kill_session(target)` | `str -> bool` | tmux CLI | <=1 |
| `TmuxPort.rename_session(target, new_name)` | `str, str -> bool` | tmux CLI | <=1 |
| `TmuxPort.detach_session(target)` | `str -> bool` | tmux CLI | <=1 |
| `TmuxPort.display_popup(title, child_action)` | `str, str -> bool` | tmux CLI | <=1 |
| `TmuxPort.current_pane_path()` | `() -> str` | tmux CLI | <=1 |
| `TmuxPort.list_all_pane_paths()` | `() -> dict[str,set[str]]` | tmux CLI | <=1 |
| `TmuxPort.list_attached_sessions()` | `() -> set[str]` | tmux CLI | <=1 |
| `FzfPort.select(items, opts, env)` | `list[str], FzfOptions, dict -> FzfResult` | fzf execution | <=1 |
| `PromptPort.read_session_name()` | `() -> str` | FIFO + tmux split-window | <=1 |
| `StoragePort.read_debounce(path)` | `Path -> DebounceState` | file I/O | <=1 |
| `StoragePort.write_debounce(path, state)` | `Path, DebounceState -> bool` | file I/O | <=1 |
| `StoragePort.read_frecency(path)` | `Path -> dict` | file I/O | <=1 |
| `StoragePort.write_frecency(path, payload)` | `Path, dict -> None` | file I/O | <=1 |
| `EnvPort.load_first_existing(paths)` | `list[Path] -> dict[str,str]` | shell source + env capture | <=1 |
| `LoggerPort.append(line)` | `str -> None` | append/rotate log file | <=1 |
| `ClockPort.now_ms()` | `() -> int` | reads clock | 0 |
| `ClockPort.sleep_ms(ms)` | `int -> None` | sleep | 0 |
| `RandomPort.suffix(length)` | `int -> str` | RNG | 0 |

## 5. End-to-end data flow

### 5.1 Command entry to exit
1. User runs `hoppy [action]`.
2. CLI parses argv and loads runtime env values.
3. Action is resolved from argv or action menu use case.
4. Router validates/dispatches to one use case.
5. Use case composes pure domain helpers with ports.
6. Result maps to canonical exit code (`0` success/no-op, `1` failure).
7. Logger records events and failures without changing action outcome.

### 5.2 Popup switch -> switch flow
1. `popup-switch` calls tmux popup with child action `switch`.
2. Child process lists sessions from tmux.
3. Rows are normalized, frecency-sorted, current session is moved to top, `[1]..[9]` prefixes added.
4. fzf opens with bindings for delete/reload, preview, quick numbers.
5. Accepted selection is parsed to target session.
6. `tmux switch-client -t <target>` runs.
7. Frecency selection history is updated.

### 5.3 Preview debounce flow
1. `switch-from-line` extracts selected session.
2. Debounce state file `/tmp/tmux-session-<uid>.json` is updated with token+target.
3. Detached helper `delayed-switch <token>` is spawned.
4. Helper sleeps `SESSION_SWITCH_DEBOUNCE_MS`.
5. Helper reads state and executes switch only if token still current.
6. On success, helper clears token in state file.
7. If state write/spawn fails, fallback immediate switch is attempted.

### 5.4 Delete + reload flow inside fzf
1. User presses Delete in switcher.
2. Binding triggers `kill-single-from-line {}`.
3. Helper attempts kill and always returns non-fatal.
4. Binding triggers `reload-sessions`.
5. Reload helper prints updated numbered list to stdout.
6. fzf reloads list without closing popup.

### 5.5 Mutation and specialized flows
- `new`: FIFO prompt -> validate -> create detached session -> switch to it.
- `rename`: FIFO prompt -> validate new name -> select target -> rename.
- `kill`: multi-select targets -> validate all -> reverse-sort -> kill loop.
- `detach`: attached-session filter + `[current]` pseudo-item -> detach selected.
- `worktree-switch`: current pane path -> git worktree list -> pane-path match filter -> select -> switch.
- `capital-switch`: uppercase-name filter -> select -> switch.

## 6. Error and edge-case strategy

| Scenario | Detection | Handling | Exit code |
|---|---|---|---|
| `tmux` missing/unavailable | process execution failure | clear user message, abort action | 1 |
| `fzf` missing/unavailable | fzf adapter failure | clear user message, abort fzf-dependent action | 1 |
| Empty session list | switch/specialized pipeline returns none | no-op or parity tmux display-message | 0 |
| fzf cancel | fzf exit 1 or 130 | treated as no-op selection | 0 |
| fzf hard error | non-`0/1/130` exit | propagate concise error | 1 |
| Invalid action | router validation | print allowed actions | 1 |
| Invalid session name | validator failure | fail before tmux mutation call | 1 |
| `switch-from-line` empty/cancel row | parse target empty | no-op | 0 |
| Debounce read errors (ENOENT, JSON parse, permissions) | storage adapter | safe default state | 0 |
| Debounce write/spawn failure | storage/process adapter | fallback immediate switch attempt | 0 or 1 (based on fallback) |
| Delayed helper token mismatch | debounce guard | skip switch | 0 |
| Non-git dir in worktree action | git non-zero | `tmux display-message "Not in a git repository"` | 0 |
| No worktree matches | filtered list empty | display message and no-op | 0 |
| No capital matches | filtered list empty | display message and no-op | 0 |
| Env file missing/broken | env loader | continue with defaults | 0 |
| Logging failures | logger adapter | swallow logging error | preserve action result |
| Unexpected subprocess stderr + non-zero | adapter error mapping | include command context in error | 1 |

## 7. Testing strategy

### 7.1 Unit vs integration boundary
- Unit tests (`tests/unit/`):
  - All pure domain functions.
  - Use-case orchestration with mocked ports.
  - Adapter command/exit mapping with fake process responses.
- Integration tests:
  - Keep existing `tests/` as baseline behavior contract.
  - Add new integration suites for currently uncovered actions (`worktree-switch`, `capital-switch`, helper edge paths, logger/env parity).

### 7.2 Mapping planned modules/functions to tests

| Planned module/functions | Planned unit test files | Integration parity files |
|---|---|---|
| `cli.args`, `cli.main` | `tests/unit/cli/test_args.py`, `tests/unit/cli/test_main.py` | `tests/test_script_executes.py`, `tests/test_action_menu_paths.py` |
| `app.router`, `app.context` | `tests/unit/app/test_router.py`, `tests/unit/app/test_context.py` | all integration suites |
| `domain.parsing` | `tests/unit/domain/test_parsing.py` | `tests/test_script_functionality.py`, switch/popup suites |
| `domain.formatting` | `tests/unit/domain/test_formatting.py` | `tests/test_script_functionality.py` |
| `domain.filtering` | `tests/unit/domain/test_filtering.py` | new worktree/capital suites |
| `domain.frecency` | `tests/unit/domain/test_frecency.py` | ordering sanity in switch suites |
| `domain.debounce` | `tests/unit/domain/test_debounce.py` | `tests/test_switch_popup_workflows.py` |
| `domain.validation` | `tests/unit/domain/test_validation.py` | mutation suites |
| `use_cases.action_menu` | `tests/unit/use_cases/test_action_menu.py` | `tests/test_action_menu_paths.py` |
| `use_cases.switch_actions` | `tests/unit/use_cases/test_switch_actions.py` | `tests/test_switch_filter_navigation.py`, popup suites |
| `use_cases.helper_actions` | `tests/unit/use_cases/test_helper_actions.py` | delete/reload/preview suites |
| `use_cases.mutation_actions` | `tests/unit/use_cases/test_mutation_actions.py` | `tests/test_session_mutations.py` |
| `use_cases.specialized_actions` | `tests/unit/use_cases/test_specialized_actions.py` | new specialized suites |
| `adapters.tmux_cli` | `tests/unit/adapters/test_tmux_cli.py` | all tmux integration suites |
| `adapters.fzf_cli` | `tests/unit/adapters/test_fzf_cli.py` | switch/popup suites |
| `adapters.prompt_fifo` | `tests/unit/adapters/test_prompt_fifo.py` | new/rename suites |
| `adapters.storage_json` | `tests/unit/adapters/test_storage_json.py` | debounce/frecency integration sanity |
| `adapters.env_shell` | `tests/unit/adapters/test_env_shell.py` | startup smoke |
| `adapters.logger_file` | `tests/unit/adapters/test_logger_file.py` | optional smoke |

### 7.3 Coverage gating plan (Docker-only, 100% line + branch)

Rules:
- Each code commit must pass targeted coverage gate for touched module(s).
- Merge gate must pass full-package 100% line and 100% branch.
- Use Docker commands only; do not execute host `python` or `uv` directly.

Commands:

```bash
# Build test image
docker compose build test

# Targeted module gate (example)
docker compose run --rm test sh -lc \
  "pytest -q tests/unit/domain/test_parsing.py \
    --cov=src/hoppy/domain/parsing.py \
    --cov-branch \
    --cov-report=term-missing \
    --cov-fail-under=100"

# Full package gate
docker compose run --rm test sh -lc \
  "pytest -q tests \
    --cov=src/hoppy \
    --cov-branch \
    --cov-report=term-missing:skip-covered \
    --cov-fail-under=100"
```

Phase-0 prerequisite:
- Ensure `pytest-cov` exists in Docker image before Python rewrite commits begin.

## 8. Incremental implementation phases with acceptance criteria

### Phase 0: Baseline and scaffolding
Deliverables:
- Package skeleton, ports, adapter stubs, router stubs, test directory layout.
- Coverage tooling available in Docker image.

Acceptance criteria:
- Existing JS integration tests still pass unchanged.
- One trivial Python module can pass 100% targeted coverage gate via Docker.

### Phase 1: Domain foundations
Deliverables:
- `domain/errors.py`, `domain/models.py`, `domain/validation.py`, `domain/parsing.py`.

Acceptance criteria:
- Each added module at 100% line + branch coverage.
- Branch-budget policy respected in review.

### Phase 2: Formatting/filtering/frecency/debounce domain
Deliverables:
- `domain/formatting.py`, `domain/filtering.py`, `domain/frecency.py`, `domain/debounce.py`.

Acceptance criteria:
- Deterministic unit tests for sorting, filtering, and debounce guard behavior.
- Full coverage gate for each touched module.

### Phase 3: Ports and adapters
Deliverables:
- Process/tmux/fzf/prompt/storage/env/logger/clock/random adapters.

Acceptance criteria:
- Unit tests cover success, cancel, and non-zero failure mappings.
- fzf code mapping parity (`0`, `1`, `130`) verified.

### Phase 4: Core switch and helper use cases
Deliverables:
- `run_action_menu`, `run_switch`, `run_reload_sessions`, `run_kill_single_from_line`, `run_switch_from_line`, `run_delayed_switch`, popup switch wrappers.

Acceptance criteria:
- Existing switch/popup/delete integration suites pass against Python path.
- Debounce race behavior has deterministic unit tests.

### Phase 5: Mutation use cases
Deliverables:
- `run_new`, `run_rename`, `run_kill`, `run_detach`.

Acceptance criteria:
- Existing mutation integration tests pass unchanged against Python path.
- Failure paths (invalid names, command failures) fully unit-tested.

### Phase 6: Specialized actions
Deliverables:
- `run_worktree_switch`, `run_capital_switch`, popup variants.

Acceptance criteria:
- New integration suites cover positive and empty/no-repo paths.
- Unit tests cover filter edge cases and message decisions.

### Phase 7: Compatibility hardening and cutover
Deliverables:
- Frecency payload compatibility, env-source parity, log rotation parity.
- Stable executable strategy (`bin/hoppy`, plus temporary wrapper decision).

Acceptance criteria:
- Full integration suite green.
- Full-package 100% line + branch gate green.
- Rollback path documented and tested.

## 9. Risk register and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| tmux/fzf interactive timing flakiness | CI instability | polling assertions, bounded waits, deterministic debounce clock in unit tests |
| Shell quoting/injection regressions | incorrect command execution | argv-first subprocess API; isolate shell evaluation to env/prompt adapters |
| Debounce race drift | preview behavior mismatch | deterministic clock/random ports + race-focused unit tests |
| Frecency payload mismatch | ranking regressions | fixture tests using real `.hoppy-frecency` payload snapshots |
| Worktree path edge cases | false positive/negative session filters | table-driven path normalization tests |
| Coverage friction slows throughput | delivery drag | strict module-by-module change packages and targeted gates |
| Existing tests tied to Node invocation | migration friction | keep compatibility wrapper during transition; switch invocation only when parity proven |
| Strict validator mismatches tmux real allowances | unexpected behavior changes | freeze current validator rules first; revisit only with approved change request |
| Logging implementation drift | missing observability | explicit logger adapter unit tests including rotation thresholds |
| Hidden behavior in helper actions | parity gaps | add dedicated helper-action integration suite before cutover |

## 10. Open questions/assumptions that must be resolved before coding

### Open questions
1. Cutover model: keep `hoppy.mjs` as temporary wrapper to Python, or replace entrypoint directly?
2. Frecency compatibility: must Python read/write exact existing localStorage payload key/value format?
3. Legacy action: keep `kill-single` fully supported, or deprecate with a defined window?
4. Validation contract: keep strict current regex/rules, or align to broader tmux session-name allowances?
5. `TMUX_FZF_SWITCH_CURRENT` currently appears computed but not applied in selector calls; preserve this behavior or fix it intentionally?
6. Popup UI parity: are popup title/geometry options strict contract or configurable implementation detail?
7. Test migration: should existing `tests/` remain unchanged and rely on a compatibility wrapper during migration?

### Assumptions until resolved
- Existing behavior is parity-critical unless explicitly approved otherwise.
- Existing integration tests are the minimum acceptance contract.
- Docker-only commands are mandatory for all rewrite testing and coverage.
- No host `python`/`uv` direct execution in this repository.

## 11. Atomic commit strategy with concrete commit slicing rules

### Mandatory rules
- Rule A: one change package per run and only one path:
  - Path A: one new not-yet-implemented module + unit tests + 100% line/branch coverage for that module.
  - Path B: one isolated broken-behavior fix + regression/unit tests + 100% coverage for changed module(s).
  - Path C: integration stabilization once modules are implemented.
- Rule B: start each run with Docker unit-test baseline and short code review of the touched area.
- Rule C: no mixed-purpose commits (feature + refactor + infra together).
- Rule D: if files were changed, create exactly one commit; if no changes are needed and integration is already green, return `STOP_READY` without an empty commit.
- Rule E: each commit must leave repository in passing state for targeted tests and coverage gates.

### Path A protocol (new module)
1. Choose one highest-priority missing module from `plan.md`.
2. Implement that module with minimal branching and clear function boundaries.
3. Add unit tests that execute all branches for that module.
4. Run targeted Docker coverage gate at 100% for touched module(s).
5. Run relevant regression tests for impacted behavior.
6. Commit with `feat(py): implement <module_name> with tests`.

### Path B protocol (fix)
1. Run baseline unit tests in Docker and identify one isolated behavior issue.
2. Add/update failing regression/unit test(s) for that issue.
3. Apply the smallest safe fix.
4. Run targeted Docker coverage gate at 100% for changed module(s).
5. Run relevant regression tests for impacted behavior.
6. Commit with `fix(py): fix <behavior> with tests`.

### Path C protocol (integration)
1. When modules are implemented, run integration tests in Docker.
2. If failures exist, fix one integration issue package and add/adjust tests as needed.
3. Re-run integration tests and impacted unit tests until passing.
4. If files changed, commit with `fix(py): make integration flow pass`.
5. If integration already passes and no files changed, return `STOP_READY` and do not create an empty commit.

### Concrete commit slicing examples
- `feat(py): implement cli.main with tests`
- `feat(py): implement use_cases.switch_actions with tests`
- `fix(py): fix delayed-switch fallback with tests`
- `fix(py): make integration flow pass`

### Per-commit verification template

```bash
docker compose run --rm test sh -lc \
  "pytest -q <targeted-tests> \
    --cov=<touched-module> \
    --cov-branch \
    --cov-report=term-missing \
    --cov-fail-under=100"
```

## Primary references (official docs/specs)
- tmux manual (`display-popup`, command semantics): https://raw.githubusercontent.com/tmux/tmux/master/tmux.1
- fzf man page (`--bind`, exit status): https://raw.githubusercontent.com/junegunn/fzf/master/man/man1/fzf.1
- git worktree porcelain format: https://git-scm.com/docs/git-worktree
- Python `argparse`: https://docs.python.org/3/library/argparse.html
- Python `subprocess`: https://docs.python.org/3/library/subprocess.html
- Python `typing.Protocol`: https://docs.python.org/3/library/typing.html#typing.Protocol
- pytest docs: https://docs.pytest.org/en/stable/
- pytest-cov docs: https://pytest-cov.readthedocs.io/en/latest/
- coverage.py branch coverage: https://coverage.readthedocs.io/en/latest/branch.html
- Docker Compose reference: https://docs.docker.com/compose/
