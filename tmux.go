// tmux.go — every external process call lives here. It is the ONLY file that
// runs tmux or git, and it owns the `runner` seam that tests swap for a fake.
//
// READ SPEC §0.9 BEFORE ADDING A CALL. Every quote in SPEC is a SHELL quote:
// zx ran each template through `bash -c` and bash removed them before the
// program saw them. So the format below is the argv element
// `#S @ #{session_windows} windows` with NO surrounding quotes. Keeping the
// quotes throws no error and still looks almost right — the bug only shows up
// later as wrong frecency order (SPEC §0.9.1 table, §0.9.2).
package main

import (
	"bytes"
	"errors"
	"fmt"
	"os/exec"
	"slices"
	"strings"
)

// runner runs one external command and returns its stdout. This is the
// program's only process seam. Production uses execRun; tests use a fake.
type runner func(argv ...string) (stdout string, err error)

var run runner = execRun

// -F format strings (SPEC §0.9.1 rows 1, 2). One argv element each, no quotes.
// The pane separator is a real TAB.
const (
	sessionListFormat = "#S @ #{session_windows} windows"
	panePathFormat    = "#{session_name}\t#{pane_current_path}"
	paneIDFormat      = "#{pane_id}"
	// attachedFormat is the Q3 fix (SPEC §6.4, §3.14.1). The old code parsed
	// the default `tmux list-sessions` output, which has no " @ ", so every
	// name came back as a whole line and the detach filter was always empty.
	attachedFormat = "#{session_name}\t#{session_attached}"
)

// Popup geometry, identical for all three popup actions (SPEC §3.2).
const (
	popupWidth  = "60%"
	popupHeight = "90%"
	popupBorder = "rounded"
)

// The three fixed user messages (SPEC §0.9.1 rows 6-8). No quotes: bash
// stripped those long before tmux saw them.
const (
	msgNotInGitRepo   = "Not in a git repository"
	msgNoWorktreeSess = "No sessions found for this project's worktrees"
	msgNoCapitalSess  = "No CAPITAL sessions found"
)

// execRun is the real runner. It captures stdout and folds stderr into the
// error, so callers can log SPEC §13.2 message 16 with a useful reason.
//
// Both error paths wrap with %w so the *exec.ExitError survives: callers read
// the real exit status with errors.As (SPEC §12). %s would drop the status and
// every non-zero exit would then look the same.
func execRun(argv ...string) (string, error) {
	if len(argv) == 0 {
		return "", errors.New("empty command")
	}
	cmd := exec.Command(argv[0], argv[1:]...)
	var out, errOut bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &errOut

	err := cmd.Run()
	if err != nil {
		if msg := strings.TrimSpace(errOut.String()); msg != "" {
			return out.String(), fmt.Errorf("%s: %s: %w", argv[0], msg, err)
		}
		return out.String(), fmt.Errorf("%s: %w", argv[0], err)
	}
	return out.String(), nil
}

// tmuxCurrentSession returns the session the client is in (SPEC §0.9.1 row 3).
// Outside tmux this fails; the caller treats that as "no current session"
// and must not stop (SPEC §1.1).
func tmuxCurrentSession() (string, error) {
	out, err := run("tmux", "display-message", "-p", "#S")
	return strings.TrimSpace(out), err
}

// tmuxPaneCurrentPath returns the working directory of the active pane
// (SPEC §0.9.1 row 4). Used by worktree-switch.
func tmuxPaneCurrentPath() (string, error) {
	out, err := run("tmux", "display-message", "-p", "#{pane_current_path}")
	return strings.TrimSpace(out), err
}

// tmuxCurrentPaneID returns the active pane id, e.g. "%3".
// promptSessionName records it BEFORE the split so it can restore focus
// afterwards (SPEC §9.2.1 step 2).
func tmuxCurrentPaneID() (string, error) {
	out, err := run("tmux", "display-message", "-p", paneIDFormat)
	return strings.TrimSpace(out), err
}

// tmuxListSessions returns one row per session: "name @ 3 windows"
// (SPEC §0.9.1 row 1, §4.1 step 3).
func tmuxListSessions() ([]string, error) {
	out, err := run("tmux", "list-sessions", "-F", sessionListFormat)
	if err != nil {
		return nil, err
	}
	return parseLines(out), nil
}

// tmuxListPanePaths maps every session name to its pane working directories
// (SPEC §6.2). Lines with no TAB are skipped.
func tmuxListPanePaths() (map[string][]string, error) {
	out, err := run("tmux", "list-panes", "-a", "-F", panePathFormat)
	if err != nil {
		return nil, err
	}
	paths := map[string][]string{}
	for _, line := range parseLines(out) {
		name, path, found := strings.Cut(line, "\t")
		if !found {
			continue
		}
		if !slices.Contains(paths[name], path) {
			paths[name] = append(paths[name], path)
		}
	}
	return paths, nil
}

// tmuxAttachedSessionNames returns the names of the sessions a client is
// attached to (Q3 fix, SPEC §6.4, §3.14.1).
func tmuxAttachedSessionNames() (map[string]bool, error) {
	out, err := run("tmux", "list-sessions", "-F", attachedFormat)
	if err != nil {
		return nil, err
	}
	attached := map[string]bool{}
	for _, line := range parseLines(out) {
		name, flag, found := strings.Cut(line, "\t")
		if !found || name == "" {
			continue
		}
		// An empty flag is not "attached". tmux prints 0 or 1 here, but an
		// unexpected/blank field must never widen the detach filter.
		if f := strings.TrimSpace(flag); f != "" && f != "0" {
			attached[name] = true
		}
	}
	return attached, nil
}

// tmuxHasSession reports whether the session exists. tmux exits non-zero when
// it does not, and that is not an error worth reporting (SPEC §14).
func tmuxHasSession(name string) bool {
	_, err := run("tmux", "has-session", "-t", name)
	return err == nil
}

// ---------------------------------------------------------------------------
// Writes. Every session name is ONE argv element, spaces and all (SPEC §0.9).
// ---------------------------------------------------------------------------

func tmuxSwitchClient(name string) error {
	_, err := run("tmux", "switch-client", "-t", name)
	return err
}

func tmuxKillSession(name string) error {
	_, err := run("tmux", "kill-session", "-t", name)
	return err
}

func tmuxNewSessionDetached(name string) error {
	_, err := run("tmux", "new-session", "-d", "-s", name)
	return err
}

func tmuxRenameSession(oldName, newName string) error {
	_, err := run("tmux", "rename-session", "-t", oldName, newName)
	return err
}

// tmuxDetachClient detaches every client of the session; the session lives on.
func tmuxDetachClient(name string) error {
	_, err := run("tmux", "detach", "-s", name)
	return err
}

// tmuxDisplayMessage shows one status message (SPEC §0.9.1 rows 5-8).
func tmuxDisplayMessage(msg string) error {
	_, err := run("tmux", "display-message", msg)
	return err
}

// tmuxSessionMissingMessage builds SPEC §0.9.1 row 5.
func tmuxSessionMissingMessage(name string) string {
	return "Session " + name + " does not exist"
}

// tmuxDisplayPopup opens the fzf selector in a popup (SPEC §0.9.1 row 9, §3.2).
// -E closes the popup when the command exits. The title carries NO quotes.
func tmuxDisplayPopup(title, scriptPath, action string) error {
	_, err := run("tmux", "display-popup", "-E",
		"-w", popupWidth, "-h", popupHeight,
		"-x", "R", "-y", "C",
		"-T", title, "-b", popupBorder,
		scriptPath, action)
	return err
}

// tmuxSplitPrompt opens the session-name prompt pane (SPEC §9.2.1 step 3) and
// returns the id of the NEW pane. `script` is ONE argv element, never requoted.
//
// `-P -F #{pane_id}` is what makes step 7 safe: the pane we must KILL is this
// new one and there is no other way to learn its id.
//
// Verified against tmux 3.5a: with more than one trailing argument tmux execs
// the argv directly, so `sh -c <script>` really runs the script as one word.
func tmuxSplitPrompt(script string) (string, error) {
	out, err := run("tmux", "split-window", "-v", "-l", "30%", "-b",
		"-P", "-F", paneIDFormat, "sh", "-c", script)
	return strings.TrimSpace(out), err
}

// tmuxKillPane closes the prompt pane (SPEC §9.2.1 step 7). Skipping this
// leaves that pane ACTIVE and it eats the keystrokes meant for fzf.
func tmuxKillPane(paneID string) error {
	_, err := run("tmux", "kill-pane", "-t", paneID)
	return err
}

// tmuxSelectPane puts focus back on the pane recorded in §9.2.1 step 2.
// Killing the prompt pane usually does this by itself, but not when the window
// held other panes, so make it explicit.
func tmuxSelectPane(paneID string) error {
	_, err := run("tmux", "select-pane", "-t", paneID)
	return err
}

// gitWorktrees lists the worktree paths of the repository at dir (SPEC §6.1).
// Any failure — not a git repo, git missing — is logged and gives an empty
// list. It never stops the program.
func gitWorktrees(dir string) []string {
	out, err := run("git", "-C", dir, "worktree", "list", "--porcelain")
	if err != nil {
		logEvent(fmt.Sprintf("gitWorktrees: git worktree list failed: %v", err))
		return []string{}
	}
	paths := []string{}
	for _, line := range strings.Split(out, "\n") {
		// "worktree " is 9 characters. The rest is taken as is, no trim.
		if strings.HasPrefix(line, "worktree ") {
			paths = append(paths, line[9:])
		}
	}
	return paths
}
