// prompt.go — asking the user for a session name (used by `new` and `rename`).
//
// SPEC §9, §9.1, §9.2, §9.2.1 and quirk Q8. This is the highest-risk file in the
// port: the Python tests write straight into the FIFO, so the timing contract is
// part of the behaviour.
//
// Order of operations, and none of it is optional (SPEC §9.2.1):
//
//  1. os.Remove(fifo) then syscall.Mkfifo(fifo, 0666) -- FIRST THING, inside
//     200 ms of process start, BEFORE .envs sourcing. main calls prepareFifo
//     for the `new` and `rename` actions before anything slow runs. The tests
//     only open the path for writing; if the FIFO is not there yet, Python
//     creates a plain file and the name is lost.
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
	"os"
	"strings"
	"syscall"
	"time"
)

// fifoPath is fixed by the test helpers (tests/helpers/workflow.py:31).
// It is a binding contract: do not replace the FIFO with tmux command-prompt.
const fifoPath = "/tmp/tmux_fzf_session_name"

// promptScript is the shell text tmux runs in the split pane.
// Kept as one argv element and never re-quoted by Go.
// The redirect is on the last printf ONLY — see step 4 above.
const promptScript = `printf 'Session Name: '; read n; printf '%s\n' "$n" > ` + fifoPath

// fifoReadTimeout bounds the read that hangs forever today (SPEC §9.1, M8).
// 60 s matches a normal user prompt and is far above the ~2.0 s the tests need.
const fifoReadTimeout = 60 * time.Second

// fifoMode is the FIFO permission. Both sides may run under different umasks,
// so the mode is set again with Chmod after mkfifo.
const fifoMode = 0o666

// fifoReady records that the FIFO exists. main sets it at startup for `new` and
// `rename`; promptSessionName falls back to creating it itself (the action menu
// path, where the action is only known after fzf has run).
var fifoReady bool

// prepareFifo creates the FIFO and never fails loudly (SPEC §9.2.1 step 1).
func prepareFifo() {
	if err := makeFifo(fifoPath); err != nil {
		logEvent("prompt: could not create " + fifoPath + ": " + err.Error())
		fifoReady = false
		return
	}
	fifoReady = true
}

// makeFifo removes anything at path and makes a fresh FIFO there.
// The remove matters: a leftover REGULAR file from a crashed run would make
// mkfifo fail with EEXIST, and every later run would then be broken.
func makeFifo(path string) error {
	if err := os.Remove(path); err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	if err := syscall.Mkfifo(path, fifoMode); err != nil {
		return err
	}
	// mkfifo applies the umask, so 0666 usually becomes 0644. Widen it again.
	_ = os.Chmod(path, fifoMode)
	return nil
}

// promptSessionName shows the prompt pane and returns the name the user typed.
// An empty result means "cancelled" and the caller must exit 0 (SPEC §3.8, §3.12).
func promptSessionName() string {
	if !fifoReady {
		prepareFifo()
	}
	if !fifoReady {
		return ""
	}
	// Step 8: remove the FIFO only after the read returns.
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
		promptPane = ""
	}

	// Steps 5 and 6.
	line, readErr := readFirstLine(fifoPath, fifoReadTimeout)

	// Step 7. Do this before the caller draws anything: while the prompt pane
	// lives, it is the active pane and it eats every keystroke.
	if promptPane != "" {
		if err := tmuxKillPane(promptPane); err != nil {
			logEvent("prompt: tmux kill-pane failed: " + err.Error())
		}
		if originalPane != "" {
			_ = tmuxSelectPane(originalPane)
		}
	}

	if readErr != nil {
		logEvent("prompt: no session name read: " + readErr.Error())
		return ""
	}
	return strings.TrimSpace(line)
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
