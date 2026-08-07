// prompt_test.go — the FIFO name prompt (SPEC §9, §9.2.1).
//
// The prompt is the highest-risk part of the port, so its two mechanical rules
// are pinned here: the FIFO really is a FIFO, and the read stops at the first
// line. Both run without tmux.
package main

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

// ---------------------------------------------------------------------------
// The script text (SPEC §9.2.1 step 4)
// ---------------------------------------------------------------------------

func TestPromptScriptRedirectsOnlyTheLastPrintf(t *testing.T) {
	// This is the rule that makes both the real prompt and the tests work.
	// If the whole script were redirected, the prompt pane would hold the
	// write end open from the start: the read could never see a clean end and
	// might pick up the pane's own empty line.
	if strings.Count(promptScript, ">") != 1 {
		t.Fatalf("the script must redirect exactly once, got %q", promptScript)
	}
	if !strings.HasSuffix(promptScript, "> "+fifoPath) {
		t.Errorf("the redirect must sit at the very end, got %q", promptScript)
	}
	// A `{ ... }` block would redirect every command inside it.
	if strings.ContainsAny(promptScript, "{}") {
		t.Errorf("no braces allowed in the script, got %q", promptScript)
	}
	if !strings.Contains(promptScript, "read n") {
		t.Errorf("the script must read one line from the user, got %q", promptScript)
	}
}

func TestFifoPathIsTheOneTheTestsWriteTo(t *testing.T) {
	// tests/helpers/workflow.py builds the same path from os.getuid().
	// It is a contract (SPEC §9.2.1, corrected 2026-08-07).
	want := filepath.Join(os.TempDir(), "tmux-session-"+strconv.Itoa(os.Getuid()), "name.fifo")
	if fifoPath != want {
		t.Errorf("fifoPath = %q, want %q", fifoPath, want)
	}
	// The directory must not collide with the debounce state file, which is
	// <tmp>/tmux-session-<uid>.json (SPEC §7.1).
	if fifoDir() == debouncePath() {
		t.Errorf("the FIFO directory collides with the debounce file: %q", fifoDir())
	}
}

func TestMakeFifoUsesPrivatePermissions(t *testing.T) {
	// /tmp is shared. A world-writable FIFO let any local user read the name
	// the user typed, or write a name of their own.
	dir := filepath.Join(t.TempDir(), "tmux-session-test")
	path := filepath.Join(dir, fifoName)

	if err := makeFifo(path); err != nil {
		t.Fatalf("makeFifo: %v", err)
	}

	dirInfo, err := os.Stat(dir)
	if err != nil {
		t.Fatalf("stat dir: %v", err)
	}
	if got := dirInfo.Mode().Perm(); got != fifoDirMode {
		t.Errorf("directory mode = %o, want %o", got, fifoDirMode)
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat fifo: %v", err)
	}
	if got := info.Mode().Perm(); got&0o077 != 0 {
		t.Errorf("fifo mode = %o, want no group or other bits", got)
	}
}

func TestMakeFifoRefusesAPathThatIsNotADirectory(t *testing.T) {
	// A plain file where our private directory belongs means somebody else got
	// there first. Fail loudly instead of carrying on.
	base := t.TempDir()
	blocker := filepath.Join(base, "tmux-session-test")
	if err := os.WriteFile(blocker, []byte("not a directory"), 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}

	if err := makeFifo(filepath.Join(blocker, fifoName)); err == nil {
		t.Fatal("want an error, got nil")
	}
}

func TestFifoReadTimeoutIsGenerous(t *testing.T) {
	// Go reaches the read in milliseconds and then waits about 2.0 s for the
	// test to write. A short timeout would turn a passing flow into an empty
	// name and a silent exit 0 (SPEC §9.2.1 step 5).
	if fifoReadTimeout < 5*time.Second {
		t.Errorf("fifoReadTimeout = %v, far too short", fifoReadTimeout)
	}
}

// ---------------------------------------------------------------------------
// makeFifo (SPEC §9.2.1 step 1)
// ---------------------------------------------------------------------------

func TestMakeFifoCreatesANamedPipe(t *testing.T) {
	path := filepath.Join(t.TempDir(), "fifo")

	if err := makeFifo(path); err != nil {
		t.Fatalf("makeFifo: %v", err)
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if info.Mode()&os.ModeNamedPipe == 0 {
		t.Errorf("mode = %v, want a named pipe", info.Mode())
	}
}

func TestMakeFifoReplacesALeftoverRegularFile(t *testing.T) {
	// A crashed run, or a test that opened the path before we created it,
	// leaves a REGULAR file behind. Without the remove, mkfifo fails with
	// EEXIST and every later run is broken.
	path := filepath.Join(t.TempDir(), "fifo")
	if err := os.WriteFile(path, []byte("stale"), 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}

	if err := makeFifo(path); err != nil {
		t.Fatalf("makeFifo over a regular file: %v", err)
	}
	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if info.Mode()&os.ModeNamedPipe == 0 {
		t.Errorf("mode = %v, want a named pipe", info.Mode())
	}
}

func TestMakeFifoIsIdempotent(t *testing.T) {
	path := filepath.Join(t.TempDir(), "fifo")
	if err := makeFifo(path); err != nil {
		t.Fatalf("first makeFifo: %v", err)
	}
	if err := makeFifo(path); err != nil {
		t.Fatalf("second makeFifo: %v", err)
	}
}

// ---------------------------------------------------------------------------
// readFirstLine (SPEC §9.2.1 steps 5 and 6)
// ---------------------------------------------------------------------------

func TestReadFirstLineReadsOnlyTheFirstLine(t *testing.T) {
	path := filepath.Join(t.TempDir(), "fifo")
	if err := makeFifo(path); err != nil {
		t.Fatalf("makeFifo: %v", err)
	}

	// This is exactly what tests/helpers/workflow.py:32 does: open the path
	// for writing, write one line, close.
	go func() {
		f, err := os.OpenFile(path, os.O_WRONLY, 0)
		if err != nil {
			return
		}
		_, _ = f.WriteString("fresh_session\nsecond line\n")
		_ = f.Close()
	}()

	line, err := readFirstLine(path, 5*time.Second)
	if err != nil {
		t.Fatalf("readFirstLine: %v", err)
	}
	if got := strings.TrimSpace(line); got != "fresh_session" {
		t.Errorf("line = %q, want %q", got, "fresh_session")
	}
}

func TestReadFirstLineAcceptsAWriterThatSendsNoNewline(t *testing.T) {
	path := filepath.Join(t.TempDir(), "fifo")
	if err := makeFifo(path); err != nil {
		t.Fatalf("makeFifo: %v", err)
	}

	go func() {
		f, err := os.OpenFile(path, os.O_WRONLY, 0)
		if err != nil {
			return
		}
		_, _ = f.WriteString("no_newline")
		_ = f.Close()
	}()

	line, err := readFirstLine(path, 5*time.Second)
	if err != nil {
		t.Fatalf("readFirstLine: %v", err)
	}
	if got := strings.TrimSpace(line); got != "no_newline" {
		t.Errorf("line = %q, want %q", got, "no_newline")
	}
}

func TestReadFirstLineTimesOutWhenNobodyWrites(t *testing.T) {
	path := filepath.Join(t.TempDir(), "fifo")
	if err := makeFifo(path); err != nil {
		t.Fatalf("makeFifo: %v", err)
	}

	start := time.Now()
	if _, err := readFirstLine(path, 200*time.Millisecond); err == nil {
		t.Fatal("want a timeout error, got nil")
	}
	// Without a bound this call would block forever (SPEC §9.1, M8).
	if elapsed := time.Since(start); elapsed > 3*time.Second {
		t.Errorf("the read took %v; the timeout did not work", elapsed)
	}
}
