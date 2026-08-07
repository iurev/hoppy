package main

import (
	"reflect"
	"testing"
	"time"
)

// fixedNow is a stable "now" for every frecency test in this file.
var fixedNow = time.Date(2026, 8, 7, 12, 0, 0, 0, time.UTC)

// hoursAgo returns the epoch-millisecond timestamp h hours before fixedNow.
func hoursAgo(h float64) int64 {
	return fixedNow.Add(-time.Duration(h * float64(time.Hour))).UnixMilli()
}

// stateWith builds a frecencyState from name -> timestamps.
func stateWith(m map[string][]int64) frecencyState {
	st := frecencyState{Version: frecencyVersion, Sessions: map[string]frecencySession{}}
	for name, ts := range m {
		st.Sessions[name] = frecencySession{SelectedAt: ts}
	}
	return st
}

// ---------------------------------------------------------------------------
// orderByFrecency (SPEC §4.1 step 6)
// ---------------------------------------------------------------------------

func TestOrderByFrecencySortsDescending(t *testing.T) {
	lines := []string{
		"cold @ 1 windows",
		"warm @ 2 windows",
		"hot @ 3 windows",
	}
	st := stateWith(map[string][]int64{
		"cold": {hoursAgo(1000)}, // 1
		"warm": {hoursAgo(10)},   // 50
		"hot":  {hoursAgo(0.5)},  // 100
	})

	got := orderByFrecency(lines, st, fixedNow)
	want := []string{"hot @ 3 windows", "warm @ 2 windows", "cold @ 1 windows"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

// ARCHITECTURE §6 rule 9 / SPEC §4.1 step 6: sort.SliceStable, never sort.Slice.
// On a fresh checkout every score is 0, so an unstable sort would shuffle the
// whole list and every [1]..[9] shortcut would move between runs.
func TestOrderByFrecencyIsStableForTies(t *testing.T) {
	lines := []string{
		"a @ 1 windows", "b @ 1 windows", "c @ 1 windows",
		"d @ 1 windows", "e @ 1 windows", "f @ 1 windows",
		"g @ 1 windows", "h @ 1 windows", "i @ 1 windows",
		"j @ 1 windows", "k @ 1 windows", "l @ 1 windows",
		"m @ 1 windows", "n @ 1 windows", "o @ 1 windows",
	}
	// Empty state: every score is 0, so every pair is a tie.
	got := orderByFrecency(lines, frecencyState{}, fixedNow)
	if !reflect.DeepEqual(got, lines) {
		t.Errorf("ties changed order:\n got %#v\nwant %#v", got, lines)
	}
}

func TestOrderByFrecencyKeepsTmuxOrderWithinOneScore(t *testing.T) {
	lines := []string{
		"zebra @ 1 windows", // score 100
		"apple @ 1 windows", // score 0
		"mango @ 1 windows", // score 100
	}
	st := stateWith(map[string][]int64{
		"zebra": {hoursAgo(0.1)},
		"mango": {hoursAgo(0.1)},
	})
	got := orderByFrecency(lines, st, fixedNow)
	want := []string{"zebra @ 1 windows", "mango @ 1 windows", "apple @ 1 windows"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

func TestOrderByFrecencyDoesNotMutateItsInput(t *testing.T) {
	lines := []string{"a @ 1 windows", "b @ 1 windows"}
	st := stateWith(map[string][]int64{"b": {hoursAgo(0.1)}})
	_ = orderByFrecency(lines, st, fixedNow)
	if lines[0] != "a @ 1 windows" {
		t.Errorf("the input slice was reordered: %#v", lines)
	}
}

// ---------------------------------------------------------------------------
// selectorItems (SPEC §4.2, §4.3, D3)
// ---------------------------------------------------------------------------

func TestSelectorItemsPinsTheCurrentSession(t *testing.T) {
	lines := []string{
		"alpha @ 1 windows",
		"work @ 3 windows",
		"beta @ 2 windows",
	}
	got := selectorItems(lines, "work")
	want := []string{
		"[1] work @ 3 windows",
		"[2] alpha @ 1 windows",
		"[3] beta @ 2 windows",
		"[cancel]",
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

// D3: the current session STAYS in the list and is always [1].
func TestSelectorItemsKeepsTheCurrentSessionD3(t *testing.T) {
	lines := []string{"work @ 3 windows", "other @ 1 windows"}
	got := selectorItems(lines, "work")
	if got[0] != "[1] work @ 3 windows" {
		t.Errorf("current session must stay pinned at [1], got %q", got[0])
	}
	if len(got) != 3 {
		t.Errorf("the current session was dropped: %#v", got)
	}
}

// The pin is a "<name> @ " PREFIX match, so a session whose name merely starts
// with the current name must not be pinned by accident.
func TestSelectorItemsPinNeedsTheFullPrefix(t *testing.T) {
	lines := []string{"workspace @ 1 windows", "work @ 3 windows"}
	got := selectorItems(lines, "work")
	if got[0] != "[1] work @ 3 windows" {
		t.Errorf("pinned the wrong row: %q", got[0])
	}
}

// SPEC §4.2 row 2: no "[current]" row is ever added here.
func TestSelectorItemsNoMatchingCurrentRow(t *testing.T) {
	lines := []string{"a @ 1 windows", "b @ 2 windows"}
	got := selectorItems(lines, "gone")
	want := []string{"[1] a @ 1 windows", "[2] b @ 2 windows", "[cancel]"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

func TestSelectorItemsWithoutACurrentSession(t *testing.T) {
	lines := []string{"a @ 1 windows"}
	got := selectorItems(lines, "")
	want := []string{"[1] a @ 1 windows", "[cancel]"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

func TestSelectorItemsOnAnEmptyList(t *testing.T) {
	got := selectorItems([]string{}, "work")
	want := []string{"[cancel]"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

// Q7 FIX: `reload-sessions` and the initial `switch` list must produce the SAME
// rows. Both go through selectorItems, so this pins the contract.
func TestSelectorItemsIsTheSharedShapeForReload(t *testing.T) {
	lines := []string{"b @ 1 windows", "work @ 2 windows"}
	initial := selectorItems(lines, "work")
	reload := selectorItems(lines, "work")
	if !reflect.DeepEqual(initial, reload) {
		t.Errorf("switch and reload disagree:\n %#v\n %#v", initial, reload)
	}
	if initial[len(initial)-1] != "[cancel]" {
		t.Error("the reloaded list must still end with [cancel] (Q7 FIX)")
	}
	if initial[0] != "[1] work @ 2 windows" {
		t.Error("the reloaded list must still pin the current session (Q7 FIX)")
	}
}

// ---------------------------------------------------------------------------
// pinCurrentRow — the `detach` list (SPEC §3.14.1, Q12 FIX)
// ---------------------------------------------------------------------------

func TestPinCurrentRowPrefersTheRealRow(t *testing.T) {
	lines := []string{"a @ 1 windows", "work @ 3 windows"}
	got := pinCurrentRow(lines, "work")
	want := []string{"work @ 3 windows", "a @ 1 windows"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

// Only when the current session has no row of its own does the literal
// "[current]" row appear. It carries no number and no "[cancel]".
func TestPinCurrentRowFallsBackToTheLiteralRow(t *testing.T) {
	lines := []string{"a @ 1 windows"}
	got := pinCurrentRow(lines, "gone")
	want := []string{"[current]", "a @ 1 windows"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

// ---------------------------------------------------------------------------
// filterCapital (SPEC §3.10 step 2)
// ---------------------------------------------------------------------------

func TestFilterCapital(t *testing.T) {
	lines := []string{
		"WORK @ 1 windows",
		"work @ 1 windows",
		"MY PROJECT @ 2 windows",
		"WORK_2 @ 1 windows",
		"WORK-B @ 1 windows",
		"123 @ 1 windows", // digits only: no A-Z, so it is dropped
		"Mixed @ 1 windows",
		"ADC @ 3 windows",
	}
	got := filterCapital(lines)
	want := []string{
		"WORK @ 1 windows",
		"MY PROJECT @ 2 windows",
		"WORK_2 @ 1 windows",
		"WORK-B @ 1 windows",
		"ADC @ 3 windows",
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

func TestFilterCapitalOnAnEmptyList(t *testing.T) {
	if got := filterCapital([]string{}); len(got) != 0 {
		t.Errorf("got %#v, want empty", got)
	}
}

// ---------------------------------------------------------------------------
// filterByWorktrees (SPEC §6.3)
// ---------------------------------------------------------------------------

func TestFilterByWorktrees(t *testing.T) {
	lines := []string{
		"inside @ 1 windows",
		"outside @ 1 windows",
		"nopanes @ 1 windows",
		"deep @ 1 windows",
	}
	worktrees := []string{"/repo", "/repo-feature/"} // note the trailing slash
	panePaths := map[string][]string{
		"inside":  {"/repo"},
		"outside": {"/somewhere/else"},
		"deep":    {"/repo-feature/src/pkg"},
	}
	got := filterByWorktrees(lines, worktrees, panePaths)
	want := []string{"inside @ 1 windows", "deep @ 1 windows"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

// The "/" in `wt + "/"` matters: a sibling directory that merely shares a name
// prefix is NOT inside the worktree.
func TestFilterByWorktreesRejectsASiblingPrefix(t *testing.T) {
	lines := []string{"sibling @ 1 windows"}
	panePaths := map[string][]string{"sibling": {"/repo-backup/src"}}
	got := filterByWorktrees(lines, []string{"/repo"}, panePaths)
	if len(got) != 0 {
		t.Errorf("/repo-backup must not count as inside /repo, got %#v", got)
	}
}

func TestFilterByWorktreesStripsEveryTrailingSlash(t *testing.T) {
	lines := []string{"s @ 1 windows"}
	panePaths := map[string][]string{"s": {"/repo/sub"}}
	got := filterByWorktrees(lines, []string{"/repo///"}, panePaths)
	if len(got) != 1 {
		t.Errorf("trailing slashes must be stripped, got %#v", got)
	}
}

func TestFilterByWorktreesDropsSessionsWithNoPanes(t *testing.T) {
	lines := []string{"ghost @ 1 windows"}
	got := filterByWorktrees(lines, []string{"/repo"}, map[string][]string{})
	if len(got) != 0 {
		t.Errorf("a session with no panes must be dropped, got %#v", got)
	}
}

// ---------------------------------------------------------------------------
// getSessionsList (SPEC §4.1) — through the tmux fake
// ---------------------------------------------------------------------------

func TestGetSessionsListNormalisesAndOrders(t *testing.T) {
	installFake(t, staticReply("cold  @  1 windows\nhot @ 2 windows\n\n"))
	st := stateWith(map[string][]int64{"hot": {hoursAgo(0.1)}})

	got, err := getSessionsList("cold", st, fixedNow)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"hot @ 2 windows", "cold @ 1 windows"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

func TestGetSessionsListPropagatesTheTmuxError(t *testing.T) {
	installFake(t, func([]string) (string, error) {
		return "", errTmuxDown
	})
	if _, err := getSessionsList("", frecencyState{}, fixedNow); err == nil {
		t.Error("want the tmux failure to reach the caller")
	}
}

// D3 again, at the list level: getSessionsList has no excludeCurrent parameter
// and never drops the current session.
func TestGetSessionsListKeepsTheCurrentSession(t *testing.T) {
	installFake(t, staticReply("work @ 3 windows\nother @ 1 windows\n"))
	got, err := getSessionsList("work", frecencyState{}, fixedNow)
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 {
		t.Fatalf("got %#v, want both sessions", got)
	}
}
