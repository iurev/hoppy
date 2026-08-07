// Command session-zx is a tmux session switcher driven by fzf.
// It is the Go port of session-zx.mjs. See SPEC.md and ARCHITECTURE.md.
//
// This file owns:
//   - startup (SPEC §1): appDir, log path, .envs sourcing, env defaults
//   - argv parsing (SPEC §1.2): os.Args only, "argument present = argument given"
//   - the action router (SPEC §2), in the exact order the .mjs uses
//   - one small handler function per action (SPEC §3)
//
// IMPLEMENTED HERE: the action menu, switch, reload-sessions, the three popup
// actions, worktree-switch and capital-switch.
//
// STILL STUBBED (next implementer): the helper actions switch-from-line,
// kill-single-from-line and delayed-switch (they need the debounce half of
// state.go), plus kill-single, new, rename, kill and detach (they need
// prompt.go and the mutation flows). Every stub is marked "STUB".
package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// validActions is the list checked by assertValidAction (SPEC §2.1).
// The three helper actions are routed before this gate (SPEC §2, Q15).
var validActions = []string{
	"switch", "new", "rename", "detach", "kill", "kill-single",
	"reload-sessions", "popup-switch",
	"worktree-switch", "popup-worktree-switch",
	"capital-switch", "popup-capital-switch",
}

// helperActions are routed before assertValidAction. fzf --bind and the
// detached debounce child re-invoke this binary with them (SPEC §2, §3.4-§3.6).
var helperActions = []string{
	"reload-sessions", "kill-single-from-line", "switch-from-line", "delayed-switch",
}

// defaultFzfBin is the ensureEnvDefaults value for TMUX_FZF_BIN (SPEC §8.2).
const defaultFzfBin = "fzf"

// Package-level paths, set once in main. No app struct, no DI container
// (ARCHITECTURE §6 rule 2).
var (
	// selfPath is the absolute path of this binary, symlinks resolved. It goes
	// into the fzf --bind commands and the popup command line.
	selfPath string
	// appDir is the directory holding the binary: <appDir>/session-zx.log and
	// <appDir>/.session-frecency/ (SPEC §0.55).
	appDir string
)

// envSkipKeys are the process-local variables sourceEnv must never copy, even
// when they changed. Copying them is exactly the Q5 bug (SPEC §0.4 step 5).
var envSkipKeys = map[string]bool{
	"_": true, "SHLVL": true, "PWD": true, "OLDPWD": true, "SHELL": true,
	"HOME": true, "USER": true, "LOGNAME": true, "TMUX": true, "TMUX_PANE": true,
}

func main() {
	os.Exit(start())
}

// start is the whole program. main only turns its result into an exit code, so
// that every path here can return instead of calling os.Exit in ten places.
func start() int {
	// SPEC §1 step 2: the binary path and its directory.
	selfPath = resolveSelf()
	appDir = filepath.Dir(selfPath)

	// SPEC §1 step 3: the log file sits next to the binary.
	setLogPath(appDir)

	// SPEC §1 steps 5-6 (SESSION_SWITCH_DEBOUNCE_MS and the debounce file path)
	// belong to the debounce half of state.go. Q6 moves the read to AFTER
	// sourceEnv, so nothing is needed here.

	// SPEC §1 step 8.
	sourceEnv()
	// SPEC §1 step 9.
	ensureEnvDefaults()

	// SPEC §1 step 11.
	logEvent("script started")

	// SPEC §1 steps 12-13.
	current := currentSession()
	logEvent("current session: " + current)

	// SPEC §1 step 14 (excludeCurrent) is DELETED — decision D3.

	// SPEC §1 step 15. O-4: argument present = argument given, so a session
	// named "0" works here where the .mjs treated it as missing (§1.2, M11).
	action, arg := parseArgs()
	if action == "" {
		selected, err := actionMenu()
		if err != nil {
			return fail("", err)
		}
		action = selected
	}
	logEvent("action selected: " + action)

	// SPEC §1 step 17.
	if action == "" || action == "[cancel]" {
		logEvent("action=" + actionLabel(action) + ": cancelled")
		return 0
	}

	return route(action, arg, current)
}

// route is SPEC §2, in the exact .mjs order. The order is the contract: the
// three helper actions are handled BEFORE assertValidAction and are absent from
// validActions on purpose (Q15).
func route(action, arg, current string) int {
	// 1-3: the popup wrappers.
	switch action {
	case "popup-switch":
		return actionPopup("SESSIONS", "switch")
	case "popup-worktree-switch":
		return actionPopup("WORKTREE SESSIONS", "worktree-switch")
	case "popup-capital-switch":
		return actionPopup("CAPITAL SESSIONS", "capital-switch")
	// 4: fzf's reload target.
	case "reload-sessions":
		return actionReloadSessions(current)
	// 5-7: the helper actions. They are NOT in validActions and they always
	// exit 0 (SPEC §3.4-§3.6).
	case "kill-single-from-line":
		return actionKillSingleFromLine(arg)
	case "delayed-switch":
		return actionDelayedSwitch(arg)
	case "switch-from-line":
		return actionSwitchFromLine(arg)
	}

	// The gate. Everything below is a validated action (SPEC §2, line 145).
	if err := assertValidAction(action); err != nil {
		// err.Error() already begins with "Invalid action: ", which is exactly
		// the shape of log message 18. Do not prefix it again.
		logEvent(err.Error())
		fmt.Fprintln(os.Stderr, "Error: "+err.Error())
		return 1
	}

	// 8: kill-single runs BEFORE the unconditional action log (.mjs 154 vs 258).
	if action == "kill-single" {
		return actionKillSingle(arg)
	}

	// SPEC §13.2 message 4. Unconditional for every action that reaches here
	// (.mjs line 258, M6).
	logEvent("action=" + action)

	switch action {
	case "new":
		return actionNew()
	case "worktree-switch":
		return actionWorktreeSwitch(current)
	case "capital-switch":
		return actionCapitalSwitch(current)
	case "switch":
		return actionSwitch(current)
	case "rename":
		return actionRename()
	case "kill":
		return actionKill()
	case "detach":
		return actionDetach()
	}

	// Unreachable: the gate above accepts nothing else (.mjs 662-663).
	logEvent("script complete, exiting normally")
	return 0
}

// ---------------------------------------------------------------------------
// Startup helpers (SPEC §1, §8)
// ---------------------------------------------------------------------------

// resolveSelf returns the absolute path of this binary with symlinks resolved
// (SPEC §0.1: <appDir> is "the directory that holds the Go binary").
// Every fallback still yields an absolute path, because <appDir> also decides
// where the log and the frecency directory live.
func resolveSelf() string {
	exe, err := os.Executable()
	if err != nil {
		if abs, absErr := filepath.Abs(os.Args[0]); absErr == nil {
			return abs
		}
		return os.Args[0]
	}
	if resolved, err := filepath.EvalSymlinks(exe); err == nil {
		return resolved
	}
	return exe
}

// parseArgs reads the action and its one optional argument (SPEC §1.2).
//
// O-4: "argument present = argument given". The .mjs used JavaScript
// truthiness, so a literal `0` looked missing (M11). Go has no falsy number and
// faking one would break a session legitimately named "0".
func parseArgs() (action, arg string) {
	if len(os.Args) > 1 {
		action = os.Args[1]
	}
	if len(os.Args) > 2 {
		arg = os.Args[2]
	}
	return action, arg
}

// currentSession asks tmux which session the client is in (SPEC §1 step 12).
//
// Two deliberate differences from the .mjs, both required:
//
//   - the name is validated but a failure only WARNS (SPEC §1.1, M5). tmux
//     allows names assertValidSessionName rejects, and the name came from tmux.
//   - a tmux failure is NOT fatal. The .mjs crashes with no tmux server
//     (SPEC §15 row 1), but the action menu and the popup wrappers need no
//     server at all, and tests/test_script_executes.py runs the binary with the
//     server killed. Treat it as "no current session" and carry on (O-5).
func currentSession() string {
	name, err := tmuxCurrentSession()
	if err != nil {
		logEvent("startup: tmux display-message failed: " + err.Error())
		return ""
	}
	if name == "" {
		return ""
	}
	if err := assertValidSessionName(name); err != nil {
		logEvent("Warning: Current session name is invalid: " + err.Error())
	}
	return name
}

// sourceEnv applies <appDir>/.envs, or the tmux-fzf plugin copy (SPEC §8.1).
//
// Q5 fix (SPEC §0.4): only keys that are NEW or CHANGED between a plain login
// shell and one that sourced the file are applied. PATH is the one exception and
// is always applied — it is what puts tmux, git and fzf on the path.
//
// If no candidate file exists this does nothing at all, which is today's
// behaviour and, per SPEC §16, today's reality on this machine.
func sourceEnv() {
	path := findEnvsFile()
	if path == "" {
		return
	}

	before, err := run("bash", "-lc", "env")
	if err != nil {
		logEvent("sourceEnv: could not read the login environment: " + err.Error())
		return
	}
	// The escape of `"` in the path is correct in the .mjs; keep it.
	quoted := strings.ReplaceAll(path, `"`, `\"`)
	after, err := run("bash", "-lc", `source "`+quoted+`" >/dev/null 2>&1 && env`)
	if err != nil {
		logEvent("sourceEnv: could not source " + path + ": " + err.Error())
		return
	}

	baseline := parseEnvOutput(before)
	sourced := parseEnvOutput(after)

	applied := 0
	for key, value := range sourced {
		if envSkipKeys[key] {
			continue
		}
		// Step 4: PATH is applied even when it did not change.
		if key != "PATH" {
			if old, ok := baseline[key]; ok && old == value {
				continue
			}
		}
		if os.Setenv(key, value) == nil {
			applied++
		}
	}
	logEvent(fmt.Sprintf("sourceEnv: applied %d variables from %s", applied, path))
}

// findEnvsFile returns the first existing candidate, or "" (SPEC §8.1).
func findEnvsFile() string {
	candidates := []string{filepath.Join(appDir, ".envs")}
	if home, err := os.UserHomeDir(); err == nil && home != "" {
		candidates = append(candidates,
			filepath.Join(home, ".tmux", "plugins", "tmux-fzf", "scripts", ".envs"))
	}
	for _, c := range candidates {
		if info, err := os.Stat(c); err == nil && !info.IsDir() {
			return c
		}
	}
	return ""
}

// parseEnvOutput splits `env` output at the FIRST "=" on each line and skips
// lines with no "=" (SPEC §8.1 step 3, §0.4 step 6).
// Multi-line values stay mangled. That is bug-compatible and accepted.
func parseEnvOutput(out string) map[string]string {
	env := map[string]string{}
	for _, line := range strings.Split(out, "\n") {
		if line == "" {
			continue
		}
		key, value, found := strings.Cut(line, "=")
		if !found || key == "" {
			continue
		}
		env[key] = value
	}
	return env
}

// ensureEnvDefaults sets TMUX_FZF_BIN when it is unset or empty (SPEC §8.2).
// TMUX_FZF_OPTIONS and FZF_DEFAULT_OPTS need no default: os.Getenv already gives
// "" and an empty string shell-splits into zero words.
// The TMUX_FZF_PREVIEW_OPTIONS / KAOMOJI_PREVIEW_TEXT rows are deleted (D5).
func ensureEnvDefaults() {
	if os.Getenv("TMUX_FZF_BIN") == "" {
		_ = os.Setenv("TMUX_FZF_BIN", defaultFzfBin)
	}
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

// actionMenu shows the six-item action list (SPEC §3.1).
// No number prefixes: it calls runFzf directly, so "[cancel]" is a normal item.
func actionMenu() (string, error) {
	items := []string{"switch", "new", "rename", "detach", "kill", "[cancel]"}
	selection, err := runFzf(items, headerAction, nil)
	if err != nil {
		return "", err
	}
	lines := parseLines(selection)
	if len(lines) == 0 {
		return "", nil
	}
	return lines[0], nil
}

// actionPopup re-runs this binary inside a tmux popup (SPEC §3.2).
// Geometry and titles come from tmux.go; the title carries no quotes.
func actionPopup(title, inner string) int {
	if err := tmuxDisplayPopup(title, selfPath, inner); err != nil {
		logEvent("popup-" + inner + ": tmux display-popup failed: " + err.Error())
		fmt.Fprintln(os.Stderr, "Error: tmux display-popup failed: "+err.Error())
		return 1
	}
	return 0
}

// actionReloadSessions prints the session rows for fzf's reload() (SPEC §3.3).
//
// Q7 FIX: the rows are IDENTICAL to the initial switch list. The current session
// is pinned to the top and "[cancel]" is appended. The .mjs passed a null
// current session and printed no cancel row, so the list silently changed shape
// after the first DEL press. SPEC §3.3, §4.2 and §15 still carry the old .mjs
// sentences, each annotated with "(Q7 FIX)".
func actionReloadSessions(current string) int {
	items, code := buildSelectorRows(current, "reload-sessions")
	if code != 0 {
		return code
	}
	fmt.Println(strings.Join(items, "\n"))
	return 0
}

// actionSwitch is SPEC §3.11.
func actionSwitch(current string) int {
	if code := checkSelfPath(); code != 0 {
		return code
	}

	items, code := buildSelectorRows(current, "switch")
	if code != 0 {
		return code
	}

	selection, err := runFzf(items, headerSwitch, switchBindings(selfPath))
	if err != nil {
		return fail("switch", err)
	}
	return switchToSelection("switch", selection, current, true)
}

// actionWorktreeSwitch is SPEC §3.9.
func actionWorktreeSwitch(current string) int {
	currentPath, err := tmuxPaneCurrentPath()
	if err != nil {
		logEvent("worktree-switch: tmux display-message failed: " + err.Error())
		return fail("worktree-switch", err)
	}

	worktrees := gitWorktrees(currentPath)
	if len(worktrees) == 0 {
		_ = tmuxDisplayMessage(msgNotInGitRepo)
		logEvent("action=worktree-switch: cancelled")
		return 0
	}

	panePaths, err := tmuxListPanePaths()
	if err != nil {
		logEvent("worktree-switch: tmux list-panes failed: " + err.Error())
		return fail("worktree-switch", err)
	}

	all, code := loadSessions(current, "worktree-switch")
	if code != 0 {
		return code
	}

	filtered := filterByWorktrees(all, worktrees, panePaths)
	if len(filtered) == 0 {
		_ = tmuxDisplayMessage(msgNoWorktreeSess)
		logEvent("action=worktree-switch: cancelled")
		return 0
	}

	header := fmt.Sprintf("Worktree sessions (%d/%d). Ctrl+N/P to preview.",
		len(filtered), len(all))
	selection, err := runFzf(selectorItems(filtered, current, false),
		header, previewBindings(selfPath))
	if err != nil {
		return fail("worktree-switch", err)
	}
	// §3.9 step 9: an invalid target is logged only, never printed to stderr.
	return switchToSelection("worktree-switch", selection, current, false)
}

// actionCapitalSwitch is SPEC §3.10.
func actionCapitalSwitch(current string) int {
	all, code := loadSessions(current, "capital-switch")
	if code != 0 {
		return code
	}

	filtered := filterCapital(all)
	if len(filtered) == 0 {
		_ = tmuxDisplayMessage(msgNoCapitalSess)
		logEvent("action=capital-switch: cancelled")
		return 0
	}

	header := fmt.Sprintf("CAPITAL sessions (%d/%d). Ctrl+N/P to preview.",
		len(filtered), len(all))
	selection, err := runFzf(selectorItems(filtered, current, false),
		header, previewBindings(selfPath))
	if err != nil {
		return fail("capital-switch", err)
	}
	return switchToSelection("capital-switch", selection, current, false)
}

// ---------------------------------------------------------------------------
// Shared action tails
// ---------------------------------------------------------------------------

// loadSessions reads and orders the session list, or reports the failure.
func loadSessions(current, action string) ([]string, int) {
	sessions, err := getSessionsList(current, loadFrecency(appDir), time.Now())
	if err != nil {
		logEvent(action + ": tmux list-sessions failed: " + err.Error())
		return nil, fail(action, err)
	}
	return sessions, 0
}

// buildSelectorRows is the list + pin + numbers + "[cancel]" pipeline shared by
// `switch` and `reload-sessions`. The two MUST agree row for row (Q7 FIX), and
// one function is how they are kept in step.
func buildSelectorRows(current, action string) ([]string, int) {
	sessions, code := loadSessions(current, action)
	if code != 0 {
		return nil, code
	}
	return selectorItems(sessions, current, false), 0
}

// switchToSelection is the common tail of switch, worktree-switch and
// capital-switch (SPEC §3.9-§3.11): parse, validate, switch, record frecency.
//
// printErr follows the .mjs: `switch` prints "Error: <msg>" for an invalid
// target, the two filtered switches only log it (§3.9 step 9).
func switchToSelection(action, selection, current string, printErr bool) int {
	targets := parseTargets(selection, current)
	if len(targets) == 0 {
		logEvent("action=" + action + ": cancelled")
		return 0
	}

	// Only targets[0] is used, even when fzf returned several rows.
	target := targets[0]
	if err := assertValidSessionName(target); err != nil {
		logEvent("Invalid target session: " + err.Error())
		if printErr {
			fmt.Fprintln(os.Stderr, "Error: "+err.Error())
		}
		return 1
	}

	if err := tmuxSwitchClient(target); err != nil {
		logEvent(action + ": tmux switch-client failed: " + err.Error())
		fmt.Fprintln(os.Stderr, "Error: "+err.Error())
		return 1
	}

	// SPEC §5.3: frecency is recorded only after a SUCCESSFUL switch-client, and
	// only from these three actions.
	recordSelection(appDir, target, time.Now())
	logEvent("action=" + action + ": switched to " + target)
	return 0
}

// checkSelfPath keeps the two `switch` preconditions that survive Q17
// (SPEC §3.11). The metacharacter blacklist is deleted: shellquote.Join plus
// `--with-shell sh` handles a path with a space, a quote or brackets.
func checkSelfPath() int {
	if selfPath == "" {
		return fail("switch", errors.New("Could not determine script path"))
	}
	if len(selfPath) > 4096 {
		return fail("switch", errors.New("Script path is too long"))
	}
	return 0
}

// ---------------------------------------------------------------------------
// STUBS — owned by the next implementer
// ---------------------------------------------------------------------------
//
// The fzf bindings for Ctrl+N, Ctrl+P and DEL are already wired (see
// switchBindings in fzf.go), so these three are called for real today. They MUST
// exit 0 and stay silent: fzf runs them inside execute()/execute-silent() while
// the list is on screen, and a stray line or a non-zero code shows up in the UI.

// actionKillSingleFromLine is SPEC §3.4. STUB.
// TODO(next): extractSessionName(line), then tmux kill-session -t <name>.
// No name validation and no [cancel] guard — that is the .mjs behaviour.
func actionKillSingleFromLine(line string) int {
	logEvent("action=kill-single-from-line: STUB, not implemented yet")
	_ = line
	return 0
}

// actionSwitchFromLine is SPEC §3.5, the Ctrl+N / Ctrl+P preview. STUB.
// TODO(next): extractSessionName, then scheduleSessionSwitch (SPEC §7.2).
func actionSwitchFromLine(line string) int {
	logEvent("action=switch-from-line: STUB, not implemented yet")
	_ = line
	return 0
}

// actionDelayedSwitch is SPEC §3.6, the detached debounce child. STUB.
// TODO(next): handleDelayedSwitch(token) (SPEC §7.3).
func actionDelayedSwitch(token string) int {
	logEvent("action=delayed-switch: STUB, not implemented yet")
	_ = token
	return 0
}

// actionKillSingle is SPEC §3.7 (the interactive Y/n confirm). STUB.
func actionKillSingle(name string) int {
	_ = name
	return notImplemented("kill-single")
}

// actionNew is SPEC §3.8. STUB — needs prompt.go (the FIFO, SPEC §9.2.1).
func actionNew() int { return notImplemented("new") }

// actionRename is SPEC §3.12. STUB — needs prompt.go.
func actionRename() int { return notImplemented("rename") }

// actionKill is SPEC §3.13. STUB.
func actionKill() int { return notImplemented("kill") }

// actionDetach is SPEC §3.14. STUB.
func actionDetach() int { return notImplemented("detach") }

// notImplemented fails loudly. A silent exit 0 here would look like a working
// action that quietly does nothing, which is much harder to notice.
func notImplemented(action string) int {
	logEvent("action=" + action + ": not implemented yet")
	fmt.Fprintln(os.Stderr, "Error: action "+action+" is not implemented yet")
	return 1
}

// ---------------------------------------------------------------------------
// Small helpers
// ---------------------------------------------------------------------------

// fail logs and prints one line to stderr, never a Go stack trace (O-2).
func fail(action string, err error) int {
	if action != "" {
		logEvent(action + ": " + err.Error())
	} else {
		logEvent(err.Error())
	}
	fmt.Fprintln(os.Stderr, "Error: "+err.Error())
	return 1
}

// actionLabel keeps the cancel log line readable when no action was chosen.
func actionLabel(action string) string {
	if action == "" {
		return "(none)"
	}
	return action
}
