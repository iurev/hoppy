package main

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"
)

// errTmuxDown is the shared "tmux is not reachable" error for the fake runner.
var errTmuxDown = errors.New("no server running on /tmp/tmux-0/default")

// ---------------------------------------------------------------------------
// score (SPEC §5.2)
// ---------------------------------------------------------------------------

func TestScoreBuckets(t *testing.T) {
	cases := []struct {
		name string
		age  float64 // hours
		want int
	}{
		{"just now", 0, 100},
		{"half an hour", 0.5, 100},
		{"in the future scores 100", -5, 100},
		// The boundaries are exclusive "<", so exactly 1 hour falls in the
		// 24-hour bucket, not the 1-hour one.
		{"exactly 1 hour falls to the 24h bucket", 1, 50},
		{"just under an hour", 0.999, 100},
		{"twelve hours", 12, 50},
		{"exactly 24 hours falls to the 7d bucket", 24, 10},
		{"three days", 72, 10},
		{"exactly 168 hours falls to the last bucket", 168, 1},
		{"a year", 8760, 1},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := score([]int64{hoursAgo(c.age)}, fixedNow)
			if got != c.want {
				t.Errorf("age %v h scored %d, want %d", c.age, got, c.want)
			}
		})
	}
}

func TestScoreSumsEveryTimestamp(t *testing.T) {
	sel := []int64{hoursAgo(0.5), hoursAgo(2), hoursAgo(100), hoursAgo(10000)}
	want := 100 + 50 + 10 + 1
	if got := score(sel, fixedNow); got != want {
		t.Errorf("score = %d, want %d", got, want)
	}
}

func TestScoreOfNothingIsZero(t *testing.T) {
	if got := score(nil, fixedNow); got != 0 {
		t.Errorf("score(nil) = %d, want 0", got)
	}
	if got := score([]int64{}, fixedNow); got != 0 {
		t.Errorf("score([]) = %d, want 0", got)
	}
}

// ---------------------------------------------------------------------------
// load / save (SPEC §0.3)
// ---------------------------------------------------------------------------

func TestLoadFrecencyOnAMissingDirectory(t *testing.T) {
	st := loadFrecency(t.TempDir())
	if st.Version != frecencyVersion {
		t.Errorf("version = %d, want %d", st.Version, frecencyVersion)
	}
	if len(st.Sessions) != 0 {
		t.Errorf("sessions = %#v, want empty", st.Sessions)
	}
	if got := score(st.selectedAt("anything"), fixedNow); got != 0 {
		t.Errorf("an unknown session scored %d, want 0", got)
	}
}

// A broken file must never crash the tool and must never poison the order
// (SPEC §0.3: "Missing dir / missing file / unreadable / bad JSON → treat as
// empty. Every score is 0. Never crash.").
func TestLoadFrecencyTreatsBrokenFilesAsEmpty(t *testing.T) {
	cases := []struct {
		name string
		body string
	}{
		{"not json at all", "this is not json"},
		{"truncated json", `{"version":1,"sessions":{"a":`},
		{"an array, not an object", `[1,2,3]`},
		{"a wrong version", `{"version":2,"sessions":{"a":{"selectedAt":[1]}}}`},
		{"version 0", `{"version":0,"sessions":{"a":{"selectedAt":[1]}}}`},
		{"no sessions key", `{"version":1}`},
		{"empty file", ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			dir := t.TempDir()
			writeFrecencyRaw(t, dir, c.body)
			st := loadFrecency(dir)
			if len(st.Sessions) != 0 {
				t.Errorf("got %#v, want empty state", st.Sessions)
			}
			if got := score(st.selectedAt("a"), fixedNow); got != 0 {
				t.Errorf("score = %d, want 0", got)
			}
		})
	}
}

func TestSaveThenLoadFrecencyRoundTrip(t *testing.T) {
	dir := t.TempDir()
	st := stateWith(map[string][]int64{
		"work":       {1721476800000, 1721480400000},
		"my session": {1721390000000},
	})
	if err := saveFrecency(dir, st); err != nil {
		t.Fatal(err)
	}
	got := loadFrecency(dir)
	if !reflect.DeepEqual(got, st) {
		t.Errorf("round trip gave %#v, want %#v", got, st)
	}
}

// SPEC §0.3: directory 0700, file 0600.
func TestSaveFrecencyModes(t *testing.T) {
	dir := t.TempDir()
	if err := saveFrecency(dir, stateWith(map[string][]int64{"a": {1}})); err != nil {
		t.Fatal(err)
	}

	fileInfo, err := os.Stat(frecencyPath(dir))
	if err != nil {
		t.Fatal(err)
	}
	if got := fileInfo.Mode().Perm(); got != frecencyFileMode {
		t.Errorf("file mode = %v, want %v", got, os.FileMode(frecencyFileMode))
	}

	dirInfo, err := os.Stat(filepath.Join(dir, frecencyDirName))
	if err != nil {
		t.Fatal(err)
	}
	if got := dirInfo.Mode().Perm(); got != frecencyDirMode {
		t.Errorf("dir mode = %v, want %v", got, os.FileMode(frecencyDirMode))
	}
}

// SPEC §0.55 / ARCHITECTURE §4: tests/conftest.py:37 deletes exactly
// <appDir>/.hoppy-frecency, so the path must not move.
func TestFrecencyPathLayout(t *testing.T) {
	if got := frecencyPath("/app"); got != "/app/.hoppy-frecency/sessions.json" {
		t.Errorf("frecencyPath(/app) = %q", got)
	}
}

// SPEC §0.3: no extra fields. `timesSelected` and friends are not written.
func TestSaveFrecencyWritesTheExactSchema(t *testing.T) {
	dir := t.TempDir()
	if err := saveFrecency(dir, stateWith(map[string][]int64{"a": {7}})); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(frecencyPath(dir))
	if err != nil {
		t.Fatal(err)
	}
	var generic map[string]any
	if err := json.Unmarshal(raw, &generic); err != nil {
		t.Fatal(err)
	}
	if len(generic) != 2 {
		t.Errorf("top level has %d keys (%v), want exactly version and sessions",
			len(generic), generic)
	}
	sessions, ok := generic["sessions"].(map[string]any)
	if !ok {
		t.Fatalf("sessions is not an object: %#v", generic["sessions"])
	}
	record, ok := sessions["a"].(map[string]any)
	if !ok {
		t.Fatalf("the record is not an object: %#v", sessions["a"])
	}
	if len(record) != 1 {
		t.Errorf("record = %v, want only selectedAt", record)
	}
}

// ---------------------------------------------------------------------------
// recordSelection (SPEC §0.3 cap, §5.3)
// ---------------------------------------------------------------------------

func TestRecordSelectionAppendsNewestLast(t *testing.T) {
	dir := t.TempDir()
	t0 := fixedNow
	recordSelection(dir, "work", t0)
	recordSelection(dir, "work", t0.Add(time.Minute))

	got := loadFrecency(dir).selectedAt("work")
	want := []int64{t0.UnixMilli(), t0.Add(time.Minute).UnixMilli()}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v (oldest first)", got, want)
	}
}

// SPEC §0.3: keep at most 10 timestamps; the 11th drops the oldest.
func TestRecordSelectionCapsAtTen(t *testing.T) {
	dir := t.TempDir()
	for i := 0; i < 15; i++ {
		recordSelection(dir, "work", fixedNow.Add(time.Duration(i)*time.Minute))
	}
	got := loadFrecency(dir).selectedAt("work")
	if len(got) != frecencyCap {
		t.Fatalf("kept %d timestamps, want %d", len(got), frecencyCap)
	}
	// The newest 10 are entries 5..14.
	for i := 0; i < frecencyCap; i++ {
		want := fixedNow.Add(time.Duration(i+5) * time.Minute).UnixMilli()
		if got[i] != want {
			t.Errorf("timestamp %d = %d, want %d", i, got[i], want)
		}
	}
}

func TestRecordSelectionExactlyAtTheCap(t *testing.T) {
	dir := t.TempDir()
	for i := 0; i < frecencyCap; i++ {
		recordSelection(dir, "work", fixedNow.Add(time.Duration(i)*time.Minute))
	}
	if got := len(loadFrecency(dir).selectedAt("work")); got != frecencyCap {
		t.Errorf("kept %d, want %d", got, frecencyCap)
	}
}

func TestRecordSelectionKeepsOtherSessions(t *testing.T) {
	dir := t.TempDir()
	recordSelection(dir, "a", fixedNow)
	recordSelection(dir, "b", fixedNow)
	st := loadFrecency(dir)
	if len(st.selectedAt("a")) != 1 || len(st.selectedAt("b")) != 1 {
		t.Errorf("state = %#v, want one timestamp each", st.Sessions)
	}
}

func TestRecordSelectionIgnoresAnEmptyName(t *testing.T) {
	dir := t.TempDir()
	recordSelection(dir, "", fixedNow)
	if _, err := os.Stat(frecencyPath(dir)); !os.IsNotExist(err) {
		t.Error("an empty name must not create the state file")
	}
}

// A broken file must not stop a new selection from being recorded.
func TestRecordSelectionRecoversFromABrokenFile(t *testing.T) {
	dir := t.TempDir()
	writeFrecencyRaw(t, dir, "}}} not json")
	recordSelection(dir, "work", fixedNow)
	if got := loadFrecency(dir).selectedAt("work"); len(got) != 1 {
		t.Errorf("got %#v, want one fresh timestamp", got)
	}
}

// The whole point of frecency: a session selected a minute ago must sort above
// one selected a year ago, end to end.
func TestRecordSelectionDrivesTheOrder(t *testing.T) {
	dir := t.TempDir()
	recordSelection(dir, "old", fixedNow.Add(-365*24*time.Hour))
	recordSelection(dir, "fresh", fixedNow.Add(-time.Minute))

	lines := []string{"old @ 1 windows", "fresh @ 1 windows"}
	got := orderByFrecency(lines, loadFrecency(dir), fixedNow)
	if got[0] != "fresh @ 1 windows" {
		t.Errorf("order = %#v, want the fresh session first", got)
	}
}

// writeFrecencyRaw drops raw bytes at the frecency path, creating the directory.
func writeFrecencyRaw(t *testing.T, appDir, body string) {
	t.Helper()
	path := frecencyPath(appDir)
	if err := os.MkdirAll(filepath.Dir(path), frecencyDirMode); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte(body), frecencyFileMode); err != nil {
		t.Fatal(err)
	}
}
