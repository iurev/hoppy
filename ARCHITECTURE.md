# ARCHITECTURE — the Go port of `session-zx.mjs`

Status: design + compiling skeleton. No application logic yet.
Written 2026-08-07. Language: simple English, short sentences (project rule).

Read order for an implementer: `SPEC.md` §0 → this file → `SPEC.md` §1-§16.

---

## 1. Reconciliation — SPEC.md vs go-libs.md vs test-contract.md

Three agents wrote the three input documents. They disagreed in 14 places.
`SPEC.md` §0 is binding, so where SPEC was out of date I edited SPEC.

### 1.1 Contradictions found and how they were resolved

| # | Topic | SPEC said | The other doc said | Resolution | SPEC edited? |
|---|---|---|---|---|---|
| R1 | Shell-word splitter | §0.5, Q16: use `github.com/google/shlex` | go-libs §3.2: shlex is **archived since 2019-12-02** and its double-quote backslash escapes *any* character, so `"a\b"` → `ab`. §0.5's own table requires `a\b`. Use `github.com/kballard/go-shellquote`. | go-libs wins. SPEC named a library that fails SPEC's own table. | **yes** — §0.5 and Q16 |
| R2 | Which shell runs `--bind` commands | §0.9.3, Q17: "fzf runs the inner command with `sh -c`" | go-libs S1: fzf reads `$SHELL` and only falls back to `sh`. True since fzf 0.11.3. Fix by passing `--with-shell sh` (fzf ≥ 0.51.0). | go-libs wins. SPEC's claim was false; the fix makes it true. **CORRECTED 2026-08-07:** the value must be `sh -c`, not `sh`. `--with-shell` takes the shell *and its flags* and fzf runs `<value words> <command>`. With a bare `sh` every `--bind` command fails silently — DEL and Ctrl+N/P simply do nothing. Verified against fzf 0.60.3. | **yes** — §0.5, §0.9.3, §10.2.1, Q17 |
| R3 | Minimum fzf version | O-1: "`pos(N)` needs fzf ≥ 0.36" | go-libs: `--with-shell` needs 0.51.0. test-contract §7.5: "project minimum is 0.51.0, pin it". | Floor is **0.51.0**. The test image pins **0.60.3**. | **yes** — O-1 |
| R4 | `reload-sessions` and the `[cancel]` row | §3.3: "No `[cancel]` row is printed". Q7 is labelled **FIX**: make reload identical to the initial list. | test-contract §4.1 repeats "prints no `[cancel]` row (SPEC §3.3 / Q7)". | SPEC contradicted **itself**; test-contract copied the wrong half. Q7 is a FIX, so the Go port **does** pin the current session and **does** append `[cancel]`. No test breaks. | **yes** — §3.3 |
| R5 | Go version | not stated | go-libs §5: `go 1.25` in go.mod, build with 1.26.x. test-contract §7.2 sketch: `FROM golang:1.23-bookworm`. | go-libs wins (1.23 is out of security support). `go.mod` says `go 1.25`; the image is `golang:1.26-bookworm` (go1.26.5 verified). | n/a |
| R6 | Where the Go source lives | not stated | test-contract §7.2 builds `./cmd/session-zx` | Rejected. A `cmd/` directory adds a package boundary for nothing. Flat `package main` at the repo root; build with `go build -o session-zx .` | n/a (recorded here) |
| R7 | Binary name and path | never stated | test-contract §3.5: must be `/app/session-zx` or `conftest.py:37` stops cleaning frecency | Adopted as binding. | **yes** — new §0.55 |
| R8 | Atomic write durability | §0.3, §13.3: "temp file + rename" | go-libs S3: rename is atomic for readers but not durable. Need `Sync()` before rename. | Added. One `writeAtomic` helper, three call sites. | **yes** — §0.3, §13.3 |
| R9 | Detached spawn in Go | §7.2 step 7 describes Node's `{detached:true, stdio:'ignore'}` only | go-libs S4 + test-contract G4: Go needs `SysProcAttr{Setsid:true}`, nil std fds, `Release()`, never `Wait()` | Added the Go recipe and the three traps. | **yes** — §7.2 |
| R10 | fzf exit codes | §10.1/§12 state them as **bash** codes | go-libs S5: after the port there is no bash. Use fzf's own constants; code 2 is a user error (bad `TMUX_FZF_OPTIONS`). | Added a Go note. | **yes** — §12 |
| R11 | Our fzf options as argv | §10.2 still shows `--delimiter=" @ "` with literal quotes | §0.5 says pass separate argv elements | The two sections disagreed. §10.2 as written would reproduce the §0.9.2 quote bug. Added an explicit argv table. | **yes** — new §10.2.1 |
| R12 | The prompt pane must be killed | §9 / §9.2 never mention it | test-contract §5.1: `split-window` makes the new pane **active**, so it steals the test's keystrokes. Killing it is mandatory. Race G3 says Go makes this a guaranteed failure, not a flake. | Added the full 8-step order, including the pane-id capture and the kill. | **yes** — new §9.2.1 |
| R13 | FIFO creation timing | §9 lists `rm -f` then `mkfifo` as external commands, no timing | test-contract R1-R4: must exist inside ~200 ms, before `.envs` sourcing, or Python creates a regular file at that path | Added as binding. Use `syscall.Mkfifo`, not a shell. | **yes** — §9.2.1 |
| R14 | Regex compilation | §11.3.1 gives the class, not where to compile it | go-libs: compile once at package level; it is on the keypress path | Added a note. | **yes** — §11.3.1 |

### 1.2 Gaps — things no document answered

| # | Gap | What I did |
|---|---|---|
| G1 | The 26 test sites still point at `session-zx.py`, which does not exist. `pytest` fails at the first assertion today. | Left the tests untouched — it is not my task. It is **commit 1** in §5 below. Verified the failure is exactly `assert os.path.exists("session-zx.py")`. |
| G2 | Nothing said whether the Docker image should also carry a fallback binary. | Decided **no**. `COPY --from=…` into `/app` is shadowed by the bind mount anyway, and building Go inside the test image would slow every test-image rebuild. A missing binary fails loudly, which is what we want. |
| G3 | Both containers run as root and write into the bind mount. | Accepted. On this host Docker maps ownership back to `yu` (verified: the built binary is `-rwxrwxr-x yu yu`). If that ever changes, add `user:` to the compose services. |
| G4 | O-2, O-3, O-4, O-5, O-6, O-7 in SPEC are still open owner questions. | Not touched. They do not block the skeleton. O-4 is effectively answered by using `os.Args` ("argument present = argument given"), but the owner should still confirm. |

---

## 2. File layout

Flat `package main` at the repo root. No `cmd/`, no `internal/`, no layers.
The previous Python attempt used 34 files and 6 layers. This is 8 files and 0 layers.

### 2.1 Production files

| File | Responsibility | ~Lines | Key functions |
|---|---|---|---|
| `main.go` | Startup (§1), argv (§1.2), the action router (§2) in the exact `.mjs` order, and one small handler per action (§3). | 380 | `main`, `route`, `actionMenu`, `actionPopup`, `actionReloadSessions`, `actionKillSingleFromLine`, `actionSwitchFromLine`, `actionDelayedSwitch`, `actionKillSingle`, `actionNew`, `actionWorktreeSwitch`, `actionCapitalSwitch`, `actionSwitch`, `actionRename`, `actionKill`, `actionDetach` |
| `tmux.go` | Every external process call: tmux, git. Holds the `runner` func type — seam 1 of 2. | 180 | `execRun`, `tmuxCurrentSession`, `tmuxListSessions`, `tmuxListPanePaths`, `tmuxSwitchClient`, `tmuxKillSession`, `tmuxNewSessionDetached`, `tmuxRenameSession`, `tmuxDetachClient`, `tmuxHasSession`, `tmuxDisplayMessage`, `tmuxDisplayPopup`, `tmuxSplitPrompt`, `tmuxKillPane`, `gitWorktrees` |
| `sessions.go` | Building, ordering and filtering the session list (§4.1, §4.2, §6.3, §3.10). | 200 | `getSessionsList`, `orderByFrecency`, `selectorItems`, `filterCapital`, `filterByWorktrees` |
| `text.go` | Pure string helpers and all validators (§4.3-§4.7, §11). No I/O. | 180 | `parseLines`, `dedupe`, `addNumberPrefixes`, `normalizeAtColumns`, `extractSessionName`, `parseTargets`, `splitShellWords`, `joinShellWords`, `assertValidSessionName`, `assertValidAction`, `assertValidHeader`, `assertValidFzfOptions`, `assertValidItemsArray` |
| `fzf.go` | Building the fzf argv and running it (§10). Bindings, headers, exit codes. Holds the `fzfRunner` func type — seam 2 of 2, see §2.1.1. | 180 | `buildFzfArgv`, `runFzf`, `execFzf`, `switchBindings`, `previewBindings`, `numberBindings` |
| `state.go` | The two JSON state files plus the atomic write they share: frecency (§0.3, §5) and debounce (§7). | 230 | `writeAtomic`, `loadFrecency`, `saveFrecency`, `recordSelection`, `score`, `readDebounce`, `writeDebounce`, `newToken`, `scheduleSessionSwitch`, `handleDelayedSwitch` |
| `prompt.go` | The FIFO session-name prompt for `new` and `rename` (§9, §9.2.1, Q8). | 110 | `promptSessionName`, `makeFifo`, `readFirstLine` |
| `log.go` | The event log and its in-place rotation (§13, M10 fix). | 110 | `logEvent`, `rotate`, `trimLines` |
| **Total** | | **~1370** | |

### 2.1.1 The two seams — a deliberate decision, not creeping abstraction

The program has **exactly two** function-type seams and **zero** interfaces.
The second one was added on purpose, reviewed, and approved. Here is why.

| Seam | Type | File | Used for |
|---|---|---|---|
| 1 | `type runner func(argv ...string) (stdout string, err error)` | `tmux.go`, `var run runner = execRun` | every tmux and git call, plus the `bash -lc` used by `sourceEnv` |
| 2 | `type fzfRunner func(argv []string, stdin string) (stdout, stderr string, code int, err error)` | `fzf.go`, `var runFzfCmd fzfRunner = execFzf` | fzf, and nothing else |

`runner` cannot carry fzf. fzf needs four things it has no room for:

| # | Need | Why `runner` cannot do it |
|---|---|---|
| 1 | items on **stdin** | `runner` takes argv only; the items are a data stream, not an argument, and there are up to 10000 of them (§11.5) |
| 2 | the selection from **stdout** | this part `runner` does handle |
| 3 | fzf's **stderr**, kept separate | log message 17 prints it verbatim (SPEC §13.2). `execRun` folds stderr into the error text, so it can only ever be read back out of a formatted string |
| 4 | the **exit code** as a value | SPEC §12: `0`, `1` and `130` are all NORMAL and all yield stdout; `2` and everything else are errors. `runner` returns `error`, so "normal" and "failed" would have to be told apart by parsing an error message |

The alternative was to widen `runner` to seven return values for the benefit of
one caller, or to encode the exit code into an error string and parse it back.
Both are worse than a second three-line type.

**The abstraction budget is now spent.** Two func types, no interfaces, no third
seam. Rule 3 of §6 still stands: do not add `SessionKiller`, `SessionSwitcher`
or any other per-operation interface. If a future feature seems to need a third
seam, it needs a written justification in this file first.

### 2.2 Test files (Go unit tests, stdlib `testing` only)

| File | Covers |
|---|---|
| `text_test.go` | shell split/join, `extractSessionName`, `addNumberPrefixes` (including the M12 `[work]` case), `parseTargets` (including the M14 substring case), `dedupe`, the session-name regex incl. the exotic whitespace |
| `sessions_test.go` | `columnFormat`, `orderByFrecency` stability, `filterCapital`, `filterByWorktrees` |
| `state_test.go` | score buckets and their `<` boundaries, the 10-timestamp cap, broken/missing JSON = empty, `writeAtomic`, token format |
| `fzf_test.go` | the exact argv order of `buildFzfArgv`, binding strings, quoting of a path with a space or a `'` |
| `log_test.go` | `trimLines`: the M10 wipe bug, the one-huge-line case, the line-longer-than-max case |
| `tmux_fake_test.go` | the fake `runner` shared by the other tests |

Everything above runs with **no tmux, no fzf, no processes**.
The 43 Python integration tests stay as they are (decision D2).

### 2.3 Why each file exists (justification beyond the minimum)

The absolute minimum is one file. I added seven, and each one earns its place:

| File | Why it is separate |
|---|---|
| `tmux.go` | It is the only file that touches `os/exec`. Keeping it alone is what makes every other file unit-testable. This is the boundary that matters. |
| `text.go` | Pure functions, zero dependencies. The largest block of table tests lives against it. Mixing it into `main.go` would hide that. |
| `state.go` | Two files, one atomic-write helper, one shared "broken file = empty state" rule. Splitting frecency and debounce into two files would duplicate that rule. |
| `prompt.go` | The highest-risk code in the port (test-contract ranks it #1). It has an 8-step ordering contract. It deserves to be findable. |
| `log.go` | Has its own failure policy ("swallow everything") that must not leak into the rest of the program. |
| `fzf.go` | The argv builder is the second-highest-risk item (the §0.9.2 quote trap). Isolating it makes the argv order reviewable at a glance. |
| `sessions.go` | Otherwise `main.go` passes 500 lines and the router stops being readable. |

Nothing else gets its own file. In particular there is **no** `config.go`, no `errors.go`,
no `types.go`, no `util.go`.

---

## 3. Dependency sketch

```
                       main.go
      (startup, argv, router, 15 action handlers)
        |        |        |        |        |
        v        v        v        v        v
  sessions.go  fzf.go  state.go  prompt.go  log.go
        |   \     |        |        |
        |    \    |        |        |
        v     v   v        v        v
      text.go     +----> tmux.go <--+
    (pure, no deps)   (runner seam:
                       the only os/exec)
```

Rules:

| Rule | Detail |
|---|---|
| `text.go` imports nothing from this program | pure functions + stdlib + `shellquote` |
| Only three files import `os/exec` | `tmux.go` (tmux, git, and the `bash -lc` of `sourceEnv`), `fzf.go` (fzf needs stdin, a separate stderr and the exit code — §2.1.1), and `state.go` (the detached `delayed-switch` spawn, which needs `SysProcAttr`). No other file may. |
| `log.go` imports nothing from this program | so any file can log without a cycle |
| Exactly two abstractions exist | `runner` (`var run`) for tmux/git and `fzfRunner` (`var runFzfCmd`) for fzf. Tests set both to fakes. Nothing else. See §2.1.1 for why the second one is not creeping abstraction. |
| No struct is passed around as a "context" or "app" object | package-level `appDir`, `logPath`, `selfPath` are set once in `main` |

**There is no interface hierarchy and no DI.** The two func types are the only seams,
and they exist for exactly one reason: unit tests without a tmux server and without fzf.

---

## 4. Build and test — Docker only

Go, Python, `uv` and `pytest` never run on the host. A hook enforces this.

```bash
# compile the binary into ./session-zx (host) = /app/session-zx (container)
docker compose run --rm build

# Go unit tests
docker compose run --rm build go test ./...

# format and vet
docker compose run --rm build gofmt -w .
docker compose run --rm build go vet ./...

# add or update a dependency
docker compose run --rm build go mod tidy

# the 43 Python integration tests (build first!)
docker compose run --rm test

# one Python test
docker compose run --rm test pytest tests/test_script_executes.py -x -q

# rebuild the images (only after Dockerfile or dependency changes)
docker compose build
```

Facts about this setup:

| Item | Value |
|---|---|
| Builder image | `golang:1.26-bookworm` (verified `go version go1.26.5 linux/amd64`) |
| `go.mod` floor | `go 1.25` — Go supports the two newest majors, so 1.25 and 1.26 get security fixes |
| Production dependencies | exactly one: `github.com/kballard/go-shellquote` |
| Binary | `CGO_ENABLED=0`, `-trimpath`, static ELF, ~2.7 MB |
| Test image | `python:3.11-slim` + tmux 3.5a + **fzf 0.60.3 pinned from the release tarball** + uv + pytest |
| Node | **removed.** No test needs it. `session-zx.mjs` stays in the repo as the reference. |
| Caches | named volumes `gomodcache` (`/go/pkg/mod`) and `gobuildcache` (`/root/.cache/go-build`) — a warm rebuild is about a second |
| Bind mount | `.:/app`. The binary is built **through** the mount, so it is not shadowed. |

Why the binary must be `/app/session-zx` and nowhere else: `tests/conftest.py:37` deletes
`/app/.session-frecency` between tests. `<appDir>` is the directory holding the binary
(SPEC §0.1). Move the binary and that cleanup silently stops working, and ordering tests go
flaky. See SPEC §0.55.

### 4.1 Recording a test run (optional, OFF by default)

You cannot watch the fzf popup with `tmux capture-pane`. A popup is a **per-client
overlay**, so it is not in any pane. And you must never attach a second tmux client to
look: a second client still would not see the overlay, and it can make the binary's
`display-popup` open on the *wrong* client, because tmux picks the target by last activity.

The only terminal that sees the popup is the pty of the tmux client that `pexpect` owns.
So we record that pty. When recording is on, `TmuxSession.launch()` wraps the tmux command:

```
asciinema rec -q --overwrite -c "tmux new-session -s test_session ..." <file>.cast
```

asciinema owns the inner pty, writes every byte to the `.cast` file and passes it through,
so `pexpect` and `expect()` keep working. No second tmux client is added.

```bash
# record every test (adds ~0 config; RECORD_CAST=1 is set by the service)
docker compose run --rm test-record

# record one test
docker compose run --rm test-record pytest tests/test_capital_switch.py -q

# play a recording back, on the host
asciinema play test_output/casts/tests_test_capital_switch_py_test_capital_switch_basic.cast
```

Facts:

| Item | Value |
|---|---|
| Switch | env var `RECORD_CAST=1`. Unset, `""` or `0` means no recording and no asciinema process at all. |
| Files | one per test, `test_output/casts/<nodeid>.cast`, name taken from the pytest node id. `test_output/` is git-ignored. |
| Format | asciicast v3 (asciinema 3.2.1, pinned in the `Dockerfile`, ~8 MB static binary) |
| Scope | only tests that use the `tmux` fixture. Tests that spawn their own process are not recorded. |
| Cost | ~4:13 → ~5:12 for the full suite (+23%). asciinema asks the outer terminal about itself and waits ~1s for a reply pexpect never sends, so each recorded launch costs about one extra second. |

This is a debugging aid, not a product feature. The `test` service is unchanged.

### 4.2 Turning recordings into a README animation

The `.cast` files from §4.1 are also the source of the demo animation. The path is
`.cast` → GIF (`agg`) → animated WebP (Pillow):

```bash
# one clip -> test_output/webp/<name>.gif and .webp
docker compose run --rm media scripts/cast2webp.sh \
  tests_test_switch_popup_workflows_py_test_popup_switch_by_typing_full_name

# the README demo: 4 clips, played one after another, in this order
docker compose run --rm media scripts/cast2webp.sh \
  tests_test_switch_popup_workflows_py_test_popup_switch_by_typing_full_name \
  tests_test_switch_popup_workflows_py_test_popup_switch_ctrl_n_preview_moves_client \
  tests_test_session_mutations_py_test_kill_multiple_sessions_with_tab \
  tests_test_action_menu_paths_py_test_action_menu_selects_switch_then_switches
# -> test_output/webp/demo-combined.webp   (691x490, ~27s, ~92 KB)
```

Give two or more casts and you also get the combined file. The clips are joined at
the **frame** level, not at the `.cast` level: each cast is rendered by `agg` on its
own, then Pillow appends the frames and their delays. All casts are 80x24, so the
frames match; `scripts/gif2webp.py` fails loudly on a size mismatch instead of
rescaling. Between clips it holds the closing screen for an extra `GAP_MS`, which is
the beat that tells the viewer one workflow ended.

Facts:

| Item | Value |
|---|---|
| Image | separate `media` stage in the `Dockerfile`, and the `media` compose service. `agg` and Pillow never enter the `test` image. |
| Tools | `agg` 1.9.0 (pinned, static musl binary, installed like asciinema), Pillow 12.3.0 (pinned) |
| Script | `scripts/cast2webp.sh` (agg + pacing flags) calls `scripts/gif2webp.py` (Pillow) |
| Output | `test_output/webp/` — git-ignored, like the casts |
| Pacing | `IDLE=1.2` caps every pause; `SPEED=1.0`, because the fzf list has to stay readable. Override either on the command line. |
| Beat | `GAP_MS=1000` on top of `agg --last-frame-duration 1`, so each clip ends on a 2s hold. |

Why Pillow and not `ffmpeg` for the WebP step: `ffmpeg` re-times an animation to a
constant frame rate. A terminal recording is the opposite of constant — a burst of
frames while text appears, then a long hold — so flattening it destroys the pacing.
Pillow copies each frame's own delay across unchanged.

Known quirk: Pillow's WebP *reader* reports `duration` as 0 for every frame. The
delays really are in the file (they are in the `ANMF` chunks, and browsers play them
correctly); only the read-back is lossy. Do not "fix" a file based on that.

---

## 5. Implementation order

Nine commits. Each one leaves the tree building and the tests runnable.

| # | Commit | Files | Why here |
|---|---|---|---|
| 1 | `test: repoint the suite at the session-zx binary` | 26 sites in `tests/**` (`/app/session-zx.py` → `/app/session-zx`, `./session-zx.py` → `./session-zx`), plus the docstring at `test_script_executes.py:1` | **Do this first.** Until it is done every run stops at `assert os.path.exists("session-zx.py")` and you get no signal at all. |
| 2 | `feat(go): pure helpers and validators` | `text.go` + `text_test.go` | No dependencies. Full test coverage on day one. Everything else uses it. |
| 3 | `feat(go): log file and rotation` | `log.go` + `log_test.go` | Small, self-contained, and the M10 fix is pure logic. You want logging before you debug anything else. |
| 4 | `feat(go): tmux and git command wrappers` | `tmux.go` + `tmux_fake_test.go` | Unlocks everything below. Check every argv against SPEC §0.9.1 row by row. |
| 5 | `feat(go): session list, ordering and frecency` | `sessions.go`, `state.go` (frecency half) + tests | Makes `reload-sessions` possible. |
| 6 | `feat(go): fzf argv builder and runner; reload-sessions works` | `fzf.go` + `fzf_test.go`, plus `main.go` routing for `reload-sessions`, `switch`, `popup-switch`, the action menu | **First real green.** After this commit `test_script_functionality.py` (4 tests), `test_script_executes.py` (4), `test_action_menu_paths.py` (3), `test_mini_mechanics.py` (5) and `test_switch_filter_navigation.py` (5 of 7) should pass — about 21 of 43. |
| 7 | `feat(go): kill, detach, rename target selection` | `main.go` handlers, `sessions.go` attached-session fix (Q3) | Adds `test_session_mutations.py` `kill`, multi-kill, `detach` — 3 more. |
| 8 | `feat(go): debounce and delayed switch` | `state.go` (debounce half), `main.go` helper actions | Adds the 6 Ctrl+N/P tests and the 2 DEL tests. Get the detached-spawn recipe (§7.2) exactly right or `test_script_executes.py:32` breaks. |
| 9 | `feat(go): FIFO name prompt; new and rename work` | `prompt.go`, `main.go` | Highest risk, so last, when everything else is green. Follow SPEC §9.2.1 step by step. Then add the missing test that drives the **real** prompt (SPEC Q8 asks for it). |

Suggested check after every commit:

```bash
docker compose run --rm build go vet ./...
docker compose run --rm build go test ./...
docker compose run --rm build
docker compose run --rm test
```

### 5.1 Highest-risk items, in order

From test-contract §8, cross-checked against this design:

| Rank | Item | Where |
|---|---|---|
| 1 | The FIFO prompt: creation inside 200 ms, redirect on the last `printf` only, read the first line, **kill the prompt pane** | `prompt.go`, SPEC §9.2.1 |
| 2 | The shell-quote trap: `-F '#S @ #{session_windows} windows'` must lose its quotes | `tmux.go`, SPEC §0.9.2 |
| 3 | Debounce: token compare, detached grandchild, ~300 ms of real budget | `state.go`, SPEC §7 |
| 4 | DEL kill + reload inside one fzf instance | `fzf.go` bindings + `reload-sessions` row shape |
| 5 | Stable sort. `sort.Slice` is **not** stable; use `sort.SliceStable` | `sessions.go`, SPEC §4.1 step 6 |

---

## 6. Do not do this

Aimed at the implementer. Every item is a real mistake from the abandoned Python attempt
(34 files, 6 layers, ~2400 lines) or a trap the three input documents flagged.

| # | Do not | Instead |
|---|---|---|
| 1 | Do **not** add a `domain/`, `ports/`, `adapters/`, `usecases/` or `app/` directory. | One flat `package main` at the repo root. |
| 2 | Do **not** build a DI container, a `Container` struct, or a `New*` constructor chain. | Package-level `var run runner` and three package-level path strings, set once in `main`. |
| 3 | Do **not** define an interface for each operation (`SessionKiller`, `SessionSwitcher`, …). | Two func types, `runner` and `fzfRunner` (§2.1.1). That is the whole abstraction budget, and it is spent. |
| 4 | Do **not** write forwarder methods that only call another method. | Call the function directly. |
| 5 | Do **not** create one file per function or one file per action. | 8 files. The table in §2.1 is the whole list. Adding a 9th needs a reason written in this file. |
| 6 | Do **not** add a dependency without checking §2 of `go-libs.md` first. | It says stdlib for JSON, atomic write, log rotation, exec, detached spawn, uid, tokens, and tests. One production dependency exists on purpose. |
| 7 | Do **not** copy a quote out of `SPEC.md` into an `exec.Command` argument. | Every quote in SPEC is a **shell** quote. `-F '#S @ …'` becomes the argv element `#S @ …`. SPEC §0.9.1 has the full table. |
| 8 | Do **not** run anything through `bash -c`, `sh -c`, `eval` or a heredoc. | `exec.Command` with an argv slice. The two real exceptions are the `.envs` login shell (§0.4) and the tmux prompt pane script (§9.2). |
| 9 | Do **not** use `sort.Slice` for the frecency order. | `sort.SliceStable`. Ties must keep tmux's own order. |
| 10 | Do **not** use Go's `\s` in the session-name regex. | Use the exact class in SPEC §11.3.1, compiled once at package level. |
| 11 | Do **not** let the `delayed-switch` grandchild inherit stdio. | `nil` for all three fds and `SysProcAttr{Setsid: true}`. Otherwise `pexpect` never sees EOF. |
| 12 | Do **not** shorten the FIFO read timeout to "something reasonable". | 60 s. Go arrives in milliseconds and then waits ~2.0 s for the test to write. |
| 13 | Do **not** skip `tmux kill-pane` after reading the FIFO. | The prompt pane is the **active** pane and will eat the test's keystrokes. |
| 14 | Do **not** move the binary out of the repo root. | `<appDir>` must stay `/app`. See SPEC §0.55. |
| 15 | Do **not** run `go`, `python`, `python3`, `uv` or `pytest` on the host. | `docker compose run --rm build …` / `docker compose run --rm test …`. A hook blocks the host commands by design. |
| 16 | Do **not** let a logging error, a broken JSON state file, or a missing frecency directory stop the program. | Swallow it and carry on. SPEC §0.3, §7.1, §13. |
| 17 | Do **not** "tidy up" the surviving quirks. Q1, Q13, Q14, Q15 are **KEEP**. | Only the ones labelled FIX get fixed. The owner uses the `1..9` positions daily. |
