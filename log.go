// log.go — the append-only event log and its in-place rotation (SPEC §13).
//
// Line format, byte-identical to the .mjs:
//
//	2026-07-20T11:06:44.123Z action=switch: complete
//
// Failure policy: swallow every error. Logging must never change the outcome
// of an action, so logEvent returns nothing.
package main

import (
	"os"
	"path/filepath"
	"strings"
	"time"
	"unicode/utf8"
)

const (
	logFileName = "hoppy.log"
	// LOG_MAX_BYTES = 256 * 1024. Above this size the file is rotated.
	logMaxBytes = 262144
	// LOG_TRIM_TARGET = floor(262144 * 0.8). Rotation keeps about this much.
	logTrimTarget = 209715
	// logTimeLayout is the exact .mjs toISOString() shape. The trailing "Z" is
	// a literal here: Go only treats "Z" as an offset when "07" follows it.
	logTimeLayout = "2006-01-02T15:04:05.000Z"
)

// logPath is <appDir>/hoppy.log (SPEC §0.55), set once by main.
// While it is empty, logging is a no-op — that keeps unit tests silent.
var logPath string

func setLogPath(appDir string) {
	logPath = filepath.Join(appDir, logFileName)
}

// logEvent appends one event line. It rotates first if the file grew too big.
// Every error is swallowed on purpose (SPEC §13).
func logEvent(msg string) {
	if logPath == "" {
		return
	}
	_ = rotate(logPath)

	line := time.Now().UTC().Format(logTimeLayout) + " " + msg + "\n"
	f, err := os.OpenFile(logPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		return
	}
	_, _ = f.WriteString(line)
	_ = f.Close()
}

// rotate trims the log in place when it is over logMaxBytes. There is no
// .log.1 backup file: the newest lines are kept, older ones go.
//
// ACCEPTED RACE — not fixed, on purpose. Rotation is read + writeAtomic +
// rename, and several hoppy processes really do run at once (fzf's --bind
// calls re-invoke this binary). A concurrent O_APPEND write can land in the
// unlinked inode and be lost. We accept it: the log is a debugging aid, nothing
// reads it back, and the fix (flock) costs more than a missing line.
func rotate(path string) error {
	info, err := os.Stat(path)
	if err != nil {
		// No file yet, so nothing to rotate.
		return nil
	}
	if info.Size() <= logMaxBytes {
		return nil
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}

	// A well-formed log ends with "\n". Splitting would then give a trailing
	// empty element, which is not a real line.
	content := strings.TrimSuffix(string(raw), "\n")
	lines := []string{}
	if content != "" {
		lines = strings.Split(content, "\n")
	}

	kept := trimLines(lines, logTrimTarget, logMaxBytes)
	out := strings.Join(kept, "\n")
	if out != "" {
		out += "\n"
	}
	return writeAtomic(path, []byte(out), 0644)
}

// trimLines keeps the newest lines that fit in target bytes, counting one byte
// for each line's newline. Input and output are newest-last.
//
// This is the M10 fix (SPEC §13.3): the .mjs erased the WHOLE log when the
// newest line alone was bigger than the target. Three rules replace that:
//
//  1. never return an empty result while at least one line exists
//  2. if the newest line alone is over target, keep exactly that one line
//  3. if the newest line alone is over max, truncate the LINE, not the file
func trimLines(lines []string, target, max int) []string {
	if len(lines) == 0 {
		return []string{}
	}

	bytesCount := 0
	keepFrom := 0
	for i := len(lines) - 1; i >= 0; i-- {
		lineBytes := len(lines[i]) + 1 // + the newline
		if bytesCount+lineBytes > target {
			keepFrom = i + 1
			break
		}
		bytesCount += lineBytes
	}

	// Rules 1 and 2: the newest line did not fit, so keep it alone.
	if keepFrom >= len(lines) {
		keepFrom = len(lines) - 1
	}

	kept := make([]string, len(lines)-keepFrom)
	copy(kept, lines[keepFrom:])

	// Rule 3: one line that is bigger than the whole budget gets cut short.
	if len(kept) == 1 && len(kept[0])+1 > max {
		kept[0] = truncateBytes(kept[0], max-1)
	}
	return kept
}

// truncateBytes cuts s down to at most n bytes without splitting a rune.
// The loop backs up over every continuation byte; utf8.DecodeLastRuneInString
// would only drop one of them and leave the rest of a broken 3- or 4-byte rune.
func truncateBytes(s string, n int) string {
	if n <= 0 {
		return ""
	}
	if len(s) <= n {
		return s
	}
	for n > 0 && !utf8.RuneStart(s[n]) {
		n--
	}
	return s[:n]
}

// writeAtomic writes data to path through a temp file in the same directory.
// It is shared by frecency (§0.3), debounce (§7.1) and log rotation (§13.3);
// do not write a second copy in state.go.
//
// Sync() before rename is not optional (SPEC §0.3): without it a power loss can
// leave the renamed file full of zeros. The directory fsync is skipped on
// purpose.
func writeAtomic(path string, data []byte, mode os.FileMode) error {
	dir := filepath.Dir(path)
	tmp, err := os.CreateTemp(dir, "."+filepath.Base(path)+".tmp*")
	if err != nil {
		return err
	}
	tmpName := tmp.Name()

	cleanup := func() {
		_ = tmp.Close()
		_ = os.Remove(tmpName)
	}
	if _, err := tmp.Write(data); err != nil {
		cleanup()
		return err
	}
	if err := tmp.Sync(); err != nil {
		cleanup()
		return err
	}
	if err := tmp.Chmod(mode); err != nil {
		cleanup()
		return err
	}
	if err := tmp.Close(); err != nil {
		_ = os.Remove(tmpName)
		return err
	}
	if err := os.Rename(tmpName, path); err != nil {
		_ = os.Remove(tmpName)
		return err
	}
	return nil
}
