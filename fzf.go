// fzf.go — building the fzf argv and running it (SPEC §10, §12).
//
// No shell. No heredoc. No eval. Items go to fzf's stdin, the selection comes
// back on stdout (SPEC §0.5, Q16).
//
// argv shape (SPEC §10.2.1):
//
//	<words of TMUX_FZF_BIN> <words of TMUX_FZF_OPTIONS>
//	--no-sort --delimiter " @ " --with-nth=1.. --nth=1
//	--with-shell sh
//	[--header <text>] [--bind <binding> ...]
//
// Every quote in SPEC §10.2 is a SHELL quote. There are none here: `--delimiter`
// and its value are two argv elements and the value is the three characters
// space, "@", space (SPEC §0.9.2).
//
// FZF_DEFAULT_OPTS is left untouched in the child env; fzf reads it itself and
// our argv wins on conflict.
package main

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strings"
	"unicode"
)

// Header texts. Keep them byte-identical: tests capture the pane and grep them
// (SPEC §10.4, test-contract §4.2).
//
// "Ctrl+N/P to preview." stays. Decision D5 drops the kaomoji PANE, not the
// Ctrl+N/P session preview (SPEC §0.2).
const (
	headerAction  = "Select an action."
	headerSwitch  = "Select target session. Press 1-9 for quick switch. DEL to kill. Ctrl+N/P to preview."
	headerTarget  = "Select target session."
	headerTargets = "Select target session(s). Press TAB to mark multiple items."
)

// fzfMinVersion is the documented floor. 0.51.0 is the first release with
// --with-shell, which is what makes our POSIX quoting of --bind provably right.
const fzfMinVersion = "0.51.0"

// fzf's own exit codes (src/constants.go), read directly now that no bash sits
// in between (SPEC §12).
const (
	fzfExitOk        = 0
	fzfExitNoMatch   = 1
	fzfExitInterrupt = 130
)

// ---------------------------------------------------------------------------
// The SECOND seam (design decision, approved)
// ---------------------------------------------------------------------------
//
// tmux.go's `runner` — func(argv ...string) (string, error) — is the seam for
// tmux and git, and it stays exactly as it is. It cannot carry fzf.
//
// fzf needs four things that `runner` has no room for:
//
//  1. items written to the child's STDIN
//  2. the selection read from the child's STDOUT
//  3. the child's STDERR, kept separate, for log message 17
//  4. the EXIT CODE as a value, because 0, 1 and 130 are all normal and only
//     other codes are errors (SPEC §12)
//
// Folding those into `runner` would mean encoding the code into an error string
// and parsing it back. So there is one more seam, and only one more.
//
// THE ABSTRACTION BUDGET IS NOW SPENT: two function types, zero interfaces. Do
// not add a third. See ARCHITECTURE.md §2.1 and §6 rule 3.
type fzfRunner func(argv []string, stdin string) (stdout, stderr string, code int, err error)

// runFzfCmd is the fzf process seam. Tests replace it; production uses execFzf.
var runFzfCmd fzfRunner = execFzf

// execFzf runs fzf for real.
//
// stdout and stderr are captured. fzf draws its UI straight on /dev/tty, so
// capturing them does not hide the interface — and NOT capturing stdout would
// dump the selected row into the user's terminal.
//
// The returned error is non-nil only for a genuine failure to run (binary not
// found, permission denied). A non-zero exit is reported through `code`.
func execFzf(argv []string, stdin string) (string, string, int, error) {
	if len(argv) == 0 {
		return "", "", -1, errors.New("TMUX_FZF_RUN command is empty.")
	}
	cmd := exec.Command(argv[0], argv[1:]...)
	cmd.Stdin = strings.NewReader(stdin)
	var out, errOut bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &errOut

	err := cmd.Run()
	if err != nil {
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			// A normal non-zero exit. The code is the answer, not the error.
			return out.String(), errOut.String(), exitErr.ExitCode(), nil
		}
		return out.String(), errOut.String(), -1, err
	}
	return out.String(), errOut.String(), fzfExitOk, nil
}

// ---------------------------------------------------------------------------
// argv
// ---------------------------------------------------------------------------

// buildFzfArgv builds the whole fzf command line (SPEC §10.2.1).
//
// TMUX_FZF_BIN and TMUX_FZF_OPTIONS are raw SHELL strings and are split with the
// POSIX splitter (SPEC §0.5, D9). `TMUX_FZF_BIN="fzf-tmux -p 80%"` must work.
func buildFzfArgv(header string, bindings []string) ([]string, error) {
	bin := os.Getenv("TMUX_FZF_BIN")
	if bin == "" {
		bin = defaultFzfBin
	}
	// The two validations of SPEC §10.3 that survive the port.
	if err := assertNonEmptyString(bin, "TMUX_FZF_BIN"); err != nil {
		return nil, err
	}
	if err := assertMaxLength(bin, "TMUX_FZF_BIN", 1000); err != nil {
		return nil, err
	}

	opts := os.Getenv("TMUX_FZF_OPTIONS")
	if err := assertValidFzfOptions(opts, "TMUX_FZF_OPTIONS"); err != nil {
		return nil, err
	}

	binWords, err := splitShellWords(bin)
	if err != nil {
		return nil, fmt.Errorf("TMUX_FZF_BIN is not valid shell text: %w", err)
	}
	optWords, err := splitShellWords(opts)
	if err != nil {
		return nil, fmt.Errorf("TMUX_FZF_OPTIONS is not valid shell text: %w", err)
	}

	argv := make([]string, 0, len(binWords)+len(optWords)+16)
	argv = append(argv, binWords...)
	argv = append(argv, optWords...)
	if len(argv) == 0 {
		// The message is kept from the .mjs on purpose (SPEC §10.2.1).
		return nil, errors.New("TMUX_FZF_RUN command is empty.")
	}

	// Our own options. No quotes anywhere: these are argv elements, not shell
	// text (SPEC §0.9.2, §10.2.1).
	argv = append(argv,
		"--no-sort",
		"--delimiter", sessionSep,
		"--with-nth=1..",
		"--nth=1",
		// Without this, fzf runs --bind commands with $SHELL -c, and POSIX
		// quoting of our path is wrong under fish or nushell (SPEC §0.5, Q17).
		"--with-shell", "sh",
	)

	if header != "" {
		if err := assertValidHeader(header); err != nil {
			return nil, err
		}
		argv = append(argv, "--header", header)
	}
	for _, b := range bindings {
		argv = append(argv, "--bind", b)
	}
	return argv, nil
}

// runFzf shows the items and returns the selection (SPEC §10.1, §12).
//
// Exit codes 0 (accepted), 1 (no match) and 130 (Esc / Ctrl-C) are all normal
// and all give their stdout, which for 1 and 130 is empty. Any other code is a
// real error — usually a malformed TMUX_FZF_OPTIONS.
func runFzf(items []string, header string, bindings []string) (string, error) {
	if err := assertValidItemsArray(items, "fzf items"); err != nil {
		return "", err
	}
	if err := assertValidHeader(header); err != nil {
		return "", err
	}

	argv, err := buildFzfArgv(header, bindings)
	if err != nil {
		return "", err
	}

	stdin := ensureTrailingNewline(strings.Join(items, "\n"))
	stdout, stderr, code, err := runFzfCmd(argv, stdin)
	if err != nil {
		logEvent(fmt.Sprintf("runFzf: error, exit code %d, stderr: %s", code, oneLine(stderr)))
		return "", err
	}

	switch code {
	case fzfExitOk, fzfExitNoMatch, fzfExitInterrupt:
		return strings.TrimRightFunc(stdout, unicode.IsSpace), nil
	default:
		logEvent(fmt.Sprintf("runFzf: error, exit code %d, stderr: %s", code, oneLine(stderr)))
		return "", fmt.Errorf("fzf exited with code %d: %s", code, oneLine(stderr))
	}
}

// oneLine folds a multi-line stderr into a single log line.
func oneLine(s string) string {
	s = strings.TrimSpace(s)
	s = strings.ReplaceAll(s, "\r\n", " ")
	s = strings.ReplaceAll(s, "\n", " ")
	return s
}

// ---------------------------------------------------------------------------
// Bindings (SPEC §3.9, §3.10, §3.11, Q17)
// ---------------------------------------------------------------------------

// switchBindings are the four `--bind` values of the `switch` list, in the .mjs
// order: DEL, ctrl-n, ctrl-p, then the digits (SPEC §3.11).
func switchBindings(self string) []string {
	return []string{
		"del:execute(" + bindCommand(self, "kill-single-from-line") + " {})" +
			"+reload(" + bindCommand(self, "reload-sessions") + ")",
		"ctrl-n:down+execute-silent(" + bindCommand(self, "switch-from-line") + " {})",
		"ctrl-p:up+execute-silent(" + bindCommand(self, "switch-from-line") + " {})",
		numberBindings(),
	}
}

// previewBindings are the Ctrl+N / Ctrl+P pair used by worktree-switch and
// capital-switch. DEL is deliberately NOT bound there (SPEC §3.9 step 6).
func previewBindings(self string) []string {
	return []string{
		"ctrl-n:down+execute-silent(" + bindCommand(self, "switch-from-line") + " {})",
		"ctrl-p:up+execute-silent(" + bindCommand(self, "switch-from-line") + " {})",
	}
}

// bindCommand shell-quotes the binary path and the action for the `sh` that fzf
// runs the binding under (Q17). `--with-shell sh` guarantees that shell is
// POSIX, so shellquote.Join is provably right.
//
// The `{}` placeholder is NEVER passed through here: fzf substitutes the row and
// applies its own quoting. Quoting it ourselves would quote the literal braces.
func bindCommand(self, action string) string {
	return joinShellWords(self, action)
}

// numberBindings is the 1..9 quick-switch binding (SPEC §3.11).
// It is one `--bind` value holding nine comma-separated bindings, exactly like
// the .mjs. `pos(N)` needs fzf >= 0.36; our floor is 0.51.0 anyway.
func numberBindings() string {
	parts := make([]string, 0, 9)
	for i := 1; i <= 9; i++ {
		parts = append(parts, fmt.Sprintf("%d:pos(%d)+accept", i, i))
	}
	return strings.Join(parts, ",")
}
