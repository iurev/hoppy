// state.go — the two JSON state files: frecency (SPEC §0.3, §5) and the
// Ctrl+N/P debounce record (SPEC §7). Both follow one rule: a missing,
// unreadable or broken file is treated as empty state. Never crash.
//
// writeAtomic lives in log.go and is shared by all three state files.
// Do NOT define a second one here.
package main

import (
	crand "crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
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
	frecencyDirName   = ".hoppy-frecency"
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

// frecencyPath is <appDir>/.hoppy-frecency/sessions.json (SPEC §0.3, §0.55).
// tests/conftest.py deletes exactly this directory between tests, so appDir
// must stay the directory holding the binary.
func frecencyPath(appDir string) string {
	return filepath.Join(appDir, frecencyDirName, frecencyFileName)
}

// loadFrecency reads the state file. Any failure gives empty state — every
// score is then 0 and tmux's own order survives (SPEC §0.3).
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
		// Drop the oldest into a fresh slice, so the trimmed entries cannot be
		// reached through the old backing array.
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
// The boundaries are exclusive `<`, so exactly one hour old scores 50, and a
// future timestamp has a negative age and scores 100. Both are .mjs behaviour.
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

// ---------------------------------------------------------------------------
// Debounce / delayed switch (SPEC §7) — the Ctrl+N / Ctrl+P session preview.
//
// One keypress runs two processes:
//
//	fzf --bind ctrl-n -> <self> switch-from-line <row>   (child, exits at once)
//	                     -> <self> delayed-switch <token> (detached grandchild)
//
// The grandchild sleeps, re-reads the state file, and switches only if its
// token is still the newest one. That is the whole "last target wins" rule.
// ---------------------------------------------------------------------------

const debounceFileMode = 0o600

// debouncePath is /tmp/tmux-session-<uid>.json (SPEC §7.1).
func debouncePath() string {
	return filepath.Join(os.TempDir(), "tmux-session-"+debounceID()+".json")
}

// debounceID is the uid. SPEC §7.1 also lists $USER and "pid-<pid>" fallbacks,
// but os.Getuid() only fails on Windows and this program is Linux-only, so both
// branches were dead code.
func debounceID() string {
	return strconv.Itoa(os.Getuid())
}

// debounceDelay is SESSION_SWITCH_DEBOUNCE_MS, default 300 ms (SPEC §7.3 step 2).
//
// Q6 FIX: this is read at grandchild start, so it comes AFTER sourceEnv and a
// value from .envs works. An explicit 0 really means "no delay"; the .mjs used
// `parseInt(x,10) || 300`, which turned 0 back into 300.
func debounceDelay() time.Duration {
	raw := strings.TrimSpace(os.Getenv("SESSION_SWITCH_DEBOUNCE_MS"))
	if raw == "" {
		return defaultDebounceMS * time.Millisecond
	}
	ms, err := strconv.Atoi(raw)
	if err != nil || ms < 0 {
		return defaultDebounceMS * time.Millisecond
	}
	return time.Duration(ms) * time.Millisecond
}

// readDebounce reads the state file. Every failure gives the neutral state
// {0, "", ""} and is only logged. It never crashes (SPEC §7.1).
func readDebounce(path string) debounceState {
	var empty debounceState

	raw, err := os.ReadFile(path)
	if err != nil {
		switch {
		case errors.Is(err, os.ErrNotExist):
			// Normal on the first keypress. Say nothing.
		case errors.Is(err, os.ErrPermission):
			logEvent("session debounce: no read access to " + path + ": " + err.Error())
		default:
			logEvent("session debounce: unexpected read error for " + path + ": " + err.Error())
		}
		return empty
	}

	var st debounceState
	if err := json.Unmarshal(raw, &st); err != nil {
		logEvent("session debounce: invalid JSON in " + path + ", resetting")
		return empty
	}
	// A negative lastWrite is meaningless; treat it as "never written".
	if st.LastWrite < 0 {
		st.LastWrite = 0
	}
	return st
}

// writeDebounce saves the state atomically. It reports success, because the
// caller falls back to an immediate switch when the write failed (SPEC §7.2).
func writeDebounce(path string, st debounceState) bool {
	data, err := json.Marshal(st)
	if err != nil {
		logEvent("session debounce: failed to write " + path + ": " + err.Error())
		return false
	}
	if err := writeAtomic(path, data, debounceFileMode); err != nil {
		if errors.Is(err, os.ErrPermission) {
			logEvent("session debounce: no write access to " + path + ": " + err.Error())
		} else {
			logEvent("session debounce: failed to write " + path + ": " + err.Error())
		}
		return false
	}
	return true
}

// newToken builds "<epochMillis>-<pid>-<8 base36 chars>" (SPEC §7.2 step 3).
// The three parts together make a collision practically impossible, which is
// what the "last write wins" comparison relies on.
func newToken(now time.Time, pid int) string {
	return fmt.Sprintf("%d-%d-%s", now.UnixMilli(), pid, randomSuffix())
}

// randomSuffix returns 8 base-36 characters. 5 bytes is 2^40, and 36^8 is
// larger, so the value always fits in 8 digits. crypto/rand.Read never fails.
func randomSuffix() string {
	var b [5]byte
	_, _ = crand.Read(b[:])
	n := uint64(b[0])<<32 | uint64(b[1])<<24 | uint64(b[2])<<16 | uint64(b[3])<<8 | uint64(b[4])
	s := strconv.FormatUint(n, 36)
	return strings.Repeat("0", 8-len(s)) + s
}

// scheduleSessionSwitch records the target and starts the delayed switch
// (SPEC §7.2). It never returns an error: a preview keypress must not be able
// to fail the fzf UI.
func scheduleSessionSwitch(target string) {
	name := strings.TrimSpace(target)
	if name == "" {
		return
	}

	path := debouncePath()
	now := time.Now()

	// "Last write wins" must really mean "last KEYPRESS wins" (F5, 2026-08-07).
	// Two switch-from-line processes can start microseconds apart and reach
	// os.Rename in the opposite order to the keypresses. lastWrite is what tells
	// them apart, so read it first: a stored write from the FUTURE belongs to a
	// newer keypress, and overwriting it would hand the token to the older one
	// and land the user one row short.
	if prev := readDebounce(path); prev.LastWrite > now.UnixMilli() {
		logEvent("session throttle: a newer keypress is already recorded, skipping target=" + name)
		return
	}

	token := newToken(now, os.Getpid())

	if !writeDebounce(path, debounceState{LastWrite: now.UnixMilli(), LastTarget: name, Token: token}) {
		logEvent("session throttle: write failed target=" + name + " token=" + token)
		immediateFallback(path, name, "session throttle: immediate fallback switch for "+name)
		return
	}
	logEvent("session throttle: scheduled target=" + name + " token=" + token)

	if err := spawnDelayedSwitch(token); err != nil {
		logEvent("session throttle: spawn failed for " + name + ": " + err.Error())
		immediateFallback(path, name,
			"session throttle: immediate fallback after spawn failure for "+name)
	}
}

// spawnDelayedSwitch starts the detached grandchild (SPEC §7.2 step 7).
// Each of the three details below breaks a test if it is wrong:
//
//	nil std fds   -> Go maps them to /dev/null. Inheriting the pty means
//	                 pexpect never sees EOF (test_script_executes.py).
//	Setsid: true  -> closing the popup must not kill the child before it fires.
//	Release()     -> we exit immediately; we never Wait.
func spawnDelayedSwitch(token string) error {
	cmd := exec.Command(selfPath, "delayed-switch", token)
	cmd.Stdin, cmd.Stdout, cmd.Stderr = nil, nil, nil
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	if err := cmd.Start(); err != nil {
		return err
	}
	return cmd.Process.Release()
}

// immediateFallback switches now, because the debounce machinery could not be
// used (SPEC §7.2 step 6). It also clears the token, so any grandchild that is
// still asleep does nothing when it wakes up.
func immediateFallback(path, name, successMsg string) {
	if err := tmuxSwitchClient(name); err != nil {
		logEvent("session throttle: fallback switch failed for " + name + ": " + err.Error())
		return
	}
	logEvent(successMsg)
	_ = writeDebounce(path, debounceState{
		LastWrite:  time.Now().UnixMilli(),
		LastTarget: name,
		Token:      "",
	})
}

// handleDelayedSwitch is the body of the `delayed-switch` action (SPEC §7.3).
func handleDelayedSwitch(token string) {
	if token == "" {
		logEvent("session throttle: delayed switch invoked without token, skipping")
		return
	}

	time.Sleep(debounceDelay())

	path := debouncePath()
	st := readDebounce(path)
	target := strings.TrimSpace(st.LastTarget)

	if !shouldDelayedSwitch(st, token) {
		logEvent(fmt.Sprintf("session throttle: delayed switch skip token=%s, stateToken=%s, target=%s",
			token, orNull(st.Token), orNone(target)))
		return
	}

	if err := tmuxSwitchClient(target); err != nil {
		logEvent("session throttle: delayed switch failed for " + target + ": " + err.Error())
		return
	}
	logEvent("session throttle: delayed switch executed for " + target)

	// Clearing the token makes a second delayed-switch for it a no-op.
	_ = writeDebounce(path, debounceState{
		LastWrite:  time.Now().UnixMilli(),
		LastTarget: target,
		Token:      "",
	})
}

// shouldDelayedSwitch is the whole "last target wins" rule, kept pure so it can
// be table-tested (SPEC §7.3 step 4): switch only when the state still names a
// target AND the token in the file is still ours. A newer keypress overwrites
// the token, so an older grandchild stays quiet.
func shouldDelayedSwitch(st debounceState, token string) bool {
	if token == "" {
		return false
	}
	if strings.TrimSpace(st.LastTarget) == "" {
		return false
	}
	return st.Token == token
}

// orNull and orNone print empty fields the way the .mjs printed a JSON null, so
// log message 13 keeps its exact wording (SPEC §13.2).
func orNull(s string) string {
	if s == "" {
		return "null"
	}
	return s
}

func orNone(s string) string {
	if s == "" {
		return "(none)"
	}
	return s
}
