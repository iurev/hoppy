// state.go — the two JSON state files, plus the atomic write both share.
//
// 1. Frecency  : <appDir>/.session-frecency/sessions.json  (SPEC §0.3, §5)
// 2. Debounce  : /tmp/tmux-session-<uid>.json              (SPEC §7.1)
//
// Both files follow the same rule: a missing, unreadable or broken file is
// treated as empty state. Never crash.
//
// Planned functions:
//
//	writeAtomic(path string, data []byte, mode os.FileMode) error -- temp + Sync + rename
//	loadFrecency(dir string) frecencyState                        -- SPEC §0.3
//	saveFrecency(dir string, st frecencyState) error
//	recordSelection(dir, name string, now time.Time)              -- cap 10, newest last
//	score(sel []int64, now time.Time) int                         -- SPEC §5.2 buckets 100/50/10/1
//	readDebounce(path string) debounceState                       -- SPEC §7.1
//	writeDebounce(path string, st debounceState) bool
//	newToken(now time.Time, pid int) string                       -- "<ms>-<pid>-<8 base36>"
//	scheduleSessionSwitch(name string) error                      -- SPEC §7.2
//	handleDelayedSwitch(token string) error                       -- SPEC §7.3
//
// Detached spawn recipe for §7.2 step 7 (this exact shape matters):
//
//	cmd := exec.Command(self, "delayed-switch", token)
//	cmd.Stdin, cmd.Stdout, cmd.Stderr = nil, nil, nil // -> /dev/null
//	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
//	cmd.Start(); cmd.Process.Release()                // never Wait
//
// If the grandchild inherits the pty, pexpect never sees EOF and
// test_script_executes.py:32 fails.
//
// NOT IMPLEMENTED YET.
package main

// frecencyState is the on-disk schema of §0.3. version is always 1;
// any other value means "treat the whole file as empty".
type frecencyState struct {
	Version  int                        `json:"version"`
	Sessions map[string]frecencySession `json:"sessions"`
}

// frecencySession holds epoch-millisecond timestamps, oldest first, max 10.
type frecencySession struct {
	SelectedAt []int64 `json:"selectedAt"`
}

// debounceState is the Ctrl+N / Ctrl+P "last write wins" record (SPEC §7.1).
type debounceState struct {
	LastWrite  int64  `json:"lastWrite"`
	LastTarget string `json:"lastTarget"`
	Token      string `json:"token"`
}

const (
	frecencyDirName   = ".session-frecency"
	frecencyFileName  = "sessions.json"
	frecencyCap       = 10
	defaultDebounceMS = 300
)
