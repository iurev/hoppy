# SPEC — `session-zx.mjs` behavior specification

Source of truth: `/home/yu/my/hoppy/session-zx.mjs` (1691 lines).
All line cites below are `session-zx.mjs:LINE`.
Goal: a Go developer can reimplement this exactly, without reading the `.mjs`.

Language note: simple English, short sentences (project rule).

---

## 0. Port decisions (BINDING)

These decisions are FINAL. The project owner made them.
**The Go port MUST follow them.**
If any later section of this document disagrees with this section, **this section wins**.

`<appDir>` below means the directory that holds the Go binary (symlinks resolved).
It replaces `scriptDir` from the `.mjs` (`session-zx.mjs:21`).

### 0.1 Decision table

| # | Topic | Decision |
|---|---|---|
| D1 | Target language | **Go.** Full feature parity with `session-zx.mjs`, except where a decision below says otherwise. |
| D2 | Integration tests | The existing Python tests in `tests/` **stay** and must pass against the Go binary. Do not rewrite them in Go. |
| D3 | Q1 / Q13 — current session in the switch list | **KEEP TODAY'S BEHAVIOR.** The current session stays visible and stays pinned to the top as `[1]`. The `1..9` shortcuts keep their present positions. `TMUX_FZF_SWITCH_CURRENT` is dead: **DELETE it. Do not implement it.** Q1 and Q13 are re-marked **KEEP (owner decision)**. |
| D4 | Logging | Keep the same log file path (`<appDir>/session-zx.log`) and the same line format. Log only about **20 KEY events** (list in §13.2). Do **NOT** port all 167 `logEvent` sites. Also fix the rotation wipe bug (§13.3, M10). |
| D5 | Kaomoji preview pane | **DROP.** Remove the fzf `--preview` kaomoji feature, `pickPreviewKaomoji`, `KAOMOJI_PREVIEW_TEXT` and `TMUX_FZF_PREVIEW_OPTIONS`. This makes quirk **Q2 moot** — there is nothing left to fix. Read §0.2: this does **not** touch Ctrl+N / Ctrl+P. |
| D6 | Frecency | Keep the exact same score buckets (100 / 50 / 10 / 1, §5.2). Use a **NEW simple JSON format that we own**. Do NOT reverse-engineer the `@getstation/frecency` library format. There is no old data to preserve. New path and schema: §0.3. |
| D7 | Bugs | Fix every quirk marked **FIX**. In particular `new`, `rename` (Q8) and `detach` (Q3) are broken today and **MUST work** in Go. |
| D8 | Q5 (env leak) | Apply the fix, but **PRESERVE `PATH` behavior** so `tmux`, `git` and `fzf` still resolve. Rules in §0.4. |
| D9 | Q16 (fzf options) | `TMUX_FZF_BIN` and `TMUX_FZF_OPTIONS` are raw **SHELL strings** today and are `eval`ed (`session-zx.mjs:909`). They MUST keep working, e.g. `TMUX_FZF_BIN="fzf-tmux -p 80%"`. A **POSIX shell-word splitter** is required. Exact semantics in §0.5. |

### 0.2 "Preview" means two different things — do not mix them up

This is the easiest mistake to make in this port. Read the whole table.

| Feature | What it is (source) | Decision |
|---|---|---|
| **Kaomoji preview pane** | `pickPreviewKaomoji` (1429-1468); `KAOMOJI_PREVIEW_TEXT` (1418); `TMUX_FZF_PREVIEW_OPTIONS` (1006, 1014-1015, 1416); the `includePreview` flag of `runFzf` / `selectSessions` / `selectDetachSessions`; the fzf `--preview` and `--preview-window` options. It draws random ASCII faces in a side pane. It does **not** work today (Q2). | **DROP entirely.** Do not port any of it. Q2 becomes moot. |
| **Ctrl+N / Ctrl+P session preview** | The bindings `ctrl-n:down+execute-silent(<script> switch-from-line {})` and `ctrl-p:up+…` (331-332, 396-397, 482-483); the `switch-from-line` action (§3.5); `scheduleSessionSwitch` (§7.2); the `delayed-switch` action and `handleDelayedSwitch` (§7.3); the debounce state file (§7.1); `SESSION_SWITCH_DEBOUNCE_MS`. Moving the cursor really switches the tmux client after a short delay, so the user "previews" the session for real. | **KEEP IN FULL.** Every part of it. D5 does **not** touch this. |

Said again, because it is easy to misread:
**dropping the kaomoji pane does NOT drop Ctrl+N / Ctrl+P.**
The debounce / delayed-switch machinery (§7) is kept exactly as specified.
The fzf headers still contain the text `Ctrl+N/P to preview.` — keep that wording exactly (§10.4).

What dropping the kaomoji pane changes:

| Area | Change |
|---|---|
| `runFzf`, `selectSessions`, `selectDetachSessions` | the `includePreview` parameter disappears |
| `buildFzfRunCommand` (§10.3) | loses its third part and its `TMUX_FZF_PREVIEW_OPTIONS` validation |
| `ensureEnvDefaults` (§8.2) | no longer does anything for preview |
| §8.4 `pickPreviewKaomoji` | dead. Kept in this document only as history. `KaomojiList/kaomojis.json` is never read. |
| `TMUX_FZF_PREVIEW_OPTIONS` | no longer read, no longer validated, no longer documented as supported |

### 0.3 Frecency storage — NEW format (BINDING)

| Item | Value |
|---|---|
| Directory | `<appDir>/.session-frecency` (same directory name as today) |
| File | `<appDir>/.session-frecency/sessions.json` |
| Directory mode | `0700` |
| File mode | `0600` |
| Encoding | UTF-8 JSON |

Exact schema:

```json
{
  "version": 1,
  "sessions": {
    "mysession": { "selectedAt": [1721476800000, 1721480400000] },
    "other":     { "selectedAt": [1721390000000] }
  }
}
```

Rules:

| Rule | Value |
|---|---|
| `version` | integer, always `1`. If the file has any other value, treat the whole file as empty. |
| `sessions` | object. Key = the exact tmux session name. Value = one record. |
| `selectedAt` | array of integers. Epoch **milliseconds**. Oldest first, newest last. |
| Cap | keep at most **10** timestamps per session. When appending an 11th, drop the oldest. |
| Missing dir / missing file / unreadable / bad JSON | treat as empty. Every score is 0. **Never crash.** |
| Write | create the directory if needed. Write to a temp file **in the same directory**, `Sync()` it, `Close()` it, then `rename` over the target (atomic). The `Sync()` is not optional: without it a power loss can leave the renamed file full of zeros. We deliberately skip the extra directory `fsync`. |
| When to write | only after a **successful** `tmux switch-client`, in `switch`, `worktree-switch` and `capital-switch`. Unchanged — see §5.3. |
| Extra fields | do not write `timesSelected` or anything else. Nothing reads it. |

Score buckets are unchanged: see §5.2.

### 0.4 Q5 fix — env import, with `PATH` preserved

The constraint. Today `sourceEnv` copies the **whole** login environment into the process
(`session-zx.mjs:1383-1385`). The `PATH` it copies is the login shell's `PATH`, and that is what
later finds `tmux`, `git` and `fzf`. If the port simply stops copying `PATH`, tool lookup can
break on machines where tmux starts the process with a thin `PATH`.

Required behaviour for the port:

| Step | Rule |
|---|---|
| 1 | Find the `.envs` file with the same precedence as §8.1. If no candidate exists, **do nothing at all** (today's behaviour). |
| 2 | Ask the login shell for its environment **before** sourcing and **after** sourcing the file. |
| 3 | Apply only keys that are **new** or whose **value changed** between the two. Do not apply unchanged keys. This is the Q5 fix. |
| 4 | **`PATH` is the exception: always apply the login shell's `PATH`**, even when the diff says it did not change. Today's behaviour depends on this. Without it `tmux`, `git` or `fzf` may not be found. |
| 5 | Never apply these process-local keys, even if they changed: `_`, `SHLVL`, `PWD`, `OLDPWD`, `SHELL`, `HOME`, `USER`, `LOGNAME`, `TMUX`, `TMUX_PANE`. Copying them is exactly the Q5 bug. |
| 6 | Parsing of the `env` output is unchanged: split each line at the **first** `=`; skip lines with no `=` (§8.1 step 3). Multi-line values stay mangled — bug-compatible and acceptable. |

Ground truth today: `.envs` exists in neither location on this machine (§16), so `sourceEnv`
is currently a no-op. Verify step 4 on the real target machine before shipping.

### 0.5 fzf options are SHELL strings — required splitter

Today `buildFzfRunCommand` (§10.3) joins `TMUX_FZF_BIN` and `TMUX_FZF_OPTIONS` into one string
`TMUX_FZF_RUN`, and bash runs `eval "$TMUX_FZF_RUN"` (`session-zx.mjs:909`).
So both variables are **shell text**, not single argv elements. Users rely on this:

| Example value | Must still do |
|---|---|
| `TMUX_FZF_BIN="fzf-tmux -p 80%"` | run `fzf-tmux` with args `-p`, `80%` |
| `TMUX_FZF_OPTIONS="--multi --height 40%"` | add args `--multi`, `--height`, `40%` |
| `TMUX_FZF_OPTIONS="--bind 'ctrl-a:select-all'"` | add args `--bind`, `ctrl-a:select-all` (the single quotes group one word) |

Required splitter semantics — **POSIX `sh` word splitting of a command line**:

| Feature | Required? |
|---|---|
| unquoted space / tab / newline separates words | **yes** |
| single quotes `'…'` — content is literal, no escapes inside | **yes** |
| double quotes `"…"` — content is literal, but `\` escapes `"`, `\`, `` ` `` and `$` | **yes** |
| backslash outside quotes escapes the next character | **yes** |
| an empty variable produces zero words | **yes** |
| unbalanced quote | **error**: reject with a clear message, do not guess |
| variable expansion `$VAR` / `${VAR}` | **NO** — pass through as literal text |
| command substitution `` `…` `` / `$(…)` | **NO** — never run |
| globbing `*`, `?`, `[…]` | **NO** |
| redirection `>` `<` `\|`, `;`, `&&` | **NO** — plain characters, never interpreted |

This is the same as Python's `shlex.split(s, posix=True)` without comment handling.

**In Go use `github.com/kballard/go-shellquote` (`shellquote.Split`).**
It is the only candidate whose double-quote escape set is exactly the table above.
Do **not** use `github.com/google/shlex`: that repo has been archived (read-only) since
2019-12-02, and inside double quotes its backslash escapes **any** character, so `"a\b"`
becomes `ab` where the table requires `a\b`. Do not use `mattn/go-shellwords` either: it turns
`\t` / `\n` into real control characters and rejects a bare `(`, which fzf option strings such as
`--bind 'ctrl-a:execute(foo)'` contain all the time.
(Corrected 2026-08-07 after the Go library review. This is the one production dependency.)

This is a **deliberate narrowing** of today's `eval`. `eval` would expand and execute those
constructs. Nobody sets such values and running them is a security hole. Record it as the one
accepted difference from the `.mjs`.

How the fzf command line is built in Go:

| Part | Today (`.mjs`) | Go port |
|---|---|---|
| user's own `FZF_DEFAULT_OPTS` | prepended into the built option string (§10.2 part 1) | leave the variable in the child environment, unchanged. fzf reads it itself. Order is preserved: env options first, argv last, argv wins. |
| our own options (`--no-sort`, `--delimiter`, `--with-nth`, `--nth`, `--with-shell`, `--header`, `--bind …`) | appended into `FZF_DEFAULT_OPTS` as one shell string | pass as **separate argv elements**, with **no quotes of any kind** around the values. This removes the quoting bugs Q9 and Q17. Exact list in §10.2. |
| `TMUX_FZF_BIN` + `TMUX_FZF_OPTIONS` | joined into `TMUX_FZF_RUN`, then `eval`ed | shell-split as above. The words become the **head** of the argv. |
| items | fed through a quoted heredoc into a bash pipeline | write to fzf's **stdin** directly. No shell, no heredoc, no `eval`. |
| empty result | — | if the split of `TMUX_FZF_BIN` + `TMUX_FZF_OPTIONS` yields zero words, fail with the existing message `TMUX_FZF_RUN command is empty.` |

One thing stays shell-ish: the value of `--bind` contains fzf's own mini-language, e.g.
`execute(<path> kill-single-from-line {})`. fzf parses it and runs the inner command through a
shell. So `<path>` must still be quoted for that shell. See Q17.

**CORRECTION (2026-08-07): fzf uses `$SHELL -c`, not `sh -c`.**
`src/util/util_unix.go` reads `os.Getenv("SHELL")` and only falls back to `sh` when it is empty.
fzf has done this since 0.11.3. If the user's `$SHELL` is `fish`, `nushell` or `csh`, POSIX
quoting of our path is simply wrong.

**Required fix: always add `--with-shell`, `sh` to our own argv** (two separate argv elements;
fzf ≥ 0.51.0). Then the inner command really is run by POSIX `sh`, and `shellquote.Join` is
provably correct. This makes the "`sh -c`" wording in §0.9.3 and Q17 true instead of hopeful.
It also sets the project's minimum fzf version to **0.51.0** (see O-1).

### 0.55 Binary name and path (BINDING — added 2026-08-07)

`<appDir>` is not free to choose. The Python test suite pins it.

| Item | Value | Why |
|---|---|---|
| Binary name | `session-zx` (no extension) | short, no spaces, no shell metacharacters, so the fzf `--bind` path stays clean |
| Repo path | `/home/yu/my/hoppy/session-zx` | the repo root is bind-mounted at `/app` |
| Container path | `/app/session-zx` | so `<appDir>` = `/app` |
| Frecency dir | `/app/.session-frecency` | `tests/conftest.py:37` deletes exactly this path between tests |
| Log file | `/app/session-zx.log` | already in `.gitignore` |

Do **not** install it to `/usr/local/bin`. That moves `<appDir>` and `conftest.py:37` silently
stops cleaning frecency, so ordering tests go flaky.

The binary is compiled **through** the bind mount (`docker compose run --rm build`), because a
build-time `COPY` into `/app` is shadowed by the mount at run time.

### 0.6 What is DELETED from the port

| Thing | Reason |
|---|---|
| `TMUX_FZF_SWITCH_CURRENT` and the `excludeCurrent` variable | D3 — dead today, deleted, not implemented |
| kaomoji preview: `pickPreviewKaomoji`, `KAOMOJI_PREVIEW_TEXT`, `TMUX_FZF_PREVIEW_OPTIONS`, `includePreview` | D5 |
| `TMUX_FZF_SESSION_FORMAT` | Q4 — validated but never used. Drop the variable and both validations. |
| `extractSessionNameFromLine` (474-477) | Q10 — dead code |
| the empty-items guard in `runFzf` (888-891) | Q11 — dead code |
| the `@getstation/frecency` on-disk format and `node-localstorage` | D6 |
| about 147 of the 167 `logEvent` calls | D4 |

---

## 0.9 CRITICAL — the quotes in this document are SHELL quotes (M1)

**Read this before you write a single `exec.Command`.**

`session-zx.mjs` uses zx (`zx ^7.2.3`, see `package.json`). In zx 7 a `` $`…` `` template is
**not** executed directly. zx builds one command **string** and hands it to a shell:

```
/bin/bash -c 'set -euo pipefail;<the built command string>'
```

Bash then parses that string. **Bash removes the quotes.** The program never sees them.

Two rules follow:

| Rule | Meaning for the Go port |
|---|---|
| **R1** | Any `'…'` or `"…"` written **literally inside the template** is *shell* quoting. It only groups words. Bash strips it. In Go you pass the **content** as one argv element, with **no quotes at all**. |
| **R2** | Any `${value}` interpolation is passed through zx's `quote()` helper, which shell-quotes it (`$'…'` form when needed). After bash parses it, the value arrives as **exactly one argv element**, whatever it contains. In Go you pass the value as one argv element. |

### 0.9.1 Translation table — zx template → real argv → Go call

| # | zx template as written (line) | ACTUAL argv the program receives | Correct Go call |
|---|---|---|---|
| 1 | `` $`tmux list-sessions -F '#S @ #{session_windows} windows'` `` (1077) | `tmux` / `list-sessions` / `-F` / `#S @ #{session_windows} windows` | `exec.Command("tmux", "list-sessions", "-F", "#S @ #{session_windows} windows")` |
| 2 | `` $`tmux list-panes -a -F '#{session_name}\t#{pane_current_path}'` `` (1174) | `tmux` / `list-panes` / `-a` / `-F` / `#{session_name}<TAB>#{pane_current_path}` | `exec.Command("tmux", "list-panes", "-a", "-F", "#{session_name}\t#{pane_current_path}")` |
| 3 | `` $`tmux display-message -p '#S'` `` (1350) | `tmux` / `display-message` / `-p` / `#S` | `exec.Command("tmux", "display-message", "-p", "#S")` |
| 4 | `` $`tmux display-message -p '#{pane_current_path}'` `` (296) | `tmux` / `display-message` / `-p` / `#{pane_current_path}` | `exec.Command("tmux", "display-message", "-p", "#{pane_current_path}")` |
| 5 | `` $`tmux display-message "Session ${sessionName} does not exist"` `` (182) | `tmux` / `display-message` / `Session <name> does not exist` — **3 elements**; the whole message is **one** element | `exec.Command("tmux", "display-message", "Session "+name+" does not exist")` |
| 6 | `` $`tmux display-message "Not in a git repository"` `` (304) | `tmux` / `display-message` / `Not in a git repository` | `exec.Command("tmux", "display-message", "Not in a git repository")` |
| 7 | `` $`tmux display-message "No sessions found for this project's worktrees"` `` (321) | `tmux` / `display-message` / `No sessions found for this project's worktrees` (the `'` is plain text) | `exec.Command("tmux", "display-message", "No sessions found for this project's worktrees")` |
| 8 | `` $`tmux display-message "No CAPITAL sessions found"` `` (389) | `tmux` / `display-message` / `No CAPITAL sessions found` | `exec.Command("tmux", "display-message", "No CAPITAL sessions found")` |
| 9 | `` $`tmux display-popup -E -w 60% -h 90% -x R -y C -T "SESSIONS" -b rounded ${scriptPath} switch` `` (61) | `tmux` / `display-popup` / `-E` / `-w` / `60%` / `-h` / `90%` / `-x` / `R` / `-y` / `C` / `-T` / `SESSIONS` / `-b` / `rounded` / `<path>` / `switch` | 17 separate strings. `SESSIONS` carries **no** quotes. |
| 10 | `` $`tmux kill-session -t ${sessionName}` `` (103, 239, 622) | `tmux` / `kill-session` / `-t` / `<name>` — one element even when the name has a space | `exec.Command("tmux", "kill-session", "-t", name)` |
| 11 | `` $`tmux rename-session -t ${targets[0]} ${sessionName}` `` (586) | `tmux` / `rename-session` / `-t` / `<old>` / `<new>` | `exec.Command("tmux", "rename-session", "-t", old, new)` |
| 12 | `` $`git -C ${dirPath} worktree list --porcelain` `` (1151) | `git` / `-C` / `<dirPath>` / `worktree` / `list` / `--porcelain` | `exec.Command("git", "-C", dir, "worktree", "list", "--porcelain")` |

Note on row 2: in a JavaScript template literal `\t` is a **real TAB character** (U+0009), not a
backslash followed by `t`. So tmux receives a real tab inside the format string. In Go, `"\t"`
in a double-quoted string is also a real tab, so the Go text above is correct as written.

### 0.9.2 What breaks if you copy the quotes

Suppose the port runs
`exec.Command("tmux","list-sessions","-F","'#S @ #{session_windows} windows'")`
— quotes kept by mistake. tmux then prints rows like:

```
'work @ 3 windows'
```

Then, quietly:

| Step | Result |
|---|---|
| `columnFormat` (§4.1 step 5) | keeps the quotes |
| `extractSessionName` (§4.4) | returns `'work` instead of `work` |
| frecency lookup (§5) | misses every session, so the order is wrong |
| `selectSessions` (§4.2) | cannot find the `"<currentSession> @ "` line, so the current session is not pinned |
| fzf `--delimiter=" @ "` | still matches, so the UI still *looks* almost right |

**Nothing throws.** That is why this is the highest-risk item in the whole port.

### 0.9.3 Where a shell IS genuinely involved

Four places really do take shell text. Do not confuse them with §0.9.1.

| Place | Why it is shell text |
|---|---|
| `FZF_DEFAULT_OPTS` | fzf itself splits this variable shell-style. See §0.5. |
| `TMUX_FZF_BIN` / `TMUX_FZF_OPTIONS` | user-supplied shell text. Must be shell-split. See §0.5 and Q16. |
| the fzf `--bind` value, e.g. `execute(<path> kill-single-from-line {})` | fzf parses it and runs the inner command with **`$SHELL -c`**, falling back to `sh` only when `$SHELL` is empty. We force POSIX `sh` by passing `--with-shell sh` (§0.5), and then quote `<path>` for `sh`. See Q17. |
| `tmux split-window … <command>` (1325) | tmux runs `<command>` through `/bin/sh -c`. This is exactly where Q8 goes wrong. |

---

## 1. Startup sequence (runs for EVERY invocation)

The script is an ES module. The top-level code runs in this exact order.

| # | Step | Line | Detail |
|---|---|---|---|
| 1 | `$.verbose = false` | 18 | No command echo to stderr. |
| 2 | Compute `scriptFilePath`, `scriptDir` | 20-21 | Absolute path of the script file and its directory. |
| 3 | Compute `logFilePath` | 22 | `<scriptDir>/session-zx.log` |
| 4 | Constants | 23-24 | `LOG_MAX_BYTES = 262144` (256*1024). `LOG_TRIM_TARGET = floor(262144*0.8) = 209715`. |
| 5 | Read `SESSION_SWITCH_DEBOUNCE_MS` | 26 | `parseInt(env, 10) \|\| 300`. **Read BEFORE `.envs` is sourced.** |
| 6 | Compute `sessionDebounceFile` | 27 | `/tmp/tmux-session-<uid>.json` (see §7). |
| 7 | Open frecency storage | 30-35 | Dir `<scriptDir>/.session-frecency`, key `tmux-sessions`. |
| 8 | `await sourceEnv()` | 37 | See §8.1. |
| 9 | `await ensureEnvDefaults()` | 38 | See §8.2. |
| 10 | `baseFzfDefaultOpts = env.FZF_DEFAULT_OPTS ?? ''` | 40 | Captured AFTER `.envs` sourcing. |
| 11 | `logEvent('script started')` | 41 | |
| 12 | `currentSession = getCurrentSession()` | 43 | Runs `tmux display-message -p '#S'` (argv: see §0.9.1 row 3). Fails hard if tmux is not reachable. Then it **validates** the answer — see below. |
| 13 | `logEvent('current session: <name>')` | 44 | |
| 14 | `excludeCurrent = !env.TMUX_FZF_SWITCH_CURRENT` | 46 | **Computed, logged, then never used.** See quirk Q1. **Go port: DELETE — decision D3.** |
| 15 | `action = argv._[0] ? String(argv._[0]) : await selectAction()` | 49 | If no positional argument, show the action menu (§3.1). |
| 16 | `logEvent('action selected: <action>')` | 50 | |
| 17 | If action is empty or `[cancel]` → log, `exit 0` | 52-55 | |

### 1.1 `getCurrentSession()` validates but never fails (M5)

`session-zx.mjs:1349-1362`. After `tmux display-message -p '#S'` the trimmed name is passed to
`assertValidSessionName` (§11.3). A failure is **not** thrown. It is only logged as:

```
Warning: Current session name is invalid: <message>
```

and the raw name is returned anyway. The comment in the source says: the name came from tmux
itself, so trust it. The Go port must copy this: warn, never fail. tmux allows names that
`assertValidSessionName` rejects (for example a name with a `.`), so this path is reachable.

### 1.2 Argument parsing and the `0` trap (M11)

`argv` comes from `zx` (minimist over `process.argv.slice(2)`), so `argv._[0]` is the
first positional argument and `argv._[1]` the second.
minimist converts pure-number arguments to **numbers**, hence the `String(...)` calls.

The script tests those values for **truthiness**, not for presence. In JavaScript the number `0`
is falsy. So a literal `0` argument behaves as if it were missing:

| Command | Line that decides | What actually happens |
|---|---|---|
| `session-zx.mjs 0` | 49 `argv._[0] ? … : selectAction()` | the action menu opens (§3.1), as if no argument was given |
| `session-zx.mjs kill-single 0` | 158 `if (!argv._[1])` | stderr `Error: Session name required for kill-single action`, exit 1 |
| `session-zx.mjs kill-single-from-line 0` | 97 | the line is treated as `''` → no kill, exit 0 |
| `session-zx.mjs switch-from-line 0` | 120 | the line is treated as `''` → `no session to process`, exit 0 |
| `session-zx.mjs delayed-switch 0` | 113 | the token is treated as `''` → skip, exit 0 |

A tmux session may legally be named `0`. Go has no falsy-number rule, so a literal Go port would
behave **differently** here. Decide once and follow it: the recommended Go rule is
"argument present = argument given", which also fixes the `0` session name. Note this in the
release notes; it is a small, deliberate difference.

Related, and also caused by argument parsing: a session name that starts with `-` may be read by
minimist as a flag, so `argv._[1]` is missing and the helper action becomes a no-op (§15).
`assertValidSessionName` allows a leading `-`.

---

## 2. Action routing order (CRITICAL)

The order matters. Some actions are handled **before** `assertValidAction`.
A Go port must keep this order to be bug-compatible.

| Order | Action | Line | Validated by `assertValidAction`? |
|---|---|---|---|
| 1 | `popup-switch` | 58 | No (handled earlier) |
| 2 | `popup-worktree-switch` | 67 | No |
| 3 | `popup-capital-switch` | 76 | No |
| 4 | `reload-sessions` | 85 | No |
| 5 | `kill-single-from-line` | 96 | No (**not in the valid-action list at all**) |
| 6 | `delayed-switch` | 112 | No (**not in the valid-action list at all**) |
| 7 | `switch-from-line` | 119 | No (**not in the valid-action list at all**) |
| — | **`assertValidAction(action)`** | 145-151 | Gate. On failure: log, print `Error: <msg>` to stderr, `exit 1`. |
| 8 | `kill-single` | 154 | Yes |
| — | `logEvent('action=<action>')` — unconditional, runs for every action that reaches this point | 258 | — (M6) |
| 9 | `new` | 260 | Yes |
| 10 | `worktree-switch` | 292 | Yes |
| 11 | `capital-switch` | 373 | Yes |
| — | `sessions = getSessionsList(...)` | 437 | Runs only for the actions below. |
| 12 | `switch` | 440 | Yes |
| 13 | `rename` | 543 | Yes |
| 14 | `kill` | 591 | Yes |
| 15 | `detach` | 628 | Yes |
| — | fallthrough: log `script complete, exiting normally`, `exit 0` | 662-663 | Unreachable in practice. |

### 2.1 Valid action list (`assertValidAction`, 1550-1555)

```
switch, new, rename, detach, kill, kill-single,
reload-sessions, popup-switch,
worktree-switch, popup-worktree-switch,
capital-switch, popup-capital-switch
```

Error message on failure (1562):
`Invalid action: <action>. Must be one of: switch, new, rename, detach, kill, kill-single, reload-sessions, popup-switch, worktree-switch, popup-worktree-switch, capital-switch, popup-capital-switch`

Note: `switch-from-line`, `kill-single-from-line`, `delayed-switch` are **missing** from this
list, but they work because they are routed before the gate.

### 2.2 Full action list accepted on argv — 15 strings

| # | Action | Takes a second argument? | User-facing? |
|---|---|---|---|
| 1 | `switch` | no | yes |
| 2 | `new` | no | yes |
| 3 | `rename` | no | yes |
| 4 | `kill` | no | yes |
| 5 | `detach` | no | yes |
| 6 | `worktree-switch` | no | yes |
| 7 | `capital-switch` | no | yes |
| 8 | `popup-switch` | no | yes |
| 9 | `popup-worktree-switch` | no | yes |
| 10 | `popup-capital-switch` | no | yes |
| 11 | `kill-single` | yes — session name | semi (legacy) |
| 12 | `reload-sessions` | no | internal (fzf `reload`) |
| 13 | `kill-single-from-line` | yes — an fzf row | internal (fzf `del`) |
| 14 | `switch-from-line` | yes — an fzf row | internal (fzf `ctrl-n`/`ctrl-p`) |
| 15 | `delayed-switch` | yes — a token | internal (spawned child) |

Plus one more entry point: **no argument at all** → the action menu (§3.1).

Only the three `popup-*` actions are bound in `tmux_with_keybinds.conf`
(`C-S-l` / `l` → `popup-switch`, `C-S-o` → `popup-capital-switch`, `C-S-p` → `popup-worktree-switch`).

---

## 3. Per-action behavior

### 3.1 No action given → action menu (`selectAction`, 665-683)

* Items, in this exact order: `switch`, `new`, `rename`, `detach`, `kill`, `[cancel]`.
* Header: `Select an action.`
* `includePreview: false`, no extra bindings.
* **No number prefixes** (calls `runFzf` directly, not `selectSessions`).
* Returns `parseLines(selection)[0] ?? ''`.
* Empty or `[cancel]` → `exit 0` at line 52-55.

### 3.2 `popup-switch` / `popup-worktree-switch` / `popup-capital-switch`

Each runs one command and exits 0.

| Action | Command (line) |
|---|---|
| `popup-switch` | `tmux display-popup -E -w 60% -h 90% -x R -y C -T "SESSIONS" -b rounded <scriptPath> switch` (61) |
| `popup-worktree-switch` | `tmux display-popup -E -w 60% -h 90% -x R -y C -T "WORKTREE SESSIONS" -b rounded <scriptPath> worktree-switch` (70) |
| `popup-capital-switch` | `tmux display-popup -E -w 60% -h 90% -x R -y C -T "CAPITAL SESSIONS" -b rounded <scriptPath> capital-switch` (79) |

`<scriptPath>` is the absolute path of the script itself.
Geometry is identical for all three: width 60%, height 90%, x = right, y = center,
border style `rounded`, `-E` = close popup when the command exits.
If `tmux display-popup` fails, the `await $` throws → the process crashes with a non-zero code.

### 3.3 `reload-sessions` (85-94)

Used by the DEL binding's `reload(...)` clause.

1. `sessions = getSessionsList({ currentSession: null, excludeCurrent: false })`
   (note: `currentSession` is **null**, so no "current on top" reordering).
2. `numbered = addNumberPrefixes(sessions)`
3. `console.log(numbered.join('\n'))` → stdout, plus one trailing newline from `console.log`.
4. `exit 0`.

Output row format: `[1] name @ 3 windows`, `[2] other @ 1 windows`, … then unnumbered rows from
the 10th onwards. **No `[cancel]` row is printed** (unlike the initial list) — (`.mjs` today; the Go
port does the opposite — Q7 FIX). See quirk Q7.
If there are zero sessions, `console.log('')` prints a single empty line.

**Go port (Q7 is labelled FIX — this changes steps 1 and 3):**

| Step | Go behaviour |
|---|---|
| 1 | pass the **real** current session, not `null`, so the current session is pinned to the top |
| 2 | `addNumberPrefixes` as today |
| 3 | append the literal row `[cancel]` after numbering, exactly like `selectSessions` (§4.2) |
| 4 | print the rows to stdout, one per line, then `exit 0` |

Rule: `reload-sessions` and the initial `switch` list must produce **identical** rows for the
same set of sessions. If they differ, the list silently changes shape after the first DEL press.
The stdout assertions in `tests/test_script_functionality.py` (`[`, `]`, `@`, `windows`,
`3 windows`, the session names) all still pass with the extra `[cancel]` row.

### 3.4 `kill-single-from-line <line>` (96-110)

1. `selectedLine = argv._[1] ? String(argv._[1]) : ''`
2. `sessionName = extractSessionName(selectedLine)` (strips `[N] ` prefix and ` @ …` suffix).
3. If `sessionName` is truthy → run `tmux kill-session -t <sessionName>`.
   Any error is caught and only logged. **No name validation. No `[cancel]` guard.**
4. Always `exit 0`.

### 3.5 `switch-from-line <line>` (119-142)

Bound to Ctrl+N / Ctrl+P. This is the "preview" mechanism: it really switches the client,
but through a debounce (§7).

1. `sessionName = extractSessionName(argv._[1] ?? '')`.
2. If empty or `== '[cancel]'` → log `no session to process`, `exit 0`.
3. `result = await scheduleSessionSwitch(sessionName)` (§7.2). Errors are caught and logged.
4. Always `exit 0`.

### 3.6 `delayed-switch <token>` (112-117)

1. `token = argv._[1] ? String(argv._[1]) : ''`.
2. `await handleDelayedSwitch(token)` (§7.3).
3. `exit 0`.

### 3.7 `kill-single <name>` (154-256)

Interactive confirm flow. Reachable only if `assertValidAction` passed.

1. If `argv._[1]` is missing → log, stderr `Error: Session name required for kill-single action`, `exit 1`.
2. `assertValidSessionName(name)` → on failure stderr `Error: <msg>`, `exit 1`.
3. `tmux has-session -t <name>`; if it fails → run
   `tmux display-message "Session <name> does not exist"` and `exit 1`.
4. Print to stdout:
   ```
   <blank line>
   ⚠️  Kill session "<name>"?
   Press Y to confirm, any other key to cancel...
   <blank line>
   ```
   (exact code: `console.log('\n⚠️  Kill session "<name>"?')` then
   `console.log('Press Y to confirm, any other key to cancel...\n')`, lines 191-192.)
5. Read ONE keypress from stdin in raw mode, with a 30000 ms timeout (197-214).
   * On timeout or read error → print `✗ Timeout or error, kill cancelled`, `exit 0`.
   * If the value is not a string → print `✗ Invalid input, kill cancelled`, `exit 0`.
   * **Non-TTY stdin (M9):** `process.stdin.setRawMode(true)` (199) throws immediately when stdin
     is not a terminal (a pipe, a file, `/dev/null`). The `catch` at 215 then fires **at once** —
     there is **no** 30 s wait. The user sees `✗ Timeout or error, kill cancelled` instantly and
     the process exits 0. The Go port must reproduce this: if stdin is not a TTY, print that same
     line and exit 0 without waiting.
6. If the key matches `/^[Yy]$/` → run `tmux kill-session -t <name>`.
   * success → print `✓ Session "<name>" killed`
   * failure → print `✗ Failed to kill session "<name>"`
7. Else → print `✗ Kill cancelled`.
8. Sleep 800 ms (so the user sees the result), then `exit 0`.

### 3.8 `new` (260-289)

> **Today this action is DEAD.** `promptSessionName()` always returns `""` because of the quoting
> bug Q8, so step 2 always fires and steps 3-6 never run. The steps below describe the *intended*
> flow. The Go port MUST make them work (decision D7). See Q8 for the exact fix.

1. `sessionName = await promptSessionName()` (§9).
2. If empty → log, `exit 0`. **← today this is the only path taken.**
3. `assertValidSessionName(sessionName)`; on failure stderr `Error: <msg>`, `exit 1`.
4. `tmux new-session -d -s <name>` (not guarded; a failure crashes the process).
5. `tmux switch-client -t <name>`; on failure log and `exit 1`.
6. `exit 0`.
   **No frecency record is written for a new session.**

### 3.9 `worktree-switch` (292-370)

1. `tmux display-message -p '#{pane_current_path}'` → `currentPath` (trimmed).
2. `worktreePaths = getGitWorktrees(currentPath)` (§6.1).
   * If empty → `tmux display-message "Not in a git repository"`, `exit 0`.
3. `allPanePaths = getAllPanePaths()` (§6.2).
4. `allSessions = getSessionsList({ currentSession, excludeCurrent: false })`.
5. `filtered = filterSessionsByWorktrees(allSessions, worktreePaths, allPanePaths)` (§6.3).
   * If empty → `tmux display-message "No sessions found for this project's worktrees"`, `exit 0`.
6. Extra bindings (331-333) — DEL is intentionally **not** bound here (TODO at 328):
   ```
   --bind 'ctrl-n:down+execute-silent(<script> switch-from-line {})' --bind 'ctrl-p:up+execute-silent(<script> switch-from-line {})'
   ```
7. `selectSessions({ sessions: filtered, includeCurrent: false, currentSession,
   header: 'Worktree sessions (<F>/<A>). Ctrl+N/P to preview.', includePreview: true, extraBindings })`
   where `<F>` = filtered count and `<A>` = total count.
8. `targets = parseTargets(selection, currentSession)`; if empty → `exit 0`.
9. `assertValidSessionName(targets[0])`; on failure log and `exit 1` (nothing printed to stderr).
10. `tmux switch-client -t <targets[0]>` (unguarded).
11. Record frecency for `targets[0]`.
12. `exit 0`.

### 3.10 `capital-switch` (373-435)

1. `allSessions = getSessionsList({ currentSession, excludeCurrent: false })`.
2. Filter: keep the line if the extracted session name matches BOTH
   `^[A-Z0-9_\-\s]+$` and `[A-Z]` (384). In words: only uppercase letters, digits,
   underscore, hyphen, whitespace — and at least one uppercase letter.
3. If empty → `tmux display-message "No CAPITAL sessions found"`, `exit 0`.
4. Extra bindings: same Ctrl+N / Ctrl+P pair as worktree-switch (no DEL, no number keys).
5. Header: `CAPITAL sessions (<C>/<A>). Ctrl+N/P to preview.`
6. Same select → parse → validate → `tmux switch-client` → frecency → `exit 0` as §3.9.

### 3.11 `switch` (440-541)

Preconditions checked first (447-471), each throws (uncaught → crash):

| Check | Line | Error text |
|---|---|---|
| script path is a non-empty string | 448 | `Could not determine script path` |
| script path length ≤ 4096 | 451 | `Script path is too long` |
| script path has no `` ` `` `$` `;` `\|` `&` `<` `>` `(` `)` `{` `}` `[` `]` `!` `\` | 455 | `Script path contains unsafe characters` |
| `TMUX_FZF_SESSION_FORMAT` is a string (if set) | 461 | `TMUX_FZF_SESSION_FORMAT must be a string` |
| … length ≤ 500 | 464 | `TMUX_FZF_SESSION_FORMAT exceeds max length` (note: **no** "of 500 characters" here — the copy in `getSessionsList` has a different message, see §4.1 step 2) |
| … no `` ` `` `$` `;` `\|` `&` `<` `>` `(` `)` | 468 | `TMUX_FZF_SESSION_FORMAT contains unsafe characters` |

**Go port:** the three `TMUX_FZF_SESSION_FORMAT` rows are deleted with the variable (Q4, §0.6).
The three script-path rows stay, but Q17 replaces the character blacklist with proper quoting.

Bindings (481-498), built with the absolute script path:

```
--bind 'del:execute(<script> kill-single-from-line {})+reload(<script> reload-sessions)'
--bind 'ctrl-n:down+execute-silent(<script> switch-from-line {})'
--bind 'ctrl-p:up+execute-silent(<script> switch-from-line {})'
--bind '1:pos(1)+accept,2:pos(2)+accept,3:pos(3)+accept,4:pos(4)+accept,5:pos(5)+accept,6:pos(6)+accept,7:pos(7)+accept,8:pos(8)+accept,9:pos(9)+accept'
```

`extraBindings` = the four `--bind` strings joined by single spaces, in the order
DEL, ctrl-n, ctrl-p, numbers (508).

Selector call (502-509):
`selectSessions({ sessions, includeCurrent: false, currentSession,
header: 'Select target session. Press 1-9 for quick switch. DEL to kill. Ctrl+N/P to preview.',
includePreview: true, extraBindings })`

Then:
1. `targets = parseTargets(selection, currentSession)`; if empty → `exit 0`.
2. `assertValidSessionName(targets[0])`; on failure stderr `Error: <msg>`, `exit 1`.
3. `tmux switch-client -t <targets[0]>`
   * success → record frecency, log, `exit 0`
   * failure → log (plus stderr/stdout of the failed command), `exit 1`
4. Only `targets[0]` is used, even if fzf returned several lines.

Note: `pos(N)` needs fzf that supports the `pos` action (fzf ≥ 0.36).
Because digits 1-9 are bound, the user cannot type digits into the query in this view.

### 3.12 `rename` (543-589)

> **Today this action is DEAD**, for the same reason as `new`: `promptSessionName()` always
> returns `""` (Q8), so step 1 always exits 0 and the selector is never shown. The steps below
> describe the *intended* flow. The Go port MUST make them work (decision D7).

1. `sessionName = await promptSessionName()` (§9). If empty → `exit 0`. **← today this always fires.**
2. `assertValidSessionName(sessionName)`; on failure stderr `Error: <msg>`, `exit 1`.
3. `selectSessions({ sessions, includeCurrent: true, header: 'Select target session.', includePreview: true })`
   — **`currentSession` is NOT passed** (562-567). So a literal `[current]` row is prepended and the
   real current session is NOT moved to the top.
4. `targets = parseTargets(selection, currentSession)`; empty → `exit 0`.
5. `assertValidSessionName(targets[0])`; failure → stderr `Error: <msg>`, `exit 1`.
6. `tmux rename-session -t <targets[0]> <sessionName>` (unguarded).
7. `exit 0`.

### 3.13 `kill` (591-626)

1. `selectSessions({ sessions, includeCurrent: true,
   header: 'Select target session(s). Press TAB to mark multiple items.', includePreview: true })`
   — again **no `currentSession`**, so a `[current]` row is prepended.
2. `targets = parseTargets(selection, currentSession)`; empty → `exit 0`.
3. Validate **every** target; first failure → stderr `Error: <msg>`, `exit 1`.
4. `ordered = targets.slice().sort().reverse()` — plain lexicographic sort, then reversed
   (descending). Kill in that order: `tmux kill-session -t <target>` for each (unguarded).
5. `exit 0`.

Multi-select (TAB) only works if `--multi` is present in `TMUX_FZF_OPTIONS` or
`FZF_DEFAULT_OPTS`. The script never adds `--multi` itself.

### 3.14 `detach` (628-660)

1. `selectDetachSessions({ sessions, currentSession,
   header: 'Select target session(s). Press TAB to mark multiple items.' })` (714-719):
   * `attachedNames = getAttachedSessionNames()` — see quirk Q3, this set is effectively useless.
   * `filtered = sessions.filter(line => attachedNames.has(extractSessionName(line)))`
   * `items = ['[current]', ...filtered, '[cancel]']`, then `dedupe(items)`.
   * `runFzf(items, { header, includePreview: true })` — **no number prefixes, no extra bindings**.
2. `targets = parseTargets(selection, currentSession)`; empty → `exit 0`.
3. Validate every target; failure → stderr `Error: <msg>`, `exit 1`.
4. For each target in selection order: `tmux detach -s <target>` (unguarded).
5. `exit 0`.

#### 3.14.1 What `detach` CAN and CANNOT do today (M13, C4)

The Q3 headline "the list is always empty" is imprecise. The **filter result** is always empty.
The **list** always has exactly two rows, and one of them works.

| Case | Works today? | Why |
|---|---|---|
| Detach the session the user is in (pick `[current]`) | **YES** | `parseTargets` (1235) replaces `[current]` with `<currentSession> @ `, `extractSessionName` yields `currentSession`, and 656 runs `tmux detach -s <currentSession>`, which succeeds. |
| Detach any other session | **NO** | no other session ever reaches the picker (the filter drops them all). |
| Multi-select several sessions with TAB | **NO** | only one real row exists. |
| Pick `[cancel]` | yes (no-op, exit 0) | `parseTargets` returns `[]`. |

**Rule for the Go port:** when you fix Q3, do **not** drop the `[current]` row. It is the only
part of `detach` that works today, and the tests may depend on it. Keep `[current]` first, then
the real attached sessions, then `[cancel]`, then `dedupe`.

---

## 4. Session list, formatting and ordering

### 4.1 `getSessionsList({ currentSession, excludeCurrent })` (1051-1132)

1. If `currentSession` is truthy, run `assertValidSessionName` on it; a failure is only **logged**
   as a warning, never thrown (1055-1061).
2. Read `TMUX_FZF_SESSION_FORMAT` and validate it. **The value is never used** to build the tmux
   format string. See quirk Q4. The validation here is **not** the same as the one in `switch`
   (§3.11) — the messages differ and one check is missing (M4):

   | Check | `getSessionsList` (1067-1074) | `switch` (461-471) |
   |---|---|---|
   | runs only if the value is truthy | yes | yes |
   | must be a string | `TMUX_FZF_SESSION_FORMAT must be a string` | same message |
   | max length 500 | `TMUX_FZF_SESSION_FORMAT exceeds max length of 500 characters` | `TMUX_FZF_SESSION_FORMAT exceeds max length` (**no** "of 500 characters") |
   | unsafe characters `` ` `` `$` `;` `\|` `&` `<` `>` `(` `)` | **not checked at all** | `TMUX_FZF_SESSION_FORMAT contains unsafe characters` |

   Both throw, and nothing catches them, so a bad value **crashes** the process.
   The Go port deletes the variable and both validations (decision D6 table, §0.6 / Q4).
3. Run exactly (line 1077):
   ```
   tmux list-sessions -F '#S @ #{session_windows} windows'
   ```
   **The single quotes are shell quotes — see §0.9.1 row 1.** In Go the format is one argv element
   with no quotes: `#S @ #{session_windows} windows`. Row example: `mysession @ 3 windows`.
4. `rawLines = parseLines(stdout)` — split on `\n`, trim each line, drop empty lines.
5. `lines = columnFormat(rawLines, '@')` (1033-1049): split each line on the single character `@`;
   if fewer than 2 parts, return `line.trim()`; else trim each part and rejoin with `' @ '`.
   Net effect: whitespace around `@` is normalised to exactly one space on each side.
6. Sort by frecency score, descending (§5). The sort is stable in V8 — a Go port must use a
   **stable** sort to keep tmux's own ordering for ties.
7. If `excludeCurrent` is falsy → return all lines.
   Else → drop lines starting with `"<currentSession> @ "` (1129).
   In practice `excludeCurrent` is always `false` at every call site (87, 313, 377, 437).
   **Go port (D3):** delete the `excludeCurrent` parameter and this whole branch.
   The function always returns all lines. See Q1.

### 4.2 `selectSessions({ sessions, includeCurrent, currentSession, header, includePreview, extraBindings })` (685-712)

Item order:

| Condition | Resulting items |
|---|---|
| `currentSession` truthy AND a line starts with `"<currentSession> @ "` | that line first, then all other lines in frecency order |
| `currentSession` truthy but no matching line | all lines in frecency order (no `[current]` row, even if `includeCurrent` is true) |
| `currentSession` falsy AND `includeCurrent` true | `['[current]', ...lines]` |
| `currentSession` falsy AND `includeCurrent` false | `lines` |

Then `addNumberPrefixes(items)` (§4.3), then push the literal row `[cancel]` **after** numbering,
then call `runFzf`.

So `[cancel]` is always the last row of **`selectSessions`** (that is: `switch`,
`worktree-switch`, `capital-switch`, `rename`, `kill`) and of `selectDetachSessions`
(§3.14) and of the action menu (§3.1, where `[cancel]` is a normal list item).

**Exception (C2/W7):** `reload-sessions` does **not** print a `[cancel]` row (line 92) — (`.mjs`
today; the Go port does the opposite — Q7 FIX). It does not go through `selectSessions` at all — it
prints to stdout for fzf's `reload` action. See §3.3 and quirk Q7.

### 4.3 `addNumberPrefixes(items)` (1246-1263)

* Walk items in order, with `numberIndex` starting at 1.
* If the item starts with `[` → push unchanged, **do not** consume a number.
* Else if `numberIndex <= 9` → push `` `[${numberIndex}] ${item}` `` and increment.
* Else → push unchanged.

Row format after numbering: `[1] name @ 3 windows`.

**M12 — the `[` test is a plain prefix test.** It matches **any** item that starts with `[`, not
only `[current]` and `[cancel]`. tmux allows a session named `[work]`, so the row
`[work] @ 3 windows` gets **no** number and does not consume a number either. The rows after it
keep counting from where they were. `assertValidSessionName` (§11.3) rejects `[` and `]`, so such
a session can never be created **by this tool**, but it can already exist in tmux. Keep this
behaviour in Go: test only for the leading `[` character.

### 4.4 `extractSessionName(line)` (1265-1274)

1. If the line matches `^\[\d+\] ` → remove that prefix.
2. Find the first `' @ '`. If not found → return the whole (cleaned) string.
   Else return everything before it.

So `extractSessionName('[cancel]') === '[cancel]'` and
`extractSessionName('[current]') === '[current]'`.

### 4.5 `parseTargets(selection, currentSession)` (1229-1238)

1. `lines = parseLines(selection)`.
2. If `lines.length === 0` OR the array **contains** `[cancel]` → return `[]`
   (so a multi-select that includes `[cancel]` cancels everything).
3. Map: `line.replace('[current]', currentSession + ' @ ')` (only the first occurrence),
   then `extractSessionName`, then drop falsy values.

**M14 — this is a substring replace, not a whole-row match.** JavaScript
`String.prototype.replace` with a string pattern replaces the **first occurrence anywhere** in
the row. So a session named `x[current]y` in the row `x[current]y @ 2 windows` becomes
`x<currentSession> @ y @ 2 windows`, and `extractSessionName` then returns `x<currentSession>`.
A Go port that uses an exact-equality check (`line == "[current]"`) is **not** bug-compatible.
Use `strings.Replace(line, "[current]", currentSession+" @ ", 1)`.
Risk is low — `assertValidSessionName` rejects `[` — but keep it identical.

### 4.6 `parseLines(text)` (1276-1284)

Return `[]` for empty/falsy input. Else split on `\n`, `trim()` every line, keep non-empty ones.

### 4.7 `dedupe(items)` (1294-1304)

Keep first occurrence, preserve order.

---

## 5. Frecency

### 5.1 Storage — TODAY (reference only; the Go port uses §0.3)

| Item | Value |
|---|---|
| Backend | `node-localstorage` `LocalStorage` (**31**) |
| Directory | `<scriptDir>/.session-frecency` (**30**) |
| Frecency key | `tmux-sessions` (**32-35**, the `key` option of the `Frecency` constructor) |
| Storage item key | `frecency_tmux-sessions` (1086) |
| On-disk file | `<scriptDir>/.session-frecency/frecency_tmux-sessions` |
| Content | JSON |

(W2/C1: earlier drafts cited 1030/1031/1033. Those numbers were wrong by exactly 1000.
The correct lines are 30, 31 and 32-35, which matches §1 row 7.)

Read path (1086-1087):
```js
JSON.parse(frecencyStorage.getItem('frecency_tmux-sessions') || '{"selections":{}}')
const selections = storageData.selections || {}
```
Only `selections[<sessionName>].selectedAt` is used. That field is an array of epoch
milliseconds (numbers). A missing entry, missing `selectedAt`, or empty array → score 0.

The directory does not exist in a fresh checkout. Missing directory/file must behave like
"empty frecency" (score 0 for everything).

### 5.2 Score buckets (`calculateScore`, 1096-1114)

For each timestamp `ts` in `selectedAt`, with `ageHours = (Date.now() - ts) / 3600000`:

| Age | Points added |
|---|---|
| `< 1` hour | 100 |
| `< 24` hours | 50 |
| `< 168` hours (7 days) | 10 |
| otherwise | 1 |

The score is the sum over all timestamps. Sort comparator is `bScore - aScore` (descending).
Note the buckets are exclusive-`<`, so exactly 1 hour old falls in the 24-hour bucket, etc.
Negative ages (future timestamps) land in the `< 1` bucket and score 100.

### 5.3 When a selection is recorded

`sessionFrecency.save({ selectedId: <name> })` is called only here:

| Action | Line | When |
|---|---|---|
| `worktree-switch` | 365 | after a successful `tmux switch-client` |
| `capital-switch` | 430 | after a successful `tmux switch-client` |
| `switch` | 531 | after a successful `tmux switch-client` |

It is **not** called for `new`, `rename`, `kill`, `detach`, or `switch-from-line`
(the Ctrl+N/P preview). No search query is passed.

The library (`@getstation/frecency`) appends `Date.now()` to `selections[id].selectedAt`,
increments `timesSelected`, and keeps only the most recent N timestamps.

### 5.4 What the Go port writes (BINDING — decision D6)

Do **NOT** reverse-engineer the `@getstation/frecency` format. `node_modules/` is empty in this
checkout (§16) and there is no existing frecency data to preserve.

The port uses the new file and schema defined in **§0.3**:
`<appDir>/.session-frecency/sessions.json`, `{"version":1,"sessions":{"<name>":{"selectedAt":[…]}}}`,
cap 10 timestamps per session, atomic write, missing/broken file = every score 0.

Everything else stays the same:

| Kept exactly | Reference |
|---|---|
| the four score buckets 100 / 50 / 10 / 1 and their `<` boundaries | §5.2 |
| descending sort, **stable** for ties | §4.1 step 6 |
| write only after a successful `tmux switch-client` in `switch`, `worktree-switch`, `capital-switch` | §5.3 |
| **no** write for `new`, `rename`, `kill`, `detach`, `switch-from-line` | §5.3 |

---

## 6. Git worktree helpers

### 6.1 `getGitWorktrees(dirPath)` (1149-1167)

* Command: `git -C <dirPath> worktree list --porcelain`
* Split stdout on `\n`. For every line starting with `worktree ` take `line.slice(9)`
  (the rest of the line, unmodified — no trim).
* On any error (not a git repo, git missing, …) → log and return `[]`.

### 6.2 `getAllPanePaths()` (1173-1194)

* Command: `tmux list-panes -a -F '#{session_name}\t#{pane_current_path}'`
  (a real TAB character between the two fields — in a JS template literal `\t` is U+0009).
  **The single quotes are shell quotes — see §0.9.1 row 2.** In Go the format is one argv element:
  `"#{session_name}\t#{pane_current_path}"`, no quotes.
* Trim stdout, split on `\n`, drop empty lines.
* For each line: split at the **first** TAB. Left = session name, right = pane path.
  Lines with no TAB are skipped.
* Result: `map[sessionName] -> set of pane paths`.
* Unguarded: a tmux failure crashes the process.

### 6.3 `filterSessionsByWorktrees(sessions, worktreePaths, allPanePaths)` (1203-1227)

1. Normalise every worktree path by stripping all trailing `/` (`p.replace(/\/+$/, '')`).
2. Keep a session line if its session has at least one pane path `p` such that,
   for some normalised worktree `wt`: `p === wt` OR `p` starts with `wt + '/'`.
3. Sessions with no panes are dropped.
4. Order of the input list is preserved.

### 6.4 `getAttachedSessionNames()` (1134-1142)

* Command: `tmux list-sessions` (default format, no `-F`).
* Keep lines containing the substring `attached`.
* Map each kept line through `extractSessionName`.
* Return a `Set`.

See quirk Q3: `extractSessionName` finds no `' @ '` in the default tmux format, so it returns
the whole raw line. The resulting set never matches real session names.

---

## 7. Debounce / delayed switch

> **This whole section is KEPT IN FULL in the Go port.**
> This is the **Ctrl+N / Ctrl+P session preview**. Decision D5 drops the *kaomoji preview pane*
> and nothing else — see §0.2. Do not delete anything here.

### 7.1 State file

| Item | Value |
|---|---|
| Path | `/tmp/tmux-session-<id>.json` (27) |
| `<id>` | `os.userInfo().uid` as a string; else `username`; else `pid-<pid>` (725-738) |
| File mode | `0600` (776) |
| Encoding | UTF-8 |

JSON shape (769-774):
```json
{ "lastWrite": 1721476800000, "lastTarget": "mysession", "token": "1721476800000-12345-a1b2c3d4" }
```
* `lastWrite`: number (epoch ms). Falls back to `Date.now()` if not finite.
* `lastTarget`: string, or `null`.
* `token`: string, or `null`.

Read behaviour (`readSessionDebounceState`, 740-767) — every failure returns the neutral
state `{ lastWrite: 0, lastTarget: null, token: null }`:

| Error | Logged message |
|---|---|
| `ENOENT` | (nothing) |
| `EACCES` / `EPERM` | `session debounce: no read access to <path>: <code>` |
| invalid JSON | `session debounce: invalid JSON in <path>, resetting` |
| other | `session debounce: unexpected read error for <path>: <msg>` |

Non-finite `lastWrite` becomes `0`; non-string `lastTarget`/`token` become `null`.

Write returns `false` on `EACCES`/`EPERM` (logged as `session debounce: no write access to <path>: <code>`)
or on any other error (logged as `session debounce: failed to write <path>: <msg>`).

### 7.2 `scheduleSessionSwitch(targetName)` (788-846)

1. `trimmedName = targetName.trim()`. If empty → return `{switchedImmediately:false, scheduled:false}`.
2. `now = Date.now()`.
3. `token = `${now}-${process.pid}-${Math.random().toString(36).slice(2,10)}``
   → e.g. `1721476800000-48213-k3n2p9qz`. The random part is up to 8 base-36 chars.
4. Write the state file with `{lastWrite: now, lastTarget: trimmedName, token}`.
5. Log `session throttle: scheduled target=<name> token=<token>` (or `write failed` instead of `scheduled`).
6. **If the write failed** → fallback: run `tmux switch-client -t <name>` immediately.
   * success → log `session throttle: immediate fallback switch for <name>`, rewrite the state file with
     `{lastWrite: Date.now(), lastTarget: name, token: null}`, return `{switchedImmediately:true, scheduled:false}`.
   * failure → log `session throttle: fallback switch failed for <name>: <msg>`, return `{false,false}`.
7. **If the write succeeded** → spawn a detached child:
   `spawn(process.execPath, [scriptFilePath, 'delayed-switch', token], { detached: true, stdio: 'ignore' })`
   then `child.unref()`. Return `{switchedImmediately:false, scheduled:true}`.
   * If `spawn` throws → log `session throttle: spawn failed for <name>: <msg>` and do the same
     immediate fallback as step 6 (log text: `session throttle: immediate fallback after spawn failure for <name>`).

**Go equivalent of step 7 (added 2026-08-07).** Node's `{detached:true, stdio:'ignore'}` is two
separate things in Go, and getting either wrong breaks a test:

```go
cmd := exec.Command(selfPath, "delayed-switch", token)   // selfPath = os.Executable()
cmd.Stdin, cmd.Stdout, cmd.Stderr = nil, nil, nil        // nil => /dev/null
cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}     // new session, no controlling tty
if err := cmd.Start(); err != nil { /* immediate fallback, step 6 */ }
_ = cmd.Process.Release()                                // never Wait; we exit right away
```

| Trap | Consequence if you get it wrong |
|---|---|
| passing `os.Stdout` instead of `nil` | the child holds the popup's pty open. `tests/test_script_executes.py:32` waits 2 s for `pexpect.EOF` and never gets it. |
| calling `cmd.Wait()` | we block instead of exiting, so the popup never closes |
| omitting `Setsid: true` | closing the popup can kill the child before the debounce fires |

`syscall.SysProcAttr{Setsid: true}` is in the Linux stdlib. No `golang.org/x/sys` is needed.

### 7.3 `handleDelayedSwitch(token)` (848-879)

1. If `token` is empty → log `session throttle: delayed switch invoked without token, skipping`, return `false`.
2. Sleep `SESSION_SWITCH_DEBOUNCE_MS` (default 300 ms).
3. Read the state file.
4. If `lastTarget` is empty after trimming, OR `state.token !== token` → log
   `session throttle: delayed switch skip token=<t>, stateToken=<s|null>, target=<target|(none)>`,
   return `false`. This is the "last write wins" rule: a newer keypress replaced the token.
5. Else run `tmux switch-client -t <lastTarget>`.
   * success → log `session throttle: delayed switch executed for <target>`, rewrite the state file with
     `{lastWrite: Date.now(), lastTarget: target, token: null}`, return `true`.
   * failure → log `session throttle: delayed switch failed for <target>: <msg>`, return `false`.

The `token: null` rewrite makes a second `delayed-switch` for the same token a no-op.

### 7.4 Full Ctrl+N flow

1. User presses Ctrl+N in fzf.
2. fzf runs `down` then `execute-silent(<script> switch-from-line {})`.
3. The child process boots the whole script (sources `.envs`, calls
   `tmux display-message -p '#S'`, etc.), routes to `switch-from-line`.
4. It writes the state file with a fresh token and spawns a **grandchild**
   `node <script> delayed-switch <token>`, then exits 0.
5. The grandchild sleeps 300 ms. If no newer keypress replaced the token, it switches the client.

Cost note for the Go port: every keypress starts two full processes.

---

## 8. Environment variables

### 8.1 `.envs` sourcing (`sourceEnv`, 1364-1390)

Candidate paths, in this precedence order:

| # | Path |
|---|---|
| 1 | `<scriptDir>/.envs` |
| 2 | `<homedir>/.tmux/plugins/tmux-fzf/scripts/.envs` |

The **first existing** file wins; the function returns immediately after applying it.
If none exists → log `sourceEnv: no .envs file found` and continue.

How it is applied:
1. Escape `"` in the path as `\"` (1378 — this escape is correct).
2. Run: `bash -lc 'source "<path>" >/dev/null 2>&1 && env'`
3. Parse the output with `parseEnvOutput` (1392-1407): for each non-empty line, split at the
   **first** `=`; lines with no `=` are skipped. Multi-line values are therefore mangled.
4. Copy **every** parsed key into `process.env` — including `PATH`, `HOME`, and anything the
   login shell exports. See quirk Q5.

**Go port:** apply the diff-based fix with the `PATH` exception — the exact rules are in **§0.4**.
Ground truth: neither candidate path exists on this machine today (§16), so `sourceEnv` is a
no-op right now.

### 8.2 `ensureEnvDefaults()` (1409-1427)

| Variable | Default set if unset/empty |
|---|---|
| `TMUX_FZF_BIN` | `fzf` |
| `TMUX_FZF_OPTIONS` | `''` (empty string) |
| `TMUX_FZF_PREVIEW_OPTIONS` | **nothing** — instead `KAOMOJI_PREVIEW_TEXT` is set (see quirk Q2) |
| `FZF_DEFAULT_OPTS` | `''` (empty string) |

**Go port (decision D5):** the `TMUX_FZF_PREVIEW_OPTIONS` row disappears completely. The port sets
only `TMUX_FZF_BIN` → `fzf` and leaves `TMUX_FZF_OPTIONS` / `FZF_DEFAULT_OPTS` as empty strings
when unset. Nothing kaomoji-related remains.

### 8.3 All environment variables touched

| Variable | Read at | Written at | Default | Purpose |
|---|---|---|---|---|
| `SESSION_SWITCH_DEBOUNCE_MS` | 26 | — | 300 | Delay in ms before the delayed switch fires. Read **before** `.envs` is sourced (quirk Q6). `parseInt(...,10) \|\| 300`, so `0`, empty, or non-numeric → 300. |
| `FZF_DEFAULT_OPTS` | 40, 1424 | 1425 (default `''`), and set per fzf call at 893 | `''` | Base fzf options; the script prepends them to its own options. |
| `TMUX_FZF_SWITCH_CURRENT` | 46 | — | unset | Intended to keep the current session in the list. **Never applied** (quirk Q1). |
| `TMUX_FZF_SESSION_FORMAT` | 445, 1063 | — | unset | Validated only. **Never applied** (quirk Q4). |
| `TMUX_FZF_BIN` | 999-1001, 1010, 1410 | 1411 | `fzf` | The fzf binary (or a full command prefix). |
| `TMUX_FZF_OPTIONS` | 1003, 1011-1012, 1413 | 1414 | `''` | Extra fzf options always appended (this is where `--multi` must come from). |
| `TMUX_FZF_PREVIEW_OPTIONS` | 1006, 1014-1015, 1416 | never | unset | Extra fzf options added only when `includePreview` is true. Because it is never defaulted, preview options are absent unless `.envs` sets them. |
| `KAOMOJI_PREVIEW_TEXT` | — | 1418 | — | Set from a random kaomoji, but nothing reads it (the consumer is commented out). |
| `TMUX_FZF_RUN` | consumed by the bash heredoc (909) | 894 | — | The full fzf command line that bash `eval`s. |

`process.execPath` (the node binary) is also used, at 822. In Go, the equivalent is the path of
the Go binary itself (`os.Executable()`), used to spawn the `delayed-switch` child (§7.2 step 7).

#### 8.3.1 Which variables the Go port keeps

| Variable | Go port |
|---|---|
| `SESSION_SWITCH_DEBOUNCE_MS` | **keep**, and fix Q6: read it **after** `.envs` is loaded, and treat an explicit `0` as "no delay" |
| `FZF_DEFAULT_OPTS` | **keep**. Leave the user's value in the child environment; fzf reads it. See §0.5. |
| `TMUX_FZF_BIN` | **keep**, shell-split (§0.5) |
| `TMUX_FZF_OPTIONS` | **keep**, shell-split (§0.5) |
| `TMUX_FZF_RUN` | **drop** — no more `eval`, so no assembled command string is needed |
| `TMUX_FZF_SWITCH_CURRENT` | **DELETE** (D3) |
| `TMUX_FZF_SESSION_FORMAT` | **DELETE** (Q4) |
| `TMUX_FZF_PREVIEW_OPTIONS` | **DELETE** (D5) |
| `KAOMOJI_PREVIEW_TEXT` | **DELETE** (D5) |

### 8.4 `pickPreviewKaomoji()` (1429-1468) — HISTORY ONLY, NOT PORTED

> **Decision D5: this whole section is dropped from the Go port.** It is kept here only so a
> reader knows what the `.mjs` did. Do not implement any of it.
> Reminder: this is the *kaomoji pane*, not Ctrl+N / Ctrl+P — see §0.2.

* Loads `<scriptDir>/KaomojiList/kaomojis.json` via `require`.
  (This directory does not exist in the repo, so the fallback path is what actually runs.)
* Expected JSON shape: an array of groups; each group has `categories`; each category has an
  `emoticons` array of strings.
* Picks **6** random emoticons (with repetition possible) and joins them with `\n\n`.
* Any non-string / empty pick becomes `(^_^)`.
* If the file is missing, unparsable, or has zero emoticons → return 6 copies of `(^_^)`
  joined with `\n\n`.

---

## 9. `promptSessionName()` (1306-1347)

Used by `new` and `rename`.

1. `fifo = path.join(os.tmpdir(), 'tmux_fzf_session_name')` → normally `/tmp/tmux_fzf_session_name`.
2. Validate: tmpdir is a non-empty string (`Could not determine temp directory`),
   `fifo.length <= 4096` (`FIFO path is too long`), `fifo` starts with tmpdir (`FIFO path validation failed`).
3. `rm -f <fifo>`
4. `mkfifo <fifo>`
5. Start (do NOT await) `bash -lc <promptCommand>` where `promptCommand` is built at line 1325.
   The intended command is:
   ```
   tmux split-window -v -l 30% -b "bash -c 'printf \"Session Name: \" && read session_name && echo \"$session_name\" > <fifo>'"
   ```
   The actual string that reaches bash has the escapes collapsed. See quirk Q8 — the prompt is broken.
6. `cat <fifo>` (blocking) → `stdout.trim()` is the result.
   * On error: if the error object carries `stdout`, return `String(error.stdout).trim()`, else `''`.
7. `finally`: `rm -f <fifo>`.

Layout: the prompt pane is a horizontal split (`-v`), 30% high, placed **before** the current
pane (`-b`, i.e. above it).

### 9.1 Two more failure modes (M8)

Line 1327 is `` $`bash -lc ${promptCommand}` `` with **no `await`** and **no `.catch`**.

| Failure | What happens today | What the Go port must do |
|---|---|---|
| `tmux split-window` fails (for example the pane is too small, or tmux is gone) | the promise rejects with nobody listening → Node raises an **unhandled rejection** and kills the process with a non-zero code, at an unpredictable moment | wait for the split command, check its error, and return `""` with a logged error instead of crashing |
| the split never runs, so nothing ever opens the fifo for writing | `cat <fifo>` (1330) **blocks forever**. The script hangs with no output and no timeout. | put a timeout on the read (suggested 60 s, matching a normal user prompt) and return `""` on timeout |

Neither case is handled today. Both are in scope for decision D7.

### 9.2 The Go replacement (BINDING)

Do not build a shell string. Q8 exists only because a shell string was built.
Recommended shape (also removes the Q8 quoting trap and both failure modes above):

```
tmux split-window -v -l 30% -b <helperBinary> --prompt-to <fifoPath>
```

or, without a helper mode, pass the inner script as **one** argv element:

```
exec.Command("tmux", "split-window", "-v", "-l", "30%", "-b",
             "sh", "-c", `printf 'Session Name: '; read n; printf '%s\n' "$n" > `+fifo)
```

The rule: the script text is **one** argv element that the Go code never re-quotes.
tmux joins its trailing arguments with single spaces and runs them through `/bin/sh -c`
(§0.9.3), so keep the script free of characters that need protecting, or use the helper form.

#### 9.2.1 The full required order (BINDING — added 2026-08-07)

The Python tests write straight into the FIFO and never type into the prompt pane. That makes
the *ordering* below part of the contract, not an implementation detail.

| # | Step | Why it is mandatory |
|---|---|---|
| 1 | `os.Remove(fifo)`, then `syscall.Mkfifo(fifo, 0666)` — **the first thing the action does**, inside ~200 ms | the test opens the path for writing at t ≈ 2.2 s. If the FIFO is not there yet, Python creates a plain **regular file** at that path, our later `mkfifo` fails with `EEXIST`, and the name is lost. The `rm -f` also clears a leftover regular file from a crashed run. |
| 2 | record the current pane id: `tmux display-message -p '#{pane_id}'` — **before** the split | there is no other reliable way to get back to it |
| 3 | `tmux split-window -v -l 30% -b sh -c <script>` with `<script>` as one argv element | see the shape above |
| 4 | the redirect `> <fifo>` sits on the **last `printf` only**, never on the whole script or a `{ … }` block | if the whole script is redirected, the pane's shell opens the write end at once. A read-to-EOF then never returns (a second writer is still open), and the read may pick up the pane's own empty line. |
| 5 | open the FIFO for **reading** and block; timeout **60 s** | Go reaches this point in milliseconds and then waits ~2.0 s for the test. A short timeout silently yields `""`, logs "no session name provided" and exits 0 — the test then fails with a confusing "session not found". Never go below ~5 s. |
| 6 | read the **first line only**, then stop | |
| 7 | `tmux kill-pane -t <paneID>` — **mandatory**, and within ~0.5 s of the read | `split-window` makes the new pane the **active** pane, and tmux routes the test's keystrokes to the active pane. If the prompt pane is still alive, the `rename` tests type `test_session` into the prompt shell instead of into fzf. Killing the pane also restores focus. |
| 8 | `os.Remove(fifo)` in a `defer`, only **after** the read returns | |

Go note: use `syscall.Mkfifo` and `os.Remove`. Do not shell out to `mkfifo` / `rm -f`.

---

## 10. fzf invocation

### 10.1 `runFzf(items, { header, includePreview, extraBindings })` (881-958)

1. Log `runFzf: called with <n> items, header: <h>, preview: <p>`.
2. `assertValidItemsArray(items, 'fzf items')` and `assertValidHeader(header)`.
   Note: an empty array throws here, so the `return ''` guard at 888-891 is dead code.
3. Copy the whole `process.env` and override:
   * `FZF_DEFAULT_OPTS = buildFzfDefaultOpts(header, extraBindings)`
   * `TMUX_FZF_RUN = buildFzfRunCommand(includePreview)`
4. Validate both with `assertValidFzfOptions`. If `TMUX_FZF_RUN` is empty → throw
   `TMUX_FZF_RUN command is empty.`
5. Build the bash script (907-911):
   ```
   \n
   set -e\n
   cat <<'__TMUX_FZF_INPUT__' | eval "$TMUX_FZF_RUN"\n
   <items joined by \n, with a guaranteed trailing \n>__TMUX_FZF_INPUT__\n
   ```
   The heredoc is quoted (`<<'…'`), so item text is passed literally (no expansion).
6. `spawn('bash', ['-ls'], { env, stdio: ['pipe','pipe','pipe'] })` — a **login** shell.
   The script text is written to its stdin and stdin is closed.
   fzf draws its UI on `/dev/tty`; stdout is captured by the parent.
7. Exit-code handling (932-947):

   | bash exit code | Behaviour |
   |---|---|
   | `0` | resolve with `stdout.trimEnd()` (the selection) |
   | `1` | resolve with `stdout.trimEnd()` (fzf: no match) |
   | `130` | resolve with `stdout.trimEnd()` (fzf: interrupted — Esc / Ctrl-C) |
   | anything else | reject with `bash exited with code <code>: <stderr>` |

   A rejection is not caught by any caller → the process crashes with a non-zero exit code.
8. A spawn error also rejects.

### 10.2 `buildFzfDefaultOpts(header, extraBindings)` (960-995)

**Validations first (M3).** All four are missing from earlier drafts. Order matters:

| # | Line | Check | Error text |
|---|---|---|---|
| 1 | 962-964 | if `header` is truthy → `assertValidHeader(header)` (§11.7) | `Header must be a string, got <t>` / `Header exceeds max length of 500 characters` / `Header cannot contain newlines` |
| 2 | 968-970 | if `extraBindings` is truthy and not a string | `extraBindings must be a string` |
| 3 | 971 | if `extraBindings` is truthy → `assertValidFzfOptions(extraBindings, 'extraBindings')` (§11.6) | `extraBindings must be a string, got <t>` / `extraBindings exceeds max length of 10000 characters` / `extraBindings cannot contain null bytes` |
| 4 | 992 | the joined result → `assertValidFzfOptions(result, 'Built FZF_DEFAULT_OPTS')` | `Built FZF_DEFAULT_OPTS exceeds max length of 10000 characters` / `Built FZF_DEFAULT_OPTS cannot contain null bytes` |

None of these is caught by a caller, so any failure **crashes** the process.
Note the field name in check 4 is literally `Built FZF_DEFAULT_OPTS`, with a space.

Parts, joined by a single space, with empty parts dropped, then trimmed:

| Order | Part |
|---|---|
| 1 | `baseFzfDefaultOpts` (the `FZF_DEFAULT_OPTS` value captured at line 40) |
| 2 | `--no-sort` |
| 3 | `--delimiter=" @ "` (the double quotes are literally in the string) |
| 4 | `--with-nth=1..` |
| 5 | `--nth=1` |
| 6 | `--header="<header>"` — only if `header` is truthy |
| 7 | `<extraBindings>` — only if truthy |

Meaning: fzf splits each row on `" @ "`; the whole row is displayed (`--with-nth=1..`) but
matching is limited to field 1 (`--nth=1`), i.e. `[3] myproject`. Sorting is disabled so the
frecency order and the `[N]` numbers stay aligned.

`header.replace(/"/g, '\"')` at line 982 is a no-op in JavaScript — see quirk Q9.

#### 10.2.1 The Go argv (BINDING — added 2026-08-07)

There is no `FZF_DEFAULT_OPTS` string to build any more. The options above become argv elements.
**Every quote in the table above is a shell quote. Drop all of them** (§0.9.2 is the same trap).

| Order | argv elements |
|---|---|
| 1 | the words of `TMUX_FZF_BIN` (default `fzf`), shell-split (§0.5) |
| 2 | the words of `TMUX_FZF_OPTIONS`, shell-split |
| 3 | `--no-sort` |
| 4 | `--delimiter`, ` @ ` — two elements. The value is a space, `@`, space. **No quotes.** |
| 5 | `--with-nth=1..` |
| 6 | `--nth=1` |
| 7 | `--with-shell`, `sh` — two elements. Forces POSIX `sh` for `--bind` commands (§0.5). |
| 8 | `--header`, `<header text>` — two elements, only if the header is non-empty. **No quotes**, so Q9 disappears. |
| 9 | one `--bind` plus its value, as two elements, for each binding |

`FZF_DEFAULT_OPTS` stays in the child environment untouched. fzf parses it itself, before argv,
so our argv wins on conflict and the user's `--reverse` still applies.

Validations that survive: `TMUX_FZF_BIN` non-empty and ≤ 1000 chars, `TMUX_FZF_OPTIONS` through
`assertValidFzfOptions`, and `assertValidHeader`. The "Built FZF_DEFAULT_OPTS" and
"Built TMUX_FZF_RUN" checks are replaced by one rule: if steps 1+2 yield zero words, fail with
the existing message `TMUX_FZF_RUN command is empty.`

### 10.3 `buildFzfRunCommand(includePreview)` (997-1023)

**Validations first (M2).** Four of them, all missing from earlier drafts:

| # | Line | Check | Error text |
|---|---|---|---|
| 1 | 1000 | if `TMUX_FZF_BIN` is truthy → `assertNonEmptyString(…, 'TMUX_FZF_BIN')` | `TMUX_FZF_BIN must be a string, got <t>` / `TMUX_FZF_BIN cannot be empty` |
| 2 | 1001 | if `TMUX_FZF_BIN` is truthy → `assertMaxLength(…, 'TMUX_FZF_BIN', 1000)` | `TMUX_FZF_BIN exceeds max length of 1000 (got <n>)` |
| 3 | 1004 / 1007 | if `TMUX_FZF_OPTIONS` / `TMUX_FZF_PREVIEW_OPTIONS` is truthy → `assertValidFzfOptions` (§11.6) | `<NAME> exceeds max length of 10000 characters` / `<NAME> cannot contain null bytes` |
| 4 | 1020 | the joined result → `assertValidFzfOptions(result, 'Built TMUX_FZF_RUN')` | `Built TMUX_FZF_RUN exceeds max length of 10000 characters` / `Built TMUX_FZF_RUN cannot contain null bytes` |

Note the max length for `TMUX_FZF_BIN` is **1000**, not 10000. The field name in check 4 is
literally `Built TMUX_FZF_RUN`, with a space. Nothing catches these — a failure crashes.

Parts, joined by a space, then all runs of whitespace collapsed to one space, then trimmed:

1. `TMUX_FZF_BIN`
2. `TMUX_FZF_OPTIONS` (if non-empty)
3. `TMUX_FZF_PREVIEW_OPTIONS` (only if `includePreview` is true AND the variable is non-empty)

With stock defaults this is just `fzf`.

**Go port (D5 + D9):** part 3 and its validation are deleted. Parts 1 and 2 are **shell-split**
into argv words instead of joined into a string — see §0.5. Keep validations 1, 2 and 3
(for `TMUX_FZF_OPTIONS`) with the same messages. Replace validation 4 with the empty-argv check
that still raises `TMUX_FZF_RUN command is empty.`

### 10.4 Selector summary table

| Caller | Header | Preview flag | Number prefixes | `[current]` row | `[cancel]` row | Extra bindings |
|---|---|---|---|---|---|---|
| `selectAction` | `Select an action.` | false | no | n/a | yes (item in the list) | none |
| `switch` | `Select target session. Press 1-9 for quick switch. DEL to kill. Ctrl+N/P to preview.` | true | yes | no (current row moved to top) | yes | del + ctrl-n + ctrl-p + 1..9 |
| `worktree-switch` | `Worktree sessions (<F>/<A>). Ctrl+N/P to preview.` | true | yes | no | yes | ctrl-n + ctrl-p |
| `capital-switch` | `CAPITAL sessions (<C>/<A>). Ctrl+N/P to preview.` | true | yes | no | yes | ctrl-n + ctrl-p |
| `rename` | `Select target session.` | true | yes | yes (literal `[current]`) | yes | none |
| `kill` | `Select target session(s). Press TAB to mark multiple items.` | true | yes | yes (literal `[current]`) | yes | none |
| `detach` | `Select target session(s). Press TAB to mark multiple items.` | true | **no** | yes (literal `[current]`) | yes | none |

The "Preview flag" column is the **kaomoji** `includePreview` flag. Decision D5 removes that whole
column from the Go port. The header **text** `Ctrl+N/P to preview.` stays exactly as written —
it refers to the Ctrl+N/P session preview, which is kept in full (§0.2, §7).

Popup geometry (all three popup actions): `-w 60% -h 90% -x R -y C -b rounded -E`,
titles `SESSIONS`, `WORKTREE SESSIONS`, `CAPITAL SESSIONS`
(the quotes around the titles in the source are shell quotes — §0.9.1 row 9).

---

## 11. Validation rules (1480-1641)

### 11.1 `assertNonEmptyString(value, field)`
* not a string → `<field> must be a string, got <typeof>`
* length 0 → `<field> cannot be empty`

### 11.2 `assertMaxLength(value, field, max)`
* runs `assertNonEmptyString` first
* length > max → `<field> exceeds max length of <max> (got <len>)`

### 11.3 `assertValidSessionName(name)` (1513-1542)

Checks, in this order:

| # | Rule | Error message |
|---|---|---|
| 1 | non-empty string | `Session name must be a string, got <t>` / `Session name cannot be empty` |
| 2 | length ≤ 100 | `Session name exceeds max length of 100 (got <n>)` |
| 3 | no `:` | `Session name cannot contain colons (:)` |
| 4 | no `.` | `Session name cannot contain periods (.)` |
| 5 | no `\n` and no `\r` | `Session name cannot contain newlines` |
| 6 | no `[\x00-\x1F\x7F]` | `Session name cannot contain control characters` |
| 7 | no `\0` | `Session name cannot contain null bytes` |
| 8 | matches the character class below — **not** a literal `\s` | `Session name can only contain letters, numbers, underscore, hyphen, and spaces` |

Rule 8 makes rules 3-7 redundant, but the error messages differ, so keep the order.

#### 11.3.1 Rule 8 — the exact accepted character set (W1)

> **Do NOT use Go's `\s` here.** A literal port of the JavaScript regex is WRONG and will
> **reject names that the `.mjs` accepts**.

The `.mjs` uses the JavaScript regex `/^[a-zA-Z0-9_\-\s]+$/` (`session-zx.mjs:1539`).
JavaScript `\s` is far wider than Go's `\s`:

| Engine | What `\s` means |
|---|---|
| JavaScript | Unicode whitespace + line terminators + U+FEFF (full list below) |
| Go `regexp` | only `[\t\n\f\r ]` — five ASCII characters |

Full JavaScript `\s` set:

| Code point(s) | Name |
|---|---|
| U+0009 | tab |
| U+000A | line feed |
| U+000B | vertical tab |
| U+000C | form feed |
| U+000D | carriage return |
| U+0020 | space |
| U+00A0 | no-break space |
| U+1680 | ogham space mark |
| U+2000 – U+200A | en quad … hair space (11 code points) |
| U+2028 | line separator |
| U+2029 | paragraph separator |
| U+202F | narrow no-break space |
| U+205F | medium mathematical space |
| U+3000 | ideographic space |
| U+FEFF | zero width no-break space (BOM) |

Rules 5 and 6 (`session-zx.mjs:1524-1531`) already reject U+000A and U+000D (rule 5) and
U+0000-U+001F plus U+007F (rule 6). That removes U+0009, U+000B, U+000C and U+000D before
rule 8 ever runs. So they can never be accepted, whatever rule 8 says.

**Effective accepted set — use exactly this in Go:**

```
^[A-Za-z0-9_\-\x{0020}\x{00A0}\x{1680}\x{2000}-\x{200A}\x{2028}\x{2029}\x{202F}\x{205F}\x{3000}\x{FEFF}]+$
```

In other words, rule 8 accepts, and only accepts:

| Accepted | Detail |
|---|---|
| `A`-`Z`, `a`-`z` | ASCII letters only. No accented letters, no Cyrillic, no CJK. |
| `0`-`9` | ASCII digits only |
| `_` | underscore |
| `-` | hyphen-minus U+002D |
| U+0020 | ASCII space |
| the 18 Unicode whitespace code points above (U+00A0, U+1680, U+2000-U+200A, U+2028, U+2029, U+202F, U+205F, U+3000, U+FEFF) | rarely used, but the `.mjs` accepts them |

Go note: `regexp.MustCompile` this class **once at package level**, never per call. Session-name
validation sits on the Ctrl+N / Ctrl+P keypress path, and compiling a 20-alternative class on
every invocation is measurable. The `\x{...}` escapes and the `\-` inside the class are valid
RE2 syntax, and Go's `$` (without `(?m)`) matches end-of-text only — which is what we want.

Only ASCII space is realistic in daily use. The Unicode entries matter for exact
bug-compatibility, and they are the reason W6 (see Q14) is worded the way it is.
Do **not** silently narrow this to `^[A-Za-z0-9_\- ]+$` — that is a user-visible change and
needs the owner's sign-off.

### 11.4 `assertValidAction(action)` — see §2.1.

### 11.5 `assertValidItemsArray(items, field)` (1572-1595)
* not an array → `<field> must be an array, got <typeof>`
* empty → `<field> cannot be empty`
* any element not a string → `<field>[<i>] must be a string, got <typeof>`
* any element longer than 1000 → `<field>[<i>] exceeds max length of 1000 characters`
* more than 10000 elements → `<field> has too many items: <n> (max 10000)`

### 11.6 `assertValidFzfOptions(value, field)` (1603-1617)
* not a string → `<field> must be a string, got <typeof>`
* length > 10000 → `<field> exceeds max length of 10000 characters`
* contains `\0` → `<field> cannot contain null bytes`

### 11.7 `assertValidHeader(header)` (1624-1641)
* `null`/`undefined` → allowed, returns
* not a string → `Header must be a string, got <typeof>`
* length > 500 → `Header exceeds max length of 500 characters`
* contains `\n` → `Header cannot contain newlines`

### 11.8 Inline checks inside `switch` — see the table in §3.11.

---

## 12. Exit codes

| Code | When |
|---|---|
| `0` | Normal completion of every action. Also: no action / `[cancel]` chosen; empty selection; no targets parsed; `reload-sessions` done; helper actions always exit 0; `kill-single` cancelled, timed out, or failed to kill; `worktree-switch` with no git repo or no matching sessions; `capital-switch` with no capital sessions; empty session name for `new`/`rename` (**C5: today this is not an edge case — it is the ONLY path `new` and `rename` ever take, because of Q8. See §3.8 and §3.12.**). |
| `1` | Invalid action (with `Error: …` on stderr); invalid session name in `new`, `rename`, `kill`, `detach`, `switch`, `kill-single` (with `Error: …` on stderr); invalid target in `worktree-switch` / `capital-switch` (log only, no stderr); missing argument for `kill-single`; session does not exist in `kill-single`; `tmux switch-client` failure in `new` and `switch`. |
| non-zero (crash) | Any uncaught throw: an unguarded `await $\`tmux …\`` failure, a `runFzf` rejection (bash exit code other than 0/1/130), the script-path / format-string checks in `switch`, or `TMUX_FZF_RUN command is empty.`. Node prints the stack to stderr. |

fzf exit codes seen by the script (through bash, because of the pipeline):

| fzf code | Meaning | Script behaviour |
|---|---|---|
| `0` | a selection was accepted | use `stdout` |
| `1` | no match | treated as an empty selection → action becomes a no-op, `exit 0` |
| `130` | interrupted (Esc, Ctrl-C) | treated as an empty selection → no-op, `exit 0` |
| `2` and others | fzf error | `runFzf` rejects → process crashes |

**Go port note (added 2026-08-07).** The table above is bash's view: today fzf runs under
`bash -ls` and bash forwards fzf's code. After the port we exec fzf directly, so read the codes
as fzf's own constants (`src/constants.go`):

| fzf constant | Code | Go behaviour |
|---|---|---|
| `ExitOk` | 0 | use stdout |
| `ExitNoMatch` | 1 | use stdout (empty) → no-op, exit 0 |
| `ExitInterrupt` | 130 | use stdout (empty) → no-op, exit 0 |
| `ExitError` | 2 | fzf failed. The usual cause is a malformed `TMUX_FZF_OPTIONS`. Log message 17, print fzf's own stderr as one line, exit 1. Do **not** print a Go stack trace. |
| `ExitBecome` | 126 | we never use `become()`; treat like any other unexpected code |
| anything else | — | same as `ExitError` |

This turns a bad `TMUX_FZF_OPTIONS` into a *user* error we can explain, where today it surfaces
as a bash error.

---

## 13. Logging (`logEvent`, 1647-1690)

| Item | Value |
|---|---|
| File | `<scriptDir>/session-zx.log` |
| Line format | `<ISO-8601 timestamp> <message>\n` — e.g. `2026-07-20T11:06:44.123Z action=switch: complete` |
| Timestamp | `new Date().toISOString()` — UTC, milliseconds, `Z` suffix |
| Append mode | yes, UTF-8 |
| Failure policy | **all errors are swallowed** — logging never breaks the script |

Rotation, checked **before every single append**:

1. `stat` the log file. If it does not exist → no rotation.
2. If `size > 262144` bytes → rotate.
3. Rotation: read the whole file as UTF-8, split on `\n`.
   Walk backwards from the last element, adding `byteLength(line + '\n')` each step.
   Stop as soon as adding the next line would push the total above `209715` bytes;
   set `keepFromIndex = i + 1`.
4. Write back `lines.slice(keepFromIndex).join('\n')`, plus a trailing `\n` if the result is non-empty.
5. Then append the new line.

So the log keeps roughly the newest 205 KiB and drops older lines. Rotation only trims in place —
there is no `.log.1` backup file.

Because the file is read fully into memory on rotation, a Go port can read only the tail.

### 13.1 How many messages exist today (M7)

`session-zx.mjs` has **167** `logEvent(...)` call sites. Earlier drafts gave the exact text for
about 25 of them (mostly in §7). There is no complete inventory in this document, and there will
not be one.

### 13.2 The Go port logs about 20 KEY events (BINDING — decision D4)

Keep the same file path and the same line format. Do **NOT** port all 167 sites.
Log exactly these events, and nothing else:

| # | When | Suggested message |
|---|---|---|
| 1 | process start | `script started` |
| 2 | current session resolved | `current session: <name>` |
| 3 | action chosen (argv or menu) | `action selected: <action>` |
| 4 | action about to run | `action=<action>` |
| 5 | switched to a session | `action=<action>: switched to <name>` |
| 6 | created a session | `action=new: created <name>` |
| 7 | renamed a session | `action=rename: renamed <old> to <new>` |
| 8 | killed a session | `action=<action>: killed <name>` |
| 9 | detached a session | `action=detach: detached <name>` |
| 10 | user cancelled (empty selection, `[cancel]`, empty name) | `action=<action>: cancelled` |
| 11 | debounce: switch scheduled | `session throttle: scheduled target=<name> token=<token>` |
| 12 | debounce: delayed switch executed | `session throttle: delayed switch executed for <name>` |
| 13 | debounce: delayed switch skipped (newer token won) | `session throttle: delayed switch skip token=<t>, stateToken=<s\|null>, target=<target\|(none)>` |
| 14 | debounce: state file could not be written | `session debounce: failed to write <path>: <msg>` |
| 15 | debounce: immediate fallback switch used | `session throttle: immediate fallback switch for <name>` |
| 16 | any tmux command failed | `<action>: tmux <subcommand> failed: <msg>` |
| 17 | fzf exited with an unexpected code | `runFzf: error, exit code <code>, stderr: <stderr>` |
| 18 | validation rejected an action or a session name | `Invalid action: <msg>` / `Invalid target session: <msg>` |
| 19 | `.envs` was applied, with the number of keys | `sourceEnv: applied <n> variables from <path>` |
| 20 | current session name failed validation (warning only, §1.1) | `Warning: Current session name is invalid: <msg>` |

Rules kept from today:

| Rule | Value |
|---|---|
| Line format | `<ISO-8601 UTC timestamp with milliseconds and `Z`> <space> <message>` then `\n` |
| Append mode | yes, UTF-8 |
| Failure policy | **swallow all logging errors.** Logging must never break the tool. |

Messages 11, 12, 13, 15 must keep their **exact** wording — the debounce behaviour is subtle and
these lines are the only way to debug it.

### 13.3 Rotation wipe bug — MUST FIX (M10)

`session-zx.mjs:1667-1681`:

```js
let keepFromIndex = lines.length;              // 1669
for (let i = lines.length - 1; i >= 0; i--) {
  const lineBytes = Buffer.byteLength(lines[i] + '\n', 'utf8');
  if (bytesCount + lineBytes > LOG_TRIM_TARGET) { keepFromIndex = i + 1; break; }
  bytesCount += lineBytes;
}
const kept = lines.slice(keepFromIndex).join('\n');
```

The bug: if a **single line** is larger than `LOG_TRIM_TARGET` (209715 bytes), the loop breaks on
that line with `keepFromIndex` pointing past every remaining line. `kept` becomes `''` and
**the whole log file is erased**. This is reachable: `logEvent` writes the full
`FZF_DEFAULT_OPTS` string (895) and the full stderr of a failed fzf (944), and both can be large.

The Go port must:

| Rule |
|---|
| never produce an empty result while the file still holds lines that fit |
| if the newest line alone is larger than the target, keep **that one line** and drop everything older |
| if the newest line alone is larger than `LOG_MAX_BYTES`, truncate the line itself rather than the file. **Truncate to exactly `logMaxBytes - 1` bytes.** With the newline the rewritten file is then exactly `logMaxBytes`, and rotation is `size > logMaxBytes`, so the very next `logEvent` cannot immediately re-trigger rotation on the same line. Truncating to `logMaxBytes` would leave a `logMaxBytes + 1` file that rotates forever. |
| truncate on a rune boundary, never in the middle of a UTF-8 sequence |
| write the trimmed content atomically (temp file + `Sync()` + `rename`) so a crash cannot leave a half file. Use the same `writeAtomic` helper as §0.3 and §7.1. |

---

## 14. Complete list of external commands

> ### ⚠️ READ §0.9 BEFORE USING THIS TABLE (M1)
>
> Every command below is written **exactly as it appears in the `.mjs` template**.
> zx runs each one through `bash -c`, so **all the quotes you see here are SHELL quotes.**
> Bash removes them. The program never receives them.
>
> **Never copy a quote from this table into `exec.Command`.**
> `-F '#S @ #{session_windows} windows'` becomes the Go argument
> `"#S @ #{session_windows} windows"` — no single quotes.
> `display-message "Not in a git repository"` becomes the Go argument
> `"Not in a git repository"` — no double quotes.
>
> The translation table for the tricky ones is in **§0.9.1**. What silently breaks if you get it
> wrong is in **§0.9.2**.

### tmux

| Command | Line | Guarded? |
|---|---|---|
| `tmux display-message -p '#S'` | 1350 | no |
| `tmux display-message -p '#{pane_current_path}'` | 296 | no |
| `tmux list-sessions -F '#S @ #{session_windows} windows'` | 1077 | no |
| `tmux list-sessions` | 1135 | no |
| `tmux list-panes -a -F '#{session_name}\t#{pane_current_path}'` | 1174 | no |
| `tmux has-session -t <name>` | 178 | yes (try/catch) |
| `tmux new-session -d -s <name>` | 279 | no |
| `tmux switch-client -t <name>` | 282, 362, 427, 529, 807, 831, 867 | 282/529/807/831/867 yes, 362/427 no |
| `tmux rename-session -t <old> <new>` | 586 | no |
| `tmux kill-session -t <name>` | 103, 239, 622 | 103/239 yes, 622 no |
| `tmux detach -s <name>` | 656 | no |
| `tmux display-message "Session <name> does not exist"` | 182 | no |
| `tmux display-message "Not in a git repository"` | 304 | no |
| `tmux display-message "No sessions found for this project's worktrees"` | 321 | no |
| `tmux display-message "No CAPITAL sessions found"` | 389 | no |
| `tmux display-popup -E -w 60% -h 90% -x R -y C -T "<TITLE>" -b rounded <script> <action>` | 61, 70, 79 | no |
| `tmux split-window -v -l 30% -b "<prompt shell command>"` | 1325 (run at 1327) | not awaited — see the warning below |

### git

| Command | Line |
|---|---|
| `git -C <dirPath> worktree list --porcelain` | 1151 |

### shell / other

| Command | Line | Purpose |
|---|---|---|
| `bash -lc 'source "<envsPath>" >/dev/null 2>&1 && env'` | 1380 | load `.envs` |
| `bash -ls` (script on stdin) | 916 | run fzf via a heredoc + `eval "$TMUX_FZF_RUN"` |
| `bash -lc <promptCommand>` | 1327 | open the tmux prompt pane |
| `rm -f <fifo>` | 1323, 1344 | fifo lifecycle |
| `mkfifo <fifo>` | 1324 | fifo lifecycle |
| `cat <fifo>` | 1330 | read the typed session name |
| `spawn(node, [<script>, 'delayed-switch', <token>])` detached | 822 | debounced switch |

### 14.1 ⚠️ The `split-window` row does NOT work today (W5 / C3)

The row `tmux split-window -v -l 30% -b "<prompt shell command>"` (1325, run at 1327) looks like a
normal command. **It is not.** The string that actually reaches bash has its escapes collapsed,
bash then word-splits it in the wrong places, and the result writes an **empty line** to the fifo
no matter what the user types.

Consequences: `new` and `rename` are **dead** in interactive use today.
Full trace and the required Go fix: **quirk Q8** and **§9.2**.
Do not read this table row on its own and assume the command works.

### 14.2 Guard status — what "guarded" means

"Guarded? = no" means the `await $\`…\`` has **no** `try/catch`. In zx a non-zero exit throws, and
an uncaught throw ends the process with a stack trace on stderr (§12, last row).
The Go port must decide per call: either keep the crash (bug-compatible) or handle the error.
Recommended: handle every tmux error, log it (§13.2 message 16), print a short message to stderr
and exit 1. Note this is a deliberate difference from the `.mjs` and record it in the release notes.

---

## 15. Edge cases

| Situation | Behaviour | Exit code |
|---|---|---|
| Not inside tmux (no server) | `tmux display-message -p '#S'` fails at line 43 → uncaught throw, stack on stderr | non-zero crash |
| Zero tmux sessions, `switch` | **UNREACHABLE (W3).** Line 43 runs `getCurrentSession()` first and must succeed, so at least one session always exists by the time `switch` runs. With no tmux server, `tmux list-sessions` (1077) exits non-zero, zx throws, and the process **crashes** — it does not show an empty list. | non-zero crash |
| Exactly one tmux session, `switch` | items = `[1] <current> @ N windows` and `[cancel]`. Accepting `[1]` switches to the session the user is already in — a tmux no-op (Q13, kept by decision D3). | 0 |
| fzf: user presses Esc | fzf exits 130, stdout empty → `parseTargets` → `[]` → no-op | 0 |
| fzf: query matches nothing, user presses Enter | fzf exits 1, stdout empty → no-op | 0 |
| fzf: user selects `[cancel]` | `parseTargets` returns `[]` → no-op | 0 |
| Action menu returns empty string | early exit at line 52 | 0 |
| `worktree-switch` outside a git repo | `tmux display-message "Not in a git repository"` | 0 |
| `worktree-switch` in a repo but no session has a pane there | `tmux display-message "No sessions found for this project's worktrees"` | 0 |
| `capital-switch` with no uppercase-only session names | `tmux display-message "No CAPITAL sessions found"` | 0 |
| `kill-single` on a missing session | `tmux display-message "Session <name> does not exist"` | 1 |
| `kill-single`, no key pressed for 30 s | stdout `✗ Timeout or error, kill cancelled` | 0 |
| `new`/`rename`, empty name from the prompt | log and exit, no tmux call | 0 |
| `new` with an invalid name (e.g. `my.session`) | stderr `Error: Session name cannot contain periods (.)` | 1 |
| Unknown action `foo` | stderr `Error: Invalid action: foo. Must be one of: …` | 1 |
| `kill-single-from-line` with `[cancel]` as the line | runs `tmux kill-session -t '[cancel]'`, which fails; error swallowed | 0 |
| Debounce file not writable | immediate switch instead of a debounced one | 0 |
| `spawn` of the delayed child fails | immediate switch instead | 0 |
| Two Ctrl+N presses within 300 ms | only the last one switches; the first child logs a `skip` line | 0 |
| `.envs` missing in both locations | defaults are used | — |
| `KaomojiList/kaomojis.json` missing | fallback `(^_^)` text; nothing observable, because nothing reads it | — |
| `.session-frecency` directory missing | `node-localstorage` creates it; all scores are 0, so tmux's own order is kept | — |
| DEL pressed in the `switch` list | the session under the cursor is killed and the list is reloaded via `reload-sessions`; the `[cancel]` row disappears after the reload — (`.mjs` today; the Go port does the opposite — Q7 FIX: the reloaded list keeps `[cancel]` and keeps the current session pinned) | 0 |
| Selected line is the 10th or later (no `[N] ` prefix) and the name starts with `-` | minimist may parse the argument as a flag, so `argv._[1]` is missing and the helper becomes a no-op | 0 |
| Argument is the literal `0` (session named `0`, or `session-zx.mjs 0`) | JavaScript treats `0` as falsy, so the argument is seen as missing — see §1.2 | 0 or 1 |
| A tmux session whose name starts with `[` (e.g. `[work]`) | `addNumberPrefixes` gives it no number and consumes no number — see §4.3, M12 | 0 |
| A single log line larger than 209715 bytes, and the log is over 256 KiB | the whole log file is erased — see §13.3, M10 | 0 (logging errors are swallowed) |
| `kill-single` with stdin not a TTY (piped, redirected, `/dev/null`) | `✗ Timeout or error, kill cancelled` **immediately**, no 30 s wait — see §3.7 step 5, M9 | 0 |
| `tmux split-window` fails during `new` / `rename` | unhandled promise rejection kills the process at an unpredictable moment — see §9.1, M8 | non-zero crash |
| Nothing ever opens the fifo for writing | `cat <fifo>` blocks forever; the script hangs with no output — see §9.1, M8 | (hangs) |

---

## 16. Observed environment — ground truth on this machine (M15)

Checked on the real checkout. This is what the code actually does **today**, not what it was
designed to do. It matters for the port and for writing tests.

| Fact | Consequence |
|---|---|
| `<scriptDir>/.envs` does **not** exist | `sourceEnv` (§8.1) finds nothing |
| `<homedir>/.tmux/plugins/tmux-fzf/scripts/.envs` does **not** exist | `sourceEnv` is a complete **no-op**. Q5 cannot bite today. |
| `<scriptDir>/KaomojiList/` does **not** exist | `pickPreviewKaomoji` always takes its fallback path. Irrelevant anyway — dropped by D5. |
| `TMUX_FZF_PREVIEW_OPTIONS` is never set (Q2 + no `.envs`) | `includePreview` has **no effect** at any of its six call sites |
| `TMUX_FZF_BIN` / `TMUX_FZF_OPTIONS` are never set | `TMUX_FZF_RUN` is always exactly `fzf` |
| `<scriptDir>/.session-frecency/` does **not** exist | every frecency score is `0`, so the session order is exactly tmux's own order |
| `node_modules/` is **empty** | the `@getstation/frecency` on-disk format cannot be inspected — which is why decision D6 defines a new one |

So the current baseline behaviour of the tool is: plain `fzf`, no preview pane, no frecency
ordering, no `.envs`. Tests should assume this baseline unless they set the variables themselves.

---

## Known quirks and suspected bugs

Labels: **FIX** = change during the Go port. **KEEP** = keep the current behavior.
**DROP** = delete the feature, so there is nothing left to fix.

Every label below is final. It already includes the owner decisions in §0 and the verifier's
re-classification. Summary table first:

| Quirk | Short name | Label | Why |
|---|---|---|---|
| Q1 | `TMUX_FZF_SWITCH_CURRENT` unused | **KEEP (owner decision D3)** | "fixing" it hides the current session and shifts every 1-9 shortcut. Delete the variable, keep the behavior. |
| Q2 | kaomoji sets the wrong variable | **DROP (D5) — now moot** | the whole kaomoji pane is removed, so there is no bug left |
| Q3 | detach filter is always empty | **FIX (D7)** | detach must work for other sessions; keep the `[current]` row (§3.14.1) |
| Q4 | `TMUX_FZF_SESSION_FORMAT` unused | **DROP** | delete the variable and both validations |
| Q5 | `sourceEnv` imports the whole login env | **FIX (D8), with the `PATH` exception** | see §0.4 |
| Q6 | debounce env read too early | **FIX** | read after `.envs`; treat `0` as no delay |
| Q7 | `reload-sessions` output shape differs | **FIX (small)** | see the interaction note in Q7 |
| Q8 | prompt quoting sends an empty name | **FIX (D7) — mandatory** | `new` and `rename` are unusable today |
| Q9 | header quote escape is a no-op | **FIX** | pass `--header` as its own argv element |
| Q10 | dead `extractSessionNameFromLine` | **FIX (delete)** | |
| Q11 | dead empty-items guard | **FIX (delete)** | |
| Q12 | duplicate `[current]` in rename / kill | **FIX (small)** | |
| Q13 | `switch` pins the current session as `[1]` | **KEEP (owner decision D3)** | same reason as Q1 |
| Q14 | kill in reverse lexicographic order | **KEEP** | |
| Q15 | helper actions not in the valid-action list | **KEEP (document)** | |
| Q16 | `bash -ls` login shell can clobber the options | **FIX (D9), with a shell-word splitter** | see §0.5 |
| Q17 | no quoting on the fzf binding paths | **FIX** | |

### Q1 — `TMUX_FZF_SWITCH_CURRENT` is computed but never used — **KEEP (owner decision D3)**

> **Decision D3 (§0.1): KEEP TODAY'S BEHAVIOR.**
> The current session **stays** in the switch list, **stays** pinned to the top, and **keeps** the
> `[1]` prefix. The `1..9` shortcuts keep their present positions.
> `TMUX_FZF_SWITCH_CURRENT` is dead: **DELETE the variable. Do not implement it.**
>
> Why: `TMUX_FZF_SWITCH_CURRENT` is normally unset, so "fixing" this makes `excludeCurrent`
> **true** by default. The current session would disappear from the list and **every** 1-9
> shortcut would shift by one. That is a daily-driver muscle-memory break for the owner.
>
> The text below stays as a description of the current code. Ignore its old "Fix:" suggestion.

`session-zx.mjs:46`
```js
const excludeCurrent = !process.env.TMUX_FZF_SWITCH_CURRENT;
```
`session-zx.mjs:47` logs it, and that is the last use. Every call site passes a literal
`excludeCurrent: false` instead: lines 87, 313, 377, 437. The parameter is honoured inside
`getSessionsList` at 1125-1131, so the filtering code works — it is simply never asked for.

Intent: when `TMUX_FZF_SWITCH_CURRENT` is unset, the current session should be removed from
the switch list. Actual: the current session is always in the list (and, in `switch`, it is even
pinned to the top and gets the `[1]` prefix, so pressing `1` "switches" to the session you are
already in).

~~Fix: pass the computed `excludeCurrent` to the session-list call for `switch`.~~
**Superseded by decision D3.** Do not do this. Delete `excludeCurrent`, delete the
`TMUX_FZF_SWITCH_CURRENT` read, and delete the `excludeCurrent` branch inside `getSessionsList`
(§4.1 step 7) — with the variable gone, that branch is unreachable.

### Q2 — the kaomoji preview is broken — **DROP (decision D5): now MOOT**

> **Decision D5 (§0.1): the kaomoji preview pane is DROPPED from the Go port.**
> There is nothing left to fix, so **Q2 is moot**. Do not implement a preview pane, do not
> port `pickPreviewKaomoji`, `KAOMOJI_PREVIEW_TEXT` or `TMUX_FZF_PREVIEW_OPTIONS`.
>
> **This does NOT touch Ctrl+N / Ctrl+P.** The Ctrl+N / Ctrl+P session preview — the
> debounce / delayed-switch feature described in §7 — is **KEPT IN FULL**. It is a different
> feature that happens to share the word "preview". Read §0.2 before you delete anything.
>
> The description below stays as history.

`session-zx.mjs:1416-1423`
```js
  if (!process.env.TMUX_FZF_PREVIEW_OPTIONS) {
    const kaomoji = await pickPreviewKaomoji();
    process.env.KAOMOJI_PREVIEW_TEXT = kaomoji;
    // process.env.TMUX_FZF_PREVIEW_OPTIONS = [
    //   '--preview \'node -e "process.stdout.write((process.env.KAOMOJI_PREVIEW_TEXT || \\"(^_^)\\") + \\"\\n\\");"\'',
    //   '--preview-window=left:40%'
    // ].join(' ');
  }
```
Two problems in one block:
1. The guard tests `TMUX_FZF_PREVIEW_OPTIONS` but the body assigns `KAOMOJI_PREVIEW_TEXT`.
2. The assignment that would actually use `KAOMOJI_PREVIEW_TEXT` is commented out.

Result: `TMUX_FZF_PREVIEW_OPTIONS` stays unset, so `buildFzfRunCommand` never adds preview options
(1014-1016), so the `includePreview: true` flag passed by six call sites has **no effect**.
`pickPreviewKaomoji()` (a file read plus random picks) runs on every invocation and is thrown away.
`KAOMOJI_PREVIEW_TEXT` is dead — nothing reads it (only 1418 and the commented line 1420 mention it).

Fix (settled): drop the kaomoji machinery entirely. Do not port `KAOMOJI_PREVIEW_TEXT`,
`TMUX_FZF_PREVIEW_OPTIONS` or the `includePreview` flag. See §0.2 for the full removal list.

### Q3 — the `detach` FILTER is always empty (the list always has 2 rows) — **FIX (D7)**

> **Title corrected (C4).** The old title said "the detach list is always empty". That is wrong.
> The **filter result** is always empty. The **list** always shows exactly two rows,
> `[current]` and `[cancel]`, and picking `[current]` really does detach the current session.
> Full CAN / CANNOT table: **§3.14.1**. Do not drop the `[current]` row when you fix this.

`session-zx.mjs:1134-1142`
```js
async function getAttachedSessionNames() {
  const { stdout } = await $`tmux list-sessions`;
  const lines = parseLines(stdout);
  return new Set(lines.filter(l => l.includes('attached')).map(l => extractSessionName(l)));
}
```
`tmux list-sessions` with no `-F` prints the default format, e.g.
`work: 3 windows (created Mon Jul 20 11:00:00 2026) (attached)`.
`extractSessionName` (1265-1274) looks for the separator `' @ '`. The default format has no `' @ '`,
so the function returns the **entire raw line**. The set therefore contains full descriptive lines,
never bare names.

Then `selectDetachSessions` (716) does
`sessions.filter(line => attachedNames.has(extractSessionName(line)))`, where `line` looks like
`work @ 3 windows`, so `extractSessionName` yields `work`. `work` is never in the set.
**The filter always yields zero sessions**, so the detach picker only ever shows
`[current]` and `[cancel]`.

Fix: use `tmux list-sessions -F '#{session_name}'` filtered by `#{session_attached}`, or use
`-F '#S @ #{session_attached}'`. Recommended Go form:
`tmux list-sessions -F '#{session_name}\t#{session_attached}'` and keep the names where the
second field is not `0`.

### Q4 — `TMUX_FZF_SESSION_FORMAT` is validated but never applied — **DROP**

`session-zx.mjs:445` and `1063` read the variable; `461-471` and `1067-1074` validate it.
The actual tmux call at `1077` hard-codes `'#S @ #{session_windows} windows'`.

So a user who sets `TMUX_FZF_SESSION_FORMAT` gets validation errors but no change in output.

Note this is stronger than "no change in output": removing the variable also removes a real
**crash path**. Today a value over 500 characters, or (in `switch` only) a value containing
`` ` `` `$` `;` `|` `&` `<` `>` `(` `)`, throws an uncaught error at 465/469/1069/1072 and kills
the process. The two validations are not even identical — see §4.1 step 2 (M4).

Decision: **remove** the variable and both validations. Honouring it is not an option, because the
whole parsing chain (`columnFormat`, `extractSessionName`, `--delimiter=" @ "`) assumes the
`' @ '` separator. Document the removal in the release notes — it is a user-visible config key,
even though nothing in this repo sets it.

### Q5 — `sourceEnv` imports the whole login-shell environment — **FIX (D8), with the `PATH` exception**

> **Decision D8 (§0.1): apply the fix, but PRESERVE `PATH` behavior.**
> Today `sourceEnv` overwrites `PATH` with the login shell's `PATH` (1383-1385), and that `PATH`
> is what later resolves `tmux`, `git` and `fzf`. A naive diff-only fix can break tool lookup on
> machines where tmux starts the process with a thin `PATH`.
> **The exact required rules are in §0.4.** Verify on the real target machine before shipping:
> `.envs` exists in neither location on this one (§16), so today the whole function is a no-op.

`session-zx.mjs:1379-1385`
```js
const script = `source "${quoted}" >/dev/null 2>&1 && env`;
const { stdout } = await $`bash -lc ${script}`;
const envMap = parseEnvOutput(stdout);
Object.entries(envMap).forEach(([key, value]) => { process.env[key] = value; });
```
`env` prints every variable of the login shell, not just the ones `.envs` defines. All of them
overwrite the current process environment — including `PATH`, `PWD`, `SHLVL`, `_`, and anything
the user's `~/.bash_profile` exports. Values that contain newlines are also split wrongly by
`parseEnvOutput` (it skips lines without `=`).

Fix: diff the environment (run `env` once before and once after sourcing) and apply only the keys
that changed — **plus `PATH` always**, and never the process-local keys listed in §0.4 step 5.

### Q6 — `SESSION_SWITCH_DEBOUNCE_MS` cannot be set from `.envs` — **FIX**

`session-zx.mjs:26` runs at module top level, **before** `await sourceEnv()` at line 37.
Every other tunable is read after sourcing. So putting `SESSION_SWITCH_DEBOUNCE_MS=500` in
`.envs` has no effect; only a real process environment variable works.

Also note `parseInt(x, 10) || 300`: the values `0`, `""`, `"abc"` and `NaN` all become `300`,
so the debounce cannot be disabled by setting it to `0`.

Fix: read the variable after loading `.envs`, and treat an explicit `0` as "no delay".

### Q7 — `reload-sessions` output is not identical to the initial list — **FIX (small)**

`session-zx.mjs:87` calls `getSessionsList({ currentSession: null, excludeCurrent: false })`
with `currentSession: null`, and `92` prints the numbered rows without appending `[cancel]`.
The initial `switch` list (§4.2) pins the current session to the top and always ends with `[cancel]`.

So after the user presses DEL once, the list silently changes shape: the current session may move,
and the `[cancel]` row disappears. Further DEL presses still work, but there is no cancel row and
Esc is the only way out.

Fix: make `reload-sessions` produce exactly the same rows as the initial list — pin the current
session to the top and append `[cancel]`.

**Interaction note.** `reload-sessions` and the initial list must always agree on which sessions
are shown and in which order. Under decision D3 both keep the current session, so one rule covers
both. If the owner ever revisits D3, **both** paths must change together — otherwise the list
changes shape after the first DEL press.

### Q8 — the `new` / `rename` name prompt is broken by quoting; it always returns an empty name — **FIX (D7) — MANDATORY**

`session-zx.mjs:1325`
```js
const promptCommand = `tmux split-window -v -l 30% -b "bash -c 'printf \"Session Name: \" && read session_name && echo \"$session_name\" > ${fifo}'"`;
```
In a JavaScript template literal, `\"` collapses to a plain `"`. The string that reaches
`bash -lc` is:
```
tmux split-window -v -l 30% -b "bash -c 'printf "Session Name: " && read session_name && echo "$session_name" > /tmp/tmux_fzf_session_name'"
```
Bash then splits it into these words (verified by reproducing the tokenisation):
```
[tmux] [split-window] [-v] [-l] [30%] [-b]
[bash -c 'printf Session] [Name:] [ && read session_name && echo  > /tmp/tmux_fzf_session_name']
```
Two consequences:
1. The inner command becomes `printf Session Name: && read session_name && echo  > <fifo>`,
   so the prompt text prints as `Session` (printf treats `Name:` as an ignored extra argument).
2. `$session_name` is expanded by the **outer** `bash -lc`, where it is unset, so it expands to an
   empty string. The inner `echo` therefore writes a single empty line to the fifo, no matter what
   the user typed.

`promptSessionName` reads `"\n"`, trims it to `""`, and both `new` (264-267) and `rename` (547-550)
log "no session name provided" and exit 0. **`new` and `rename` are dead in interactive use.**
The existing pytest suite hides this: `tests/helpers/workflow.py:30` writes the name straight into
`/tmp/tmux_fzf_session_name`, bypassing the prompt.

Fix: in Go, do not build a shell string at all. Either use
`tmux command-prompt -p "Session Name:" "run-shell '<binary> ... %%'"`, or pass the inner command
as a properly quoted single argument, e.g.
`tmux split-window -v -l 30% -b <sh> -c <script>` with the script as one argv element.
Concrete shapes and the two extra failure modes (unhandled rejection, infinite fifo wait) are in
**§9.1 and §9.2**. `new` and `rename` MUST work after the port — decision D7.

Test note: `tests/helpers/workflow.py` writes the name straight into the fifo, so the existing
tests will keep passing whatever the port does here. Add at least one test that drives the real
prompt, or the bug can come back unnoticed.

### Q9 — the header quote escape is a no-op — **FIX (cosmetic, but a real injection risk)**

`session-zx.mjs:982`
```js
const fixed = header.replace(/"/g, '\"');
parts.push(`--header="${fixed}"`)
```
In JavaScript `'\"'` is just `"`, so this replaces `"` with `"` — nothing happens. The header is
then embedded inside `--header="..."` in `FZF_DEFAULT_OPTS`, which fzf splits shell-style. A header
containing a double quote would break the option string.

Today all headers are hard-coded and quote-free, so nothing breaks. But a header does interpolate
counts (`Worktree sessions (<F>/<A>)`), so the pattern is fragile.

Fix: in Go, pass `--header` as its own argv element and never go through a shell-parsed
options string. If a shell string is unavoidable, escape properly (`\"` → backslash + quote).

### Q10 — dead code: `extractSessionNameFromLine` — **FIX (delete)**

`session-zx.mjs:474-477` defines a local helper inside the `switch` branch:
```js
function extractSessionNameFromLine(line) {
  return line.split(/\s+/)[0];
}
```
Nothing calls it. It is also wrong for numbered rows (it would return `[1]`). Do not port it.

### Q11 — dead code: the empty-items guard in `runFzf` — **FIX (delete)**

`session-zx.mjs:885` calls `assertValidItemsArray(items, 'fzf items')`, which throws
`fzf items cannot be empty` for an empty array (1577-1579). The guard at `888-891`
(`if (!items || items.length === 0) return '';`) can therefore never run.
In practice this never triggers, because `selectSessions` always appends `[cancel]`.

### Q12 — `rename` and `kill` show a duplicate way to pick the current session — **FIX (small)**

`session-zx.mjs:562-567` and `593-598` call `selectSessions` **without** `currentSession`.
Inside `selectSessions` (689) that takes the `else` branch, so a literal `[current]` row is
prepended AND the real current session line is still in the list. The user sees two rows that
mean the same session. `switch` / `worktree-switch` / `capital-switch` do pass `currentSession`,
so they behave differently.

`parseTargets` still resolves `[current]` correctly (1235), so nothing crashes — the UI is just
inconsistent between actions.

Fix: pick one convention. Recommended: always pass the current session and pin it to the top;
drop the `[current]` pseudo-row.

### Q13 — the `switch` selector always includes the current session as `[1]` — **KEEP (owner decision D3)**

`session-zx.mjs:689-698` pins the current session line to the top, and `addNumberPrefixes`
gives it `[1]`. Combined with the `1:pos(1)+accept` binding (the literal is at **488**, inside the
array that starts at 487 — W4), pressing `1` runs `tmux switch-client` to the session the user is
already in. That is a harmless no-op in tmux.

> **Decision D3 (§0.1): KEEP.** This is the same change as Q1 and carries the same risk —
> it shifts every 1-9 shortcut by one position. The owner uses these shortcuts daily.
> Port it exactly as it is today.

### Q14 — `kill` deletes in reverse lexicographic order — **KEEP**

`session-zx.mjs:618`: `const ordered = targets.slice().sort().reverse();`
This is a plain JavaScript string sort (UTF-16 code units), then reversed.

The conclusion for Go is unchanged: **`sort.Strings` then reverse gives the same order.**
But the old reason given here was wrong (W6). It said "for ASCII session names (the only ones the
validator allows)". The validator allows more than ASCII — see §11.3.1: JavaScript `\s` admits
U+00A0, U+2000-U+200A, U+3000, U+FEFF and more. The correct reason is:

| Fact | Why the orders still match |
|---|---|
| Go compares strings by **UTF-8 bytes** | UTF-8 byte order equals Unicode code-point order |
| JavaScript compares by **UTF-16 code units** | equals code-point order for every non-surrogate BMP character |
| Every character rule 8 accepts is a non-surrogate BMP character (max U+FEFF) | so both comparisons give the same result |

Keep the reverse order. The sort is on names, not indexes, so the original intent is unclear, but
the behavior is harmless and cheap to copy.

### Q15 — helper actions are not in the valid-action list — **KEEP (document)**

`switch-from-line`, `kill-single-from-line` and `delayed-switch` are missing from
`assertValidAction` (1550-1555) but are routed before the gate (96, 112, 119). This is
deliberate-looking and required for the fzf bindings to work. Keep the routing, but in the Go port
add them to the known-action list so the error message is honest.

### Q16 — `bash -ls` (login shell) can clobber the fzf options — **FIX (D9), with a shell-word splitter**

`session-zx.mjs:916`: `spawn('bash', ['-ls'], { env, ... })`.
The `-l` flag makes bash read `/etc/profile` and `~/.bash_profile`. If any of those set
`FZF_DEFAULT_OPTS`, the carefully built value from line 893 is overwritten before fzf runs.
The same risk applies to `TMUX_FZF_RUN`.

Fix: in Go, exec fzf directly with an argv slice and an explicit environment. No shell,
no heredoc, no `eval`. Feed the items on fzf's stdin.

> **Decision D9 (§0.1) — the fix is NOT complete without a splitter.**
> `TMUX_FZF_BIN` and `TMUX_FZF_OPTIONS` are **raw shell strings** today. bash `eval`s them
> (line 909). A user can legally set `TMUX_FZF_BIN="fzf-tmux -p 80%"` or
> `TMUX_FZF_OPTIONS="--bind 'ctrl-a:select-all'"`. If the port just passes each variable as one
> argv element, both break silently.
>
> **Required:** split both with a **POSIX `sh` word splitter** (quotes and backslashes honoured;
> no variable expansion, no command substitution, no globbing, no redirection).
> The exact table of what must and must not be supported is in **§0.5**.
> In Go: **`github.com/kballard/go-shellquote`** (`Split`). Not `google/shlex` — it is archived
> and its double-quote backslash rule contradicts the §0.5 table. Corrected 2026-08-07.
>
> Also note the login shell is what puts `fzf` on `PATH` on some machines. That is covered by the
> `PATH` rule in §0.4 — do not drop the shell before that rule is in place.

### Q17 — no shell quoting on the fzf binding command paths — **FIX**

`session-zx.mjs:481-483, 331-332, 396-397` build binding strings by string concatenation:
```
--bind 'del:execute(<scriptPath> kill-single-from-line {})+reload(<scriptPath> reload-sessions)'
```
The script path is checked for metacharacters at `455`, but a path containing a single quote or a
space is not handled — a space would silently split the command inside `execute(...)`.
Note the metacharacter check rejects `[` and `]`, so a path such as `/home/u/[work]/hoppy`
fails with `Script path contains unsafe characters` even though it is harmless.

Fix: in Go, quote the binary path when building the binding string, and relax the character
blacklist to a proper quoting routine.

**Exact fix (added 2026-08-07):**

1. Pass `--with-shell`, `sh` in our own argv. Without it fzf runs the inner command with
   `$SHELL -c`, and POSIX quoting is wrong under `fish` or `nushell` (§0.5).
2. Build the binding with `shellquote.Join`, and **do not** put `{}` through it — `{}` is fzf's
   placeholder and fzf applies its own quoting to the substituted value:
   ```go
   "execute(" + shellquote.Join(bin, "kill-single-from-line") + " {})"
   ```
3. Delete the metacharacter blacklist at `session-zx.mjs:455`. With proper quoting a path such
   as `/home/u/[work]/hoppy` is harmless, and today it is rejected for no reason.
   Keep the two other `switch` preconditions: the path is a non-empty string, and its length
   is ≤ 4096 (§3.11).

---

## Open questions

### Already ANSWERED — do not reopen

| Old question | Answer |
|---|---|
| Q-A — exact frecency write format | **Answered by D6 / §0.3.** New JSON format owned by us. Cap = 10 timestamps, newest last. Do not reverse-engineer the library. |
| Q-B — should `worktree-switch` / `capital-switch` honour `TMUX_FZF_SWITCH_CURRENT`? | **Answered by D3.** The variable is deleted. No selector ever hides the current session. |
| Q-C — what should `1..9` mean after Q1 is fixed? | **Answered by D3.** Q1 is not fixed. `1..9` keep exactly today's positions. |
| Q-G — remove or implement `TMUX_FZF_SESSION_FORMAT`? | **Answered: remove** (Q4, §0.6). |

### Still open

| # | Question | Impact | Suggested answer |
|---|---|---|---|
| **O-1** | ~~Does `fzf` support `pos(N)`?~~ **MOSTLY ANSWERED 2026-08-07.** The floor is now **fzf 0.51.0**, not 0.36.0: `pos(N)` needs 0.36.0, but `--with-shell` (required by §0.5 / Q17) needs 0.51.0. | The test image is safe. The owner's host machine is not yet checked. | Test image **pins fzf 0.60.3** from the release tarball (`Dockerfile`, `ARG FZF_VERSION`). Still to do: run `fzf --version` on the host and record `fzf >= 0.51.0` in the README. |
| **O-2** | What exit code should the Go port use for an internal error (the cases where the `.mjs` crashes with a Node stack trace)? | User-visible; scripts may check it. | `1`, with a one-line message on stderr and no stack trace. Confirm with the owner. |
| **O-3** | Should the Go port write `detach-client -s` instead of `tmux detach -s` (1656)? `detach` is a tmux alias, so both work. | Cosmetic only, no behavior change. | Yes, use the full name `detach-client`. Confirm. |
| **O-4** | Argument handling of a literal `0` (§1.2). Go has no falsy-number rule, so an exact port is impossible without adding one on purpose. | A session named `0` works in Go but not in the `.mjs`. | Use "argument present = argument given". This is a small, deliberate improvement. Confirm and put it in the release notes. |
| **O-5** | Should unguarded tmux failures keep crashing (bug-compatible) or be handled (§14.2)? | Changes what the user sees when tmux misbehaves. | Handle them: log, print one line to stderr, exit 1. Confirm. |
| **O-6** | `PATH` handling (§0.4 step 4) has never been tested against a real `.envs`, because none exists on this machine (§16). | If wrong, `tmux` / `git` / `fzf` may not be found on some machines. | Test on the real target machine before release. |
| **O-7** | Rule 8 of `assertValidSessionName` accepts 18 exotic Unicode whitespace code points (§11.3.1). Keep them, or narrow to `^[A-Za-z0-9_\- ]+$`? | Narrowing is a user-visible change; nobody is likely to notice. | Keep the exact set for now. Revisit only if it complicates the code. |
