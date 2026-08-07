// prompt.go — asking the user for a session name (used by `new` and `rename`).
//
// SPEC §9, §9.1, §9.2 and quirk Q8. This is the highest-risk file in the port:
// the Python tests write straight into the FIFO, so the timing contract is hard.
//
// Order of operations, and none of it is optional:
//
//  1. os.Remove(fifo) then syscall.Mkfifo(fifo, 0666) -- FIRST THING, inside 200 ms.
//     The tests only open the path for writing; if the FIFO is not there yet,
//     Python creates a plain file and the name is lost.
//  2. Record the current pane id BEFORE splitting:
//     tmux display-message -p '#{pane_id}'
//  3. tmux split-window -v -l 30% -b sh -c <script>
//     <script> is ONE argv element. The redirect sits on the LAST printf only:
//     printf 'Session Name: '; read n; printf '%s\n' "$n" > <fifo>
//     If the whole script is redirected, the pane holds the write end open and
//     the read never returns.
//  4. Open the FIFO for reading and block. Timeout 60 s (do NOT shorten below
//     ~5 s: Go arrives here in milliseconds and waits ~2.0 s for the test).
//  5. Read the FIRST LINE only.
//  6. tmux kill-pane -t <paneID> -- MANDATORY. split-window makes the new pane
//     active, and tmux routes the test's keystrokes to the active pane. Without
//     this the rename tests type into the prompt shell, not into fzf.
//  7. os.Remove(fifo), in a defer, only AFTER the read returns.
//
// Planned functions:
//
//	promptSessionName() (string, error)
//	makeFifo(path string) error
//	readFirstLine(path string, timeout time.Duration) (string, error)
//
// NOT IMPLEMENTED YET.
package main

// fifoPath is fixed by the test helpers (tests/helpers/workflow.py:31).
// It is a binding contract: do not replace the FIFO with tmux command-prompt.
const fifoPath = "/tmp/tmux_fzf_session_name"

// promptScript is the shell text tmux runs in the split pane.
// Kept as one argv element and never re-quoted by Go.
const promptScript = `printf 'Session Name: '; read n; printf '%s\n' "$n" > ` + fifoPath
