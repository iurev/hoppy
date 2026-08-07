// fzf.go — building the fzf argv and running it.
//
// No shell. No heredoc. No eval. Items go to fzf's stdin, the selection comes
// back on stdout (SPEC §0.5, Q16).
//
// argv shape:
//
//	<words of TMUX_FZF_BIN> <words of TMUX_FZF_OPTIONS>
//	--no-sort --delimiter " @ " --with-nth=1.. --nth=1
//	--with-shell sh
//	[--header <text>] [--bind <binding> ...]
//
// FZF_DEFAULT_OPTS is left untouched in the child env; fzf reads it itself and
// our argv wins on conflict.
//
// Planned functions:
//
//	buildFzfArgv(header string, bindings []string) ([]string, error) -- SPEC §10.2/§10.3
//	runFzf(items []string, header string, bindings []string) (string, error) -- SPEC §10.1
//	switchBindings(self string) []string   -- del + ctrl-n + ctrl-p + 1..9 (SPEC §3.11)
//	previewBindings(self string) []string  -- ctrl-n + ctrl-p only (SPEC §3.9, §3.10)
//
// Exit codes (SPEC §10.1, §12, fzf src/constants.go):
//
//	0   ExitOk        -> use stdout
//	1   ExitNoMatch   -> use stdout (empty)
//	130 ExitInterrupt -> use stdout (empty)
//	2   ExitError     -> report fzf's stderr; usually a bad TMUX_FZF_OPTIONS
//
// NOT IMPLEMENTED YET.
package main

// Header texts. Keep them byte-identical: tests capture the pane and grep them
// (SPEC §10.4, test-contract §4.2).
const (
	headerAction  = "Select an action."
	headerSwitch  = "Select target session. Press 1-9 for quick switch. DEL to kill. Ctrl+N/P to preview."
	headerTarget  = "Select target session."
	headerTargets = "Select target session(s). Press TAB to mark multiple items."
)

// fzfMinVersion is the documented floor. 0.51.0 is the first release with
// --with-shell, which is what makes our POSIX quoting of --bind provably right.
const fzfMinVersion = "0.51.0"
