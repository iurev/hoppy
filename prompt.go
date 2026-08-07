// prompt.go — asking the user for a session name (used by `new` and `rename`).
//
// The ordered 8-step contract lives in SPEC §9.2.1; follow it exactly. This is
// the highest-risk file in the port, because the Python tests write straight
// into the FIFO, so the timing is part of the behaviour. The two traps that
// cost the most to rediscover are documented at promptScript (where the
// redirect goes) and at the kill-pane defer (why focus must be restored).
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
// The old path was the fixed, world-writable /tmp/tmux_fzf_session_name (0666),
// so any local user could read the typed name or pick the session instead.
const (
	fifoDirMode = 0o700
	fifoMode    = 0o600
	fifoName    = "name.fifo"
)

// fifoDir is <tmp>/tmux-session-<uid>/, one private directory per user. It does
// NOT collide with the debounce state, which is the FILE
// <tmp>/tmux-session-<uid>.json — the ".json" suffix keeps the names apart.
func fifoDir() string {
	return filepath.Join(os.TempDir(), "tmux-session-"+debounceID())
}

// fifoPath is <tmp>/tmux-session-<uid>/name.fifo. tests/helpers/workflow.py
// builds the very same path from os.getuid(). It is a binding contract: do not
// replace the FIFO with tmux command-prompt.
var fifoPath = filepath.Join(fifoDir(), fifoName)

// promptScript is the shell text tmux runs in the split pane, as ONE argv
// element that Go never re-quotes.
//
// The redirect `> <fifo>` sits on the LAST printf ONLY (SPEC §9.2.1 step 4).
// Redirecting the whole script would make the pane's shell open the write end
// at once; that second writer keeps the read from ending, and the read can then
// pick up the pane's own empty line. Where it is now, the pane opens the write
// end only after the user presses Enter.
//
// The path holds only letters, digits, "-", "." and "/", so it needs no
// quoting inside the script (SPEC §0.9.2).
var promptScript = `printf 'Session Name: '; read n; printf '%s\n' "$n" > ` + fifoPath

// fifoReadTimeout bounds the read that hangs forever today (SPEC §9.1, M8).
// 60 s matches a normal user prompt and is far above the ~2.0 s the tests need.
const fifoReadTimeout = 60 * time.Second

// fifoReady records that the FIFO exists; fifoErr keeps the reason it does not.
// main sets them at startup for `new` and `rename`; promptSessionName falls back
// to creating the FIFO itself (the action-menu path, where the action is only
// known after fzf has run) and reports fifoErr to the user (Q8, decision D7).
var (
	fifoReady bool
	fifoErr   error
)

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
// /tmp is shared, so anything unexpected at our path is a hard error, never
// something to work around: another user got there first.
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
// mkfifo comes FIRST, so a clean run leaves no window between a remove and a
// create. Only when something is already at the path do we remove and retry —
// that leftover is normally a REGULAR file from a crashed run, which would make
// mkfifo fail with EEXIST for ever.
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
	// Step 8: remove the FIFO only AFTER the read returns. This defer is
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
		// execRun folds stderr into the error, so tmux can create the pane,
		// print its id on stdout, warn on stderr and STILL exit non-zero.
		// Throwing that id away would leave the pane alive and ACTIVE.
		if strings.HasPrefix(promptPane, "%") {
			logEvent("prompt: keeping pane " + promptPane + " from the failed split")
		} else {
			promptPane = ""
		}
	}

	// Step 7, as a defer so the pane dies on EVERY path out of this function.
	// split-window makes the new pane ACTIVE and tmux routes keystrokes to the
	// active pane, so without this kill the rename tests type into the prompt
	// shell instead of into fzf. Focus then goes back to the original pane.
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
// On timeout the goroutine stays blocked; the process exits right after, so
// there is nothing to clean up.
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
