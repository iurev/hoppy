// Command session-zx is a tmux session switcher driven by fzf.
// It is the Go port of session-zx.mjs. See SPEC.md and ARCHITECTURE.md.
//
// This file owns:
//   - startup (SPEC §1): appDir, log path, debounce file path, .envs sourcing
//   - argv parsing (SPEC §1.2): os.Args only, "argument present = argument given"
//   - the action router (SPEC §2), in the exact order the .mjs uses
//   - one small handler function per action (SPEC §3)
//
// Planned functions:
//
//	main()                     -- startup + route
//	route(action, arg string) int
//	actionMenu() (string, error)     -- §3.1
//	actionPopup(kind string) error   -- §3.2
//	actionReloadSessions() error     -- §3.3
//	actionKillSingleFromLine(line string) error -- §3.4
//	actionSwitchFromLine(line string) error     -- §3.5
//	actionDelayedSwitch(token string) error     -- §3.6
//	actionKillSingle(name string) int           -- §3.7
//	actionNew() int                             -- §3.8
//	actionWorktreeSwitch() int                  -- §3.9
//	actionCapitalSwitch() int                   -- §3.10
//	actionSwitch() int                          -- §3.11
//	actionRename() int                          -- §3.12
//	actionKill() int                            -- §3.13
//	actionDetach() int                          -- §3.14
//
// NOT IMPLEMENTED YET. This is the compiling skeleton only.
package main

import (
	"fmt"
	"os"
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

func main() {
	action := ""
	arg := ""
	if len(os.Args) > 1 {
		action = os.Args[1]
	}
	if len(os.Args) > 2 {
		arg = os.Args[2]
	}

	// SKELETON ONLY. Real routing lands in the implementation commits.
	fmt.Printf("session-zx skeleton: action=%q arg=%q (not implemented yet)\n", action, arg)
	os.Exit(0)
}
