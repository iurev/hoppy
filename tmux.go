// tmux.go — every external process call lives here.
//
// This is the ONLY file that runs tmux, git or fzf-adjacent processes.
// It holds the single abstraction in the program: the `runner` function type.
// Tests swap `run` for a fake, so all list/format/filter logic in sessions.go
// and text.go is unit-testable with no tmux server.
//
// READ SPEC §0.9 BEFORE ADDING A CALL. The quotes in SPEC are SHELL quotes.
// Never copy a quote into an argv element.
//
// Planned functions:
//
//	execRun(argv ...string) (string, error)     -- real os/exec runner
//	tmuxCurrentSession() (string, error)        -- display-message -p '#S'
//	tmuxPaneCurrentPath() (string, error)       -- display-message -p '#{pane_current_path}'
//	tmuxListSessions() ([]string, error)        -- -F "#S @ #{session_windows} windows"
//	tmuxListSessionsRaw() ([]string, error)     -- default format, for attached lookup
//	tmuxListPanePaths() (map[string][]string, error)
//	tmuxSwitchClient(name string) error
//	tmuxKillSession(name string) error
//	tmuxNewSessionDetached(name string) error
//	tmuxRenameSession(old, new string) error
//	tmuxDetachClient(name string) error
//	tmuxHasSession(name string) bool
//	tmuxDisplayMessage(msg string) error
//	tmuxDisplayPopup(title, action string) error
//	tmuxSplitPrompt(script string) error
//	tmuxKillPane(paneID string) error
//	gitWorktrees(dir string) ([]string, error)  -- SPEC §6.1
//
// NOT IMPLEMENTED YET.
package main

// runner runs one external command and returns its stdout.
// This is the program's only seam for tests. Production sets run = execRun.
type runner func(argv ...string) (stdout string, err error)

// run is the process runner used by every tmux/git call.
// Tests replace it with a fake; nothing else in the program takes a dependency
// on os/exec.
var run runner
