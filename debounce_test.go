// debounce_test.go — the §7 half of state.go.
//
// It sits next to state_test.go instead of inside it because the frecency
// tests there already run to 290 lines, and the two halves share nothing but
// writeAtomic.
//
// Everything here is pure or file-only: no tmux, no fzf, no processes.
package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
	"time"
)

// ---------------------------------------------------------------------------
// shouldDelayedSwitch — the "last target wins" decision (SPEC §7.3 step 4)
// ---------------------------------------------------------------------------

func TestShouldDelayedSwitch(t *testing.T) {
	const mine = "1721476800000-42-abcd1234"
	const newer = "1721476800500-43-zzzz9999"

	cases := []struct {
		name  string
		state debounceState
		token string
		want  bool
	}{
		{
			"our token is still the newest",
			debounceState{LastWrite: 1, LastTarget: "work", Token: mine},
			mine, true,
		},
		{
			"a newer keypress replaced the token",
			debounceState{LastWrite: 2, LastTarget: "other", Token: newer},
			mine, false,
		},
		{
			"the token was cleared after a successful switch",
			debounceState{LastWrite: 2, LastTarget: "work", Token: ""},
			mine, false,
		},
		{
			"no target recorded",
			debounceState{LastWrite: 2, LastTarget: "", Token: mine},
			mine, false,
		},
		{
			"a whitespace-only target does not count",
			debounceState{LastWrite: 2, LastTarget: "   ", Token: mine},
			mine, false,
		},
		{
			"we were invoked without a token",
			debounceState{LastWrite: 2, LastTarget: "work", Token: ""},
			"", false,
		},
		{
			"empty state, empty token: still no switch",
			debounceState{},
			"", false,
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := shouldDelayedSwitch(c.state, c.token); got != c.want {
				t.Errorf("shouldDelayedSwitch(%+v, %q) = %v, want %v",
					c.state, c.token, got, c.want)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Token format (SPEC §7.2 step 3)
// ---------------------------------------------------------------------------

var tokenRe = regexp.MustCompile(`^\d+-\d+-[0-9a-z]{8}$`)

func TestNewTokenFormat(t *testing.T) {
	now := time.UnixMilli(1721476800000)
	token := newToken(now, 48213)

	if !tokenRe.MatchString(token) {
		t.Fatalf("token %q does not match <millis>-<pid>-<8 base36 chars>", token)
	}
	if !strings.HasPrefix(token, "1721476800000-48213-") {
		t.Errorf("token %q must start with the timestamp and the pid", token)
	}
}

func TestNewTokenIsUniquePerCall(t *testing.T) {
	now := time.UnixMilli(1721476800000)
	seen := map[string]bool{}
	// The timestamp and the pid are fixed here on purpose, so only the random
	// suffix can tell the tokens apart. That is exactly the case that matters:
	// two keypresses inside the same millisecond must not collide.
	for i := 0; i < 500; i++ {
		token := newToken(now, 42)
		if seen[token] {
			t.Fatalf("token %q was produced twice", token)
		}
		seen[token] = true
	}
}

// ---------------------------------------------------------------------------
// readDebounce / writeDebounce (SPEC §7.1)
// ---------------------------------------------------------------------------

func TestReadDebounceBadInputGivesEmptyState(t *testing.T) {
	dir := t.TempDir()
	empty := debounceState{}

	cases := []struct {
		name  string
		setup func(path string)
	}{
		{"missing file", func(string) {}},
		{"broken JSON", func(path string) {
			mustWrite(t, path, `{"lastWrite": 1, "lastTarget":`)
		}},
		{"not an object at all", func(path string) {
			mustWrite(t, path, `["work"]`)
		}},
		{"empty file", func(path string) {
			mustWrite(t, path, "")
		}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			path := filepath.Join(dir, c.name+".json")
			c.setup(path)
			if got := readDebounce(path); got != empty {
				t.Errorf("readDebounce = %+v, want the neutral state", got)
			}
		})
	}
}

func TestReadDebounceNullFieldsBecomeEmpty(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state.json")
	// This is what the .mjs wrote after a successful switch.
	mustWrite(t, path, `{"lastWrite":1721476800000,"lastTarget":null,"token":null}`)

	got := readDebounce(path)
	want := debounceState{LastWrite: 1721476800000}
	if got != want {
		t.Errorf("readDebounce = %+v, want %+v", got, want)
	}
}

func TestReadDebounceNegativeLastWriteIsZeroed(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state.json")
	mustWrite(t, path, `{"lastWrite":-5,"lastTarget":"work","token":"t"}`)

	if got := readDebounce(path).LastWrite; got != 0 {
		t.Errorf("lastWrite = %d, want 0", got)
	}
}

func TestWriteDebounceRoundTrip(t *testing.T) {
	path := filepath.Join(t.TempDir(), "state.json")
	want := debounceState{LastWrite: 1721476800000, LastTarget: "my session", Token: "a-b-c"}

	if !writeDebounce(path, want) {
		t.Fatal("writeDebounce reported failure")
	}
	if got := readDebounce(path); got != want {
		t.Errorf("round trip = %+v, want %+v", got, want)
	}

	info, err := os.Stat(path)
	if err != nil {
		t.Fatalf("stat: %v", err)
	}
	if mode := info.Mode().Perm(); mode != debounceFileMode {
		t.Errorf("mode = %o, want %o (SPEC §7.1)", mode, debounceFileMode)
	}

	// The three field names are a wire format the .mjs also used. Renaming one
	// would silently break a mixed-version machine, so pin them.
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read: %v", err)
	}
	var fields map[string]json.RawMessage
	if err := json.Unmarshal(raw, &fields); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	for _, key := range []string{"lastWrite", "lastTarget", "token"} {
		if _, ok := fields[key]; !ok {
			t.Errorf("field %q is missing from %s", key, raw)
		}
	}
}

func TestWriteDebounceFailsOnAMissingDirectory(t *testing.T) {
	path := filepath.Join(t.TempDir(), "no-such-dir", "state.json")
	if writeDebounce(path, debounceState{LastTarget: "work"}) {
		t.Error("writeDebounce must report failure so the caller can fall back")
	}
}

// ---------------------------------------------------------------------------
// Paths and the debounce delay (SPEC §7.1, §7.3 step 2, Q6)
// ---------------------------------------------------------------------------

func TestDebouncePathShape(t *testing.T) {
	path := debouncePath()
	base := filepath.Base(path)
	if !strings.HasPrefix(base, "tmux-session-") || !strings.HasSuffix(base, ".json") {
		t.Errorf("debouncePath base = %q, want tmux-session-<id>.json", base)
	}
	if filepath.Dir(path) != os.TempDir() {
		t.Errorf("debouncePath dir = %q, want %q", filepath.Dir(path), os.TempDir())
	}
}

func TestDebounceDelay(t *testing.T) {
	cases := []struct {
		name  string
		value string
		set   bool
		want  time.Duration
	}{
		{"unset falls back to 300 ms", "", false, 300 * time.Millisecond},
		{"empty falls back to 300 ms", "", true, 300 * time.Millisecond},
		{"the value the tests use", "900", true, 900 * time.Millisecond},
		// Q6 FIX: the .mjs used `parseInt(x,10) || 300`, so 0 became 300 and
		// the debounce could never be turned off.
		{"an explicit 0 really means no delay", "0", true, 0},
		{"surrounding spaces are trimmed", "  450  ", true, 450 * time.Millisecond},
		{"nonsense falls back to 300 ms", "abc", true, 300 * time.Millisecond},
		{"a negative value falls back to 300 ms", "-5", true, 300 * time.Millisecond},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if c.set {
				t.Setenv("SESSION_SWITCH_DEBOUNCE_MS", c.value)
			} else {
				t.Setenv("SESSION_SWITCH_DEBOUNCE_MS", "")
			}
			if got := debounceDelay(); got != c.want {
				t.Errorf("debounceDelay = %v, want %v", got, c.want)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Log message 13 keeps its exact wording (SPEC §13.2)
// ---------------------------------------------------------------------------

func TestOrNullAndOrNone(t *testing.T) {
	if got := orNull(""); got != "null" {
		t.Errorf("orNull(\"\") = %q, want %q", got, "null")
	}
	if got := orNull("tok"); got != "tok" {
		t.Errorf("orNull(\"tok\") = %q", got)
	}
	if got := orNone(""); got != "(none)" {
		t.Errorf("orNone(\"\") = %q, want %q", got, "(none)")
	}
	if got := orNone("work"); got != "work" {
		t.Errorf("orNone(\"work\") = %q", got)
	}
}

func mustWrite(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0o600); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}
