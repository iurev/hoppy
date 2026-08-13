package main

import (
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"regexp"
	"strings"
	"testing"
	"unicode/utf8"
)

func TestTrimLinesKeepsNewest(t *testing.T) {
	// Each line is "abcd" -> 5 bytes with the newline. Target 12 fits 2 lines.
	lines := []string{"aaaa", "bbbb", "cccc", "dddd"}
	got := trimLines(lines, 12, 100)
	want := []string{"cccc", "dddd"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("trimLines = %#v, want %#v", got, want)
	}
}

func TestTrimLinesKeepsAllWhenEverythingFits(t *testing.T) {
	lines := []string{"a", "b", "c"}
	got := trimLines(lines, 1000, 2000)
	if !reflect.DeepEqual(got, lines) {
		t.Errorf("trimLines = %#v, want %#v", got, lines)
	}
}

func TestTrimLinesEmptyInput(t *testing.T) {
	if got := trimLines(nil, 100, 200); len(got) != 0 {
		t.Errorf("trimLines(nil) = %#v, want empty", got)
	}
}

// M10, SPEC §13.3: this exact case erased the whole log in the .mjs.
// The newest line alone is bigger than the trim target, so the .mjs loop broke
// with keepFromIndex == lines.length and wrote an empty file.
func TestTrimLinesM10WipeBug(t *testing.T) {
	huge := strings.Repeat("x", 500)
	lines := []string{"old one", "old two", huge}

	got := trimLines(lines, 100, 10000)

	if len(got) == 0 {
		t.Fatal("M10 regression: trimLines wiped the whole log")
	}
	if len(got) != 1 || got[0] != huge {
		t.Fatalf("trimLines = %#v, want only the newest line", got)
	}
}

// A huge line in the MIDDLE must not stop the newest lines from being kept.
//
// This is NOT "the other half of M10": the .mjs handles this input correctly.
// Its loop breaks on the huge line with keepFromIndex = i+1, which points at
// "new one", so the .mjs also keeps the two newest lines. The case is here as a
// guard against a Go-only regression, not as a .mjs bug.
func TestTrimLinesHugeLineInTheMiddle(t *testing.T) {
	huge := strings.Repeat("x", 500)
	lines := []string{"old", huge, "new one", "new two"}

	got := trimLines(lines, 100, 10000)
	want := []string{"new one", "new two"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("trimLines = %#v, want %#v", got, want)
	}
}

// Rule 3: a single line bigger than max is truncated, not dropped.
func TestTrimLinesTruncatesALineOverMax(t *testing.T) {
	huge := strings.Repeat("x", 500)
	got := trimLines([]string{huge}, 100, 200)

	if len(got) != 1 {
		t.Fatalf("trimLines = %#v, want exactly one line", got)
	}
	if len(got[0]) != 199 {
		t.Errorf("line length = %d, want 199 (max 200 minus the newline)", len(got[0]))
	}
	if !strings.HasPrefix(huge, got[0]) {
		t.Error("the truncated line must be a prefix of the original")
	}
}

func TestTruncateBytesKeepsRunesWhole(t *testing.T) {
	// Three-byte runes. Cutting at 4 bytes must fall back to 3.
	s := strings.Repeat(string(rune(0x3000)), 3)
	got := truncateBytes(s, 4)
	if len(got) != 3 {
		t.Errorf("truncateBytes gave %d bytes, want 3", len(got))
	}
	if !utf8.ValidString(got) {
		t.Error("truncateBytes split a rune")
	}
	if truncateBytes("abc", 0) != "" {
		t.Error("truncateBytes with n=0 must give an empty string")
	}
	if truncateBytes("abc", 10) != "abc" {
		t.Error("truncateBytes must not pad or change a short string")
	}
}

// ---------------------------------------------------------------------------
// rotate + logEvent, against a real temp file
// ---------------------------------------------------------------------------

func TestRotateDoesNothingWhenSmall(t *testing.T) {
	path := filepath.Join(t.TempDir(), "hoppy.log")
	body := "line one\nline two\n"
	if err := os.WriteFile(path, []byte(body), 0644); err != nil {
		t.Fatal(err)
	}
	if err := rotate(path); err != nil {
		t.Fatal(err)
	}
	got, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != body {
		t.Errorf("rotate changed a small file: %q", string(got))
	}
}

func TestRotateMissingFileIsNotAnError(t *testing.T) {
	path := filepath.Join(t.TempDir(), "nope.log")
	if err := rotate(path); err != nil {
		t.Errorf("rotate on a missing file returned %v", err)
	}
}

func TestRotateTrimsAndKeepsTheNewestLines(t *testing.T) {
	path := filepath.Join(t.TempDir(), "hoppy.log")

	var b strings.Builder
	// Each line is 99 chars + newline = 100 bytes. 3000 lines = 300000 bytes,
	// which is over logMaxBytes.
	for i := 0; i < 3000; i++ {
		b.WriteString(strings.Repeat("x", 93))
		b.WriteString(pad4(i))
		b.WriteString("ee\n")
	}
	if err := os.WriteFile(path, []byte(b.String()), 0644); err != nil {
		t.Fatal(err)
	}

	if err := rotate(path); err != nil {
		t.Fatal(err)
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if info.Size() > logTrimTarget {
		t.Errorf("file is %d bytes after rotation, want <= %d", info.Size(), logTrimTarget)
	}
	if info.Size() == 0 {
		t.Fatal("rotation wiped the file")
	}

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if !strings.HasSuffix(string(raw), "\n") {
		t.Error("the rotated file must still end with a newline")
	}
	// The newest line must survive.
	if !strings.Contains(string(raw), pad4(2999)+"ee") {
		t.Error("the newest line was lost")
	}
	// The oldest line must be gone.
	if strings.Contains(string(raw), pad4(0)+"ee") {
		t.Error("the oldest line survived")
	}
}

// M10 end to end: one giant line must not erase the file.
func TestRotateDoesNotWipeOnOneGiantLine(t *testing.T) {
	path := filepath.Join(t.TempDir(), "hoppy.log")
	giant := strings.Repeat("y", logMaxBytes+10)
	if err := os.WriteFile(path, []byte("old\n"+giant+"\n"), 0644); err != nil {
		t.Fatal(err)
	}

	if err := rotate(path); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if len(raw) == 0 {
		t.Fatal("M10 regression: rotation erased the whole log")
	}
	if len(raw) > logMaxBytes {
		t.Errorf("file is %d bytes, want <= %d", len(raw), logMaxBytes)
	}
	if !strings.HasPrefix(string(raw), "yyy") {
		t.Error("the giant newest line should be what is left")
	}
}

// pad4 numbers a test log line so we can tell the oldest from the newest.
func pad4(n int) string {
	return fmt.Sprintf("%04d", n)
}

var logLineRe = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z .*\n$`)

func TestLogEventLineFormat(t *testing.T) {
	dir := t.TempDir()
	old := logPath
	defer func() { logPath = old }()
	setLogPath(dir)

	logEvent("action=switch: switched to work")
	logEvent("session throttle: scheduled target=work token=abc")

	raw, err := os.ReadFile(filepath.Join(dir, logFileName))
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.SplitAfter(string(raw), "\n")
	if len(lines) < 2 {
		t.Fatalf("got %d lines, want 2", len(lines))
	}
	for i := 0; i < 2; i++ {
		if !logLineRe.MatchString(lines[i]) {
			t.Errorf("line %d = %q, does not match the .mjs format", i, lines[i])
		}
	}
	if !strings.Contains(lines[0], " action=switch: switched to work\n") {
		t.Errorf("line 0 lost its message: %q", lines[0])
	}
}

func TestLogEventIsANoOpWithoutAPath(t *testing.T) {
	old := logPath
	defer func() { logPath = old }()

	// Run from an empty directory, so "no file was created" is provable rather
	// than merely "it did not panic".
	dir := t.TempDir()
	wd, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Chdir(dir); err != nil {
		t.Fatal(err)
	}
	defer func() { _ = os.Chdir(wd) }()

	logPath = ""
	logEvent("this must go nowhere and must not panic")

	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 0 {
		t.Errorf("logEvent created %d file(s) with no log path set: %v", len(entries), entries)
	}
	if _, err := os.Stat(filepath.Join(dir, logFileName)); !os.IsNotExist(err) {
		t.Errorf("logEvent created %s with no log path set", logFileName)
	}
}

// SPEC §13: rotation triggers on `size > logMaxBytes`, so the boundary itself
// must NOT rotate. One byte more must.
func TestRotateBoundaryAtLogMaxBytes(t *testing.T) {
	// Build a file of exactly n bytes out of many short lines, so that a
	// rotation would be clearly visible (it would drop about 20% of them).
	build := func(n int) string {
		var b strings.Builder
		for b.Len()+10 <= n {
			b.WriteString("abcdefghi\n") // 10 bytes
		}
		for b.Len() < n {
			b.WriteString("z")
		}
		return b.String()
	}

	t.Run("exactly 262144 bytes does not rotate", func(t *testing.T) {
		path := filepath.Join(t.TempDir(), "hoppy.log")
		body := build(logMaxBytes)
		if len(body) != logMaxBytes {
			t.Fatalf("test setup wrote %d bytes, want %d", len(body), logMaxBytes)
		}
		if err := os.WriteFile(path, []byte(body), 0644); err != nil {
			t.Fatal(err)
		}
		if err := rotate(path); err != nil {
			t.Fatal(err)
		}
		info, err := os.Stat(path)
		if err != nil {
			t.Fatal(err)
		}
		if info.Size() != int64(logMaxBytes) {
			t.Errorf("file is %d bytes, want it untouched at %d", info.Size(), logMaxBytes)
		}
	})

	t.Run("262145 bytes rotates", func(t *testing.T) {
		path := filepath.Join(t.TempDir(), "hoppy.log")
		body := build(logMaxBytes + 1)
		if len(body) != logMaxBytes+1 {
			t.Fatalf("test setup wrote %d bytes, want %d", len(body), logMaxBytes+1)
		}
		if err := os.WriteFile(path, []byte(body), 0644); err != nil {
			t.Fatal(err)
		}
		if err := rotate(path); err != nil {
			t.Fatal(err)
		}
		info, err := os.Stat(path)
		if err != nil {
			t.Fatal(err)
		}
		if info.Size() > logTrimTarget {
			t.Errorf("file is %d bytes after rotation, want <= %d", info.Size(), logTrimTarget)
		}
		if info.Size() == 0 {
			t.Error("rotation wiped the file")
		}
	})
}

// A rewritten over-long line must land at exactly logMaxBytes, so that the very
// next logEvent does not rotate again (SPEC §13.3: truncate to logMaxBytes-1,
// plus the newline).
func TestRotateOfAGiantLineCannotReTrigger(t *testing.T) {
	path := filepath.Join(t.TempDir(), "hoppy.log")
	giant := strings.Repeat("y", logMaxBytes*2)
	if err := os.WriteFile(path, []byte(giant+"\n"), 0644); err != nil {
		t.Fatal(err)
	}
	if err := rotate(path); err != nil {
		t.Fatal(err)
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if info.Size() != int64(logMaxBytes) {
		t.Fatalf("file is %d bytes, want exactly %d", info.Size(), logMaxBytes)
	}
	// The second rotate must be a no-op: size is not > logMaxBytes.
	if err := rotate(path); err != nil {
		t.Fatal(err)
	}
	again, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if again.Size() != int64(logMaxBytes) {
		t.Errorf("second rotate changed the file to %d bytes", again.Size())
	}
}

func TestLogEventSwallowsErrors(t *testing.T) {
	old := logPath
	defer func() { logPath = old }()
	// A path inside a file, so every open fails.
	dir := t.TempDir()
	blocker := filepath.Join(dir, "blocker")
	if err := os.WriteFile(blocker, []byte("x"), 0644); err != nil {
		t.Fatal(err)
	}
	logPath = filepath.Join(blocker, "hoppy.log")
	logEvent("must not panic and must not return anything")
}

func TestWriteAtomicReplacesContent(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state.json")
	if err := writeAtomic(path, []byte("first"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := writeAtomic(path, []byte("second"), 0600); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if string(raw) != "second" {
		t.Errorf("content = %q, want %q", string(raw), "second")
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	if info.Mode().Perm() != 0600 {
		t.Errorf("mode = %v, want 0600", info.Mode().Perm())
	}
}

func TestWriteAtomicLeavesNoTempFile(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "state.json")
	if err := writeAtomic(path, []byte("x"), 0600); err != nil {
		t.Fatal(err)
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 {
		t.Errorf("directory holds %d files, want only the target", len(entries))
	}
}
