// prompt.go — asking the user for a session name (used by `new` and `rename`).
//
// SPEC §9, §9.1, §9.2, §9.2.1 and quirk Q8. This is the highest-risk file in the
// port: the Python tests write straight into the FIFO, so the timing contract is
// part of the behaviour.
//
// Order of operations, and none of it is optional (SPEC §9.2.1):
//
//  1. syscall.Mkfifo(fifo, 0600) inside a private 0700 directory -- FIRST
//     THING, inside 200 ms of process start, BEFORE .envs sourcing. main calls
//     prepareFifo for the `new` and `rename` actions before anything slow runs.
//     The tests only open the path for writing; if the FIFO is not there yet,
//     Python creates a plain file and the name is lost.
//  2. Record the current pane id BEFORE splitting.
//  3. tmux split-window -v -l 30% -b -P -F '#{pane_id}' sh -c <script>
//     <script> is ONE argv element. -P -F gives us the NEW pane id, which is
//     the pane we must kill later.
//  4. The redirect `> <fifo>` sits on the LAST printf only. If the whole script
//     were redirected, the pane's shell would open the write end at once, a
//     second writer would keep the read from ending, and the read could pick up
//     the pane's own empty line. With the redirect where it is, the pane opens
//     the write end only after the user presses Enter — which never happens in
//     the tests, so the test process is the only writer.
//  5. Open the FIFO for reading and block. Timeout 60 s. Do NOT shorten it: Go
//     arrives here in milliseconds and then waits ~2.0 s for the test.
//  6. Read the FIRST LINE only.
//  7. tmux kill-pane on the PROMPT pane, then select-pane back to the original.
//     split-window makes the new pane active and tmux routes keystrokes to the
//     active pane. Without the kill, the rename tests type into the prompt
//     shell instead of into fzf.
//  8. os.Remove(fifo), in a defer, only AFTER the read returns.
package main

import (
	"bufio"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"syscall"
	"time"
)

// Permissions and names of the prompt FIFO (SPEC §9.2.1, corrected 2026-08-07).
//
// The old path was the fixed, world-writable /tmp/tmux_fzf_session_name with
// mode 0666. /tmp is shared, so any local user could read the name the user
// typed, or write a name of their own and pick the new session for them.
// The FIFO now lives in a private per-user directory instead.
const (
	fifoDirMode = 0o700
	fifoMode    = 0o600
	fifoName    = "name.fifo"
)

// fifoDir is <tmp>/tmux-session-<uid>/, one private directory per user.
//
// No collision with the debounce state file: that one is
// <tmp>/tmux-session-<uid>.json, a FILE whose name carries a ".json" suffix,
// so the two names are always different strings (state.go, SPEC §7.1).
func fifoDir() string {
	return filepath.Join(os.TempDir(), "tmux-session-"+debounceID())
}

// fifoPath is the FIFO itself, <tmp>/tmux-session-<uid>/name.fifo.
// tests/helpers/workflow.py builds the very same path from os.getuid().
// It is a binding contract: do not replace the FIFO with tmux command-prompt.
var fifoPath = filepath.Join(fifoDir(), fifoName)

// promptScript is the shell text tmux runs in the split pane.
// Kept as one argv element and never re-quoted by Go.
// The redirect is on the last printf ONLY — see step 4 above.
// The path holds only letters, digits, "-", "." and "/", so it needs no
// quoting inside the script (SPEC §0.9.2).
var promptScript = `printf 'Session Name: '; read n; printf '%s\n' "$n" > ` + fifoPath

// fifoReadTimeout bounds the read that hangs forever today (SPEC §9.1, M8).
// 60 s matches a normal user prompt and is far above the ~2.0 s the tests need.
const fifoReadTimeout = 60 * time.Second

// fifoReady records that the FIFO exists. main sets it at startup for `new` and
// `rename`; promptSessionName falls back to creating it itself (the action menu
// path, where the action is only known after fzf has run).
var fifoReady bool

// fifoErr keeps the reason the FIFO could not be created. promptSessionName
// hands it to the caller, which must tell the user (Q8, decision D7).
var fifoErr error

// prepareFifo creates the FIFO and never stops the program (SPEC §9.2.1 step 1).
// It does REMEMBER the failure, though: a silent exit 0 is the Q8 bug.
func prepareFifo() {
	fifoErr = makeFifo(fifoPath)
	if fifoErr != nil {
		logEvent("prompt: could not create " + fifoPath + ": " + fifoErr.Error())
		fifoReady = false
		return
	}
	fifoReady = true
}

// ensureFifoDir makes the private directory and checks it really is ours.
//
// /tmp is shared, so anything unexpected at our path is a hard error, never
// something to work around: a symlink, a plain file or a directory belonging to
// somebody else all mean another user got there first.
func ensureFifoDir(dir string) error {
	if err := os.Mkdir(dir, fifoDirMode); err != nil && !errors.Is(err, fs.ErrExist) {
		return err
	}
	// Lstat, not Stat: a symlink at our path must fail, not be followed.
	info, err := os.Lstat(dir)
	if err != nil {
		return err
	}
	if !info.IsDir() {
		return fmt.Errorf("%s is not a directory", dir)
	}
	stat, ok := info.Sys().(*syscall.Stat_t)
	if !ok {
		return fmt.Errorf("%s: could not read the owner", dir)
	}
	if uid := os.Getuid(); int(stat.Uid) != uid {
		return fmt.Errorf("%s belongs to uid %d, not to uid %d", dir, stat.Uid, uid)
	}
	// A directory left over with wider rights is narrowed again.
	if info.Mode().Perm() != fifoDirMode {
		if err := os.Chmod(dir, fifoDirMode); err != nil {
			return err
		}
	}
	return nil
}

// makeFifo makes a fresh FIFO at path inside the private directory.
//
// mkfifo comes FIRST. On a clean run it succeeds and there is no window at all
// between a remove and the create. Only when something is already at the path
// do we remove it and try once more — that leftover is normally a REGULAR file
// from a crashed run, which would make mkfifo fail with EEXIST for ever.
// The directory is 0700 and ours, so no other user can race us there.
func makeFifo(path string) error {
	if err := ensureFifoDir(filepath.Dir(path)); err != nil {
		return err
	}
	err := syscall.Mkfifo(path, fifoMode)
	if err == nil {
		return nil
	}
	if !errors.Is(err, fs.ErrExist) {
		return err
	}
	if err := os.Remove(path); err != nil && !errors.Is(err, fs.ErrNotExist) {
		return err
	}
	return syscall.Mkfifo(path, fifoMode)
}

// promptSessionName shows the prompt pane and returns the name the user typed.
//
// There are TWO empty results and the caller must tell them apart (Q8, D7):
//
//	("", nil)  the user cancelled — stay silent and exit 0
//	("", err)  the prompt itself broke — say so, never exit 0 in silence
func promptSessionName() (string, error) {
	if !fifoReady {
		prepareFifo()
	}
	if !fifoReady {
		if fifoErr != nil {
			return "", fifoErr
		}
		return "", errors.New("the session name prompt is not available")
	}
	// Step 8: remove the FIFO only after the read returns. This defer is
	// registered first, so it runs LAST — after the pane is killed.
	defer func() {
		fifoReady = false
		_ = os.Remove(fifoPath)
	}()

	// Step 2: the pane we must go back to, recorded before the split.
	originalPane, err := tmuxCurrentPaneID()
	if err != nil {
		logEvent("prompt: tmux display-message failed: " + err.Error())
		originalPane = ""
	}

	// Step 3.
	promptPane, err := tmuxSplitPrompt(promptScript)
	if err != nil {
		// Do not give up here. The pane is how a real user answers, but the
		// tests write into the FIFO themselves, so the read can still succeed.
		logEvent("prompt: tmux split-window failed: " + err.Error())
		// execRun folds stderr into the error (tmux.go), so tmux can create
		// the pane, print its id on stdout, warn on stderr and STILL exit
		// non-zero. Throwing that id away leaves the pane alive, and it is the
		// ACTIVE pane: it then eats every keystroke meant for fzf.
		if strings.HasPrefix(promptPane, "%") {
			logEvent("prompt: keeping pane " + promptPane + " from the failed split")
		} else {
			promptPane = ""
		}
	}

	// Step 7, as a defer so the pane dies on EVERY path out of this function.
	// It runs before the caller draws anything, which is what matters.
	defer func() {
		if promptPane == "" {
			return
		}
		if err := tmuxKillPane(promptPane); err != nil {
			logEvent("prompt: tmux kill-pane failed: " + err.Error())
		}
		if originalPane != "" {
			_ = tmuxSelectPane(originalPane)
		}
	}()

	// Steps 5 and 6.
	line, readErr := readFirstLine(fifoPath, fifoReadTimeout)
	if readErr != nil {
		logEvent("prompt: no session name read: " + readErr.Error())
		return "", readErr
	}
	return strings.TrimSpace(line), nil
}

// readFirstLine opens the FIFO for reading and returns its first line.
//
// The open and the read run in a goroutine because opening a FIFO for reading
// blocks until a writer opens the other end, and that wait must be bounded.
// On timeout the goroutine stays blocked; the process exits right afterwards,
// so there is nothing to clean up.
func readFirstLine(path string, timeout time.Duration) (string, error) {
	type result struct {
		line string
		err  error
	}
	done := make(chan result, 1)

	go func() {
		f, err := os.Open(path)
		if err != nil {
			done <- result{"", err}
			return
		}
		defer func() { _ = f.Close() }()

		line, err := bufio.NewReader(f).ReadString('\n')
		// A writer that closed without a newline still gave us a usable name.
		if err != nil && line == "" {
			done <- result{"", err}
			return
		}
		done <- result{line, nil}
	}()

	select {
	case r := <-done:
		return r.line, r.err
	case <-time.After(timeout):
		return "", errors.New("timed out waiting for a session name")
	}
}
