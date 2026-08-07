// state.go — the two JSON state files, plus the atomic write both share.
//
//  1. Frecency : <appDir>/.session-frecency/sessions.json  (SPEC §0.3, §5)
//  2. Debounce : /tmp/tmux-session-<uid>.json              (SPEC §7.1)
//
// Both files follow the same rule: a missing, unreadable or broken file is
// treated as empty state. Never crash.
//
// This file implements the FRECENCY half only. The debounce half (§7.1-§7.3:
// readDebounce, writeDebounce, newToken, scheduleSessionSwitch,
// handleDelayedSwitch and the detached spawn) is the next implementer's work.
// The recipe for the detached spawn stays here so it is not lost:
//
//	cmd := exec.Command(self, "delayed-switch", token)
//	cmd.Stdin, cmd.Stdout, cmd.Stderr = nil, nil, nil // -> /dev/null
//	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
//	cmd.Start(); cmd.Process.Release()                // never Wait
//
// If the grandchild inherits the pty, pexpect never sees EOF and
// test_script_executes.py:32 fails.
//
// writeAtomic lives in log.go and is shared by all three state files.
// Do NOT define a second one here (SPEC §0.3, §7.1, §13.3).
package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

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
	frecencyVersion   = 1
	frecencyDirMode   = 0o700
	frecencyFileMode  = 0o600
	defaultDebounceMS = 300
)

// selectedAt returns the timestamps of one session, or nil when it is unknown.
func (s frecencyState) selectedAt(name string) []int64 {
	if s.Sessions == nil {
		return nil
	}
	return s.Sessions[name].SelectedAt
}

// frecencyPath is <appDir>/.session-frecency/sessions.json (SPEC §0.3, §0.55).
// tests/conftest.py:37 deletes exactly this directory between tests, so appDir
// must stay the directory holding the binary.
func frecencyPath(appDir string) string {
	return filepath.Join(appDir, frecencyDirName, frecencyFileName)
}

// loadFrecency reads the state file. A missing directory, a missing file, an
// unreadable file, broken JSON or a wrong version all give empty state — every
// score is then 0 and tmux's own order survives. It never returns an error and
// it never crashes (SPEC §0.3).
func loadFrecency(appDir string) frecencyState {
	empty := frecencyState{Version: frecencyVersion, Sessions: map[string]frecencySession{}}

	raw, err := os.ReadFile(frecencyPath(appDir))
	if err != nil {
		return empty
	}
	var st frecencyState
	if err := json.Unmarshal(raw, &st); err != nil {
		return empty
	}
	if st.Version != frecencyVersion || st.Sessions == nil {
		return empty
	}
	return st
}

// saveFrecency writes the state file atomically (SPEC §0.3).
// The directory is created with mode 0700 and the file with 0600.
func saveFrecency(appDir string, st frecencyState) error {
	path := frecencyPath(appDir)
	if err := os.MkdirAll(filepath.Dir(path), frecencyDirMode); err != nil {
		return err
	}
	data, err := json.Marshal(st)
	if err != nil {
		return err
	}
	return writeAtomic(path, data, frecencyFileMode)
}

// recordSelection appends one timestamp for name and saves (SPEC §0.3, §5.3).
// Only the newest `frecencyCap` timestamps are kept, oldest first.
//
// Called ONLY after a successful `tmux switch-client`, and only from `switch`,
// `worktree-switch` and `capital-switch`. Never for new/rename/kill/detach or
// the Ctrl+N/P preview.
//
// A write failure is logged and swallowed: losing frecency history must never
// turn a successful switch into a failed command.
func recordSelection(appDir, name string, now time.Time) {
	if name == "" {
		return
	}
	st := loadFrecency(appDir)
	if st.Sessions == nil {
		st.Sessions = map[string]frecencySession{}
	}

	rec := st.Sessions[name]
	rec.SelectedAt = append(rec.SelectedAt, now.UnixMilli())
	if n := len(rec.SelectedAt); n > frecencyCap {
		// Drop the oldest. Copy into a fresh slice so the trimmed entries
		// cannot be reached through the old backing array.
		trimmed := make([]int64, frecencyCap)
		copy(trimmed, rec.SelectedAt[n-frecencyCap:])
		rec.SelectedAt = trimmed
	}
	st.Sessions[name] = rec

	if err := saveFrecency(appDir, st); err != nil {
		logEvent("frecency: failed to write " + frecencyPath(appDir) + ": " + err.Error())
	}
}

// score sums the frecency buckets of SPEC §5.2.
//
//	age < 1 hour     -> 100
//	age < 24 hours   -> 50
//	age < 168 hours  -> 10
//	otherwise        -> 1
//
// The boundaries are exclusive `<`, so exactly one hour old scores 50.
// A timestamp in the future gives a negative age and lands in the first bucket,
// scoring 100. Both are the .mjs behaviour and both are kept.
func score(selectedAt []int64, now time.Time) int {
	nowMS := now.UnixMilli()
	total := 0
	for _, ts := range selectedAt {
		ageHours := float64(nowMS-ts) / 3600000.0
		switch {
		case ageHours < 1:
			total += 100
		case ageHours < 24:
			total += 50
		case ageHours < 168:
			total += 10
		default:
			total++
		}
	}
	return total
}
