// main_test.go — the action handlers added last: the three fzf helper actions
// and the four mutation actions (SPEC §3.4-§3.6, §3.8, §3.12-§3.14).
//
// Every test drives the two seams (`run` and `runFzfCmd`) with fakes, so no
// tmux server, no fzf and no processes are involved.
package main

import (
	"errors"
	"os"
	"reflect"
	"strings"
	"testing"
	"time"
)

// ---------------------------------------------------------------------------
// kill order — quirk Q14, marked KEEP (SPEC §3.13 step 4)
// ---------------------------------------------------------------------------

func TestReverseSorted(t *testing.T) {
	cases := []struct {
		name string
		in   []string
		want []string
	}{
		{"plain names", []string{"kill_a", "kill_b"}, []string{"kill_b", "kill_a"}},
		{"already descending", []string{"c", "b", "a"}, []string{"c", "b", "a"}},
		{"digits sort before letters", []string{"a", "1", "Z"}, []string{"a", "Z", "1"}},
		{"one item", []string{"only"}, []string{"only"}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := reverseSorted(c.in); !reflect.DeepEqual(got, c.want) {
				t.Errorf("reverseSorted(%v) = %v, want %v", c.in, got, c.want)
			}
		})
	}
}

func TestReverseSortedOfNothing(t *testing.T) {
	if got := reverseSorted(nil); len(got) != 0 {
		t.Errorf("reverseSorted(nil) = %v, want no items", got)
	}
}

func TestReverseSortedDoesNotTouchTheInput(t *testing.T) {
	in := []string{"b", "a", "c"}
	_ = reverseSorted(in)
	if !reflect.DeepEqual(in, []string{"b", "a", "c"}) {
		t.Errorf("the input was reordered: %v", in)
	}
}

// ---------------------------------------------------------------------------
// kill-single-from-line (SPEC §3.4) — the DEL key
// ---------------------------------------------------------------------------

func TestActionKillSingleFromLine(t *testing.T) {
	cases := []struct {
		name string
		line string
		want []string // the argv we expect, or nil for "no call at all"
	}{
		{
			"a numbered row",
			"[2] kill_me @ 1 windows",
			[]string{"tmux", "kill-session", "-t", "kill_me"},
		},
		{
			"a name with spaces stays one argv element",
			"[1] my session @ 2 windows",
			[]string{"tmux", "kill-session", "-t", "my session"},
		},
		{
			// SPEC §3.4 is explicit: no name validation and no [cancel] guard.
			// tmux simply fails, and we swallow that.
			"[cancel] is passed straight through",
			"[cancel]",
			[]string{"tmux", "kill-session", "-t", "[cancel]"},
		},
		{"an empty line kills nothing", "", nil},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			f := installFake(t, nil)
			if code := actionKillSingleFromLine(c.line); code != 0 {
				t.Errorf("exit code = %d, want 0: fzf reload only runs after a 0", code)
			}
			if c.want == nil {
				if len(f.calls) != 0 {
					t.Errorf("want no tmux call, got %#v", f.calls)
				}
				return
			}
			if got := f.only(t); !reflect.DeepEqual(got, c.want) {
				t.Errorf("argv = %#v, want %#v", got, c.want)
			}
		})
	}
}

func TestActionKillSingleFromLineSwallowsAFailure(t *testing.T) {
	installFake(t, func([]string) (string, error) { return "", errTmuxDown })
	// A non-zero code here would stop fzf's reload() and freeze the list.
	if code := actionKillSingleFromLine("[1] gone @ 1 windows"); code != 0 {
		t.Errorf("exit code = %d, want 0", code)
	}
}

// ---------------------------------------------------------------------------
// switch-from-line (SPEC §3.5) — Ctrl+N / Ctrl+P
// ---------------------------------------------------------------------------

func TestActionSwitchFromLineIgnoresNothingToDo(t *testing.T) {
	for _, line := range []string{"", "[cancel]", "[3] [cancel]"} {
		t.Run("line="+line, func(t *testing.T) {
			f := installFake(t, nil)
			if code := actionSwitchFromLine(line); code != 0 {
				t.Errorf("exit code = %d, want 0", code)
			}
			// Nothing is scheduled, so no tmux call and no state file write.
			if len(f.calls) != 0 {
				t.Errorf("want no tmux call, got %#v", f.calls)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// delayed-switch (SPEC §3.6)
// ---------------------------------------------------------------------------

func TestActionDelayedSwitchWithoutATokenDoesNothing(t *testing.T) {
	f := installFake(t, nil)
	if code := actionDelayedSwitch(""); code != 0 {
		t.Errorf("exit code = %d, want 0", code)
	}
	if len(f.calls) != 0 {
		t.Errorf("want no tmux call, got %#v", f.calls)
	}
}

// ---------------------------------------------------------------------------
// detach (SPEC §3.14, §3.14.1 and the Q3 fix)
// ---------------------------------------------------------------------------

func TestActionDetachListShape(t *testing.T) {
	installFake(t, func(argv []string) (string, error) {
		switch {
		case len(argv) >= 4 && argv[1] == "list-sessions" && argv[3] == sessionListFormat:
			return "work @ 3 windows\nidle @ 1 windows\n", nil
		case len(argv) >= 4 && argv[1] == "list-sessions" && argv[3] == attachedFormat:
			// The Q3 fix: tmux answers with the real attached flag.
			return "work\t1\nidle\t0\n", nil
		}
		return "", nil
	})
	// Escape: the list shape is what this test is about.
	fzf := installFakeFzf(t, &fakeFzf{code: fzfExitInterrupt})

	if code := actionDetach("work"); code != 0 {
		t.Fatalf("exit code = %d, want 0", code)
	}

	got := strings.Split(strings.TrimRight(fzf.stdin, "\n"), "\n")
	want := []string{"[current]", "work @ 3 windows", "[cancel]"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("items = %#v, want %#v", got, want)
	}
	// SPEC §3.14 step 1: no number prefixes in this list.
	for _, item := range got {
		if strings.HasPrefix(item, "[1] ") || strings.HasPrefix(item, "[2] ") {
			t.Errorf("item %q carries a number prefix", item)
		}
	}
}

func TestActionDetachKeepsTheCurrentRowWhenNothingIsAttached(t *testing.T) {
	// SPEC §3.14.1: dropping "[current]" would leave an empty list, fzf would
	// exit 1, and detach would silently do nothing.
	installFake(t, func(argv []string) (string, error) {
		if len(argv) >= 4 && argv[1] == "list-sessions" && argv[3] == attachedFormat {
			return "work\t0\n", nil
		}
		return "work @ 3 windows\n", nil
	})
	fzf := installFakeFzf(t, &fakeFzf{code: fzfExitInterrupt})

	if code := actionDetach("work"); code != 0 {
		t.Fatalf("exit code = %d, want 0", code)
	}
	if !strings.Contains(fzf.stdin, "[current]") {
		t.Errorf("items = %q, want the [current] row", fzf.stdin)
	}
}

func TestActionDetachRunsDetachPerTarget(t *testing.T) {
	f := installFake(t, func(argv []string) (string, error) {
		switch {
		case len(argv) >= 4 && argv[1] == "list-sessions" && argv[3] == attachedFormat:
			return "work\t1\nother\t1\n", nil
		case len(argv) >= 2 && argv[1] == "list-sessions":
			return "work @ 3 windows\nother @ 1 windows\n", nil
		}
		return "", nil
	})
	installFakeFzf(t, &fakeFzf{
		stdout: "other @ 1 windows\nwork @ 3 windows\n",
		code:   fzfExitOk,
	})

	if code := actionDetach("work"); code != 0 {
		t.Fatalf("exit code = %d, want 0", code)
	}

	var detached [][]string
	for _, call := range f.calls {
		if len(call) >= 2 && call[1] == "detach" {
			detached = append(detached, call)
		}
	}
	want := [][]string{
		{"tmux", "detach", "-s", "other"},
		{"tmux", "detach", "-s", "work"},
	}
	if !reflect.DeepEqual(detached, want) {
		t.Errorf("detach calls = %#v, want %#v (selection order)", detached, want)
	}
}

// ---------------------------------------------------------------------------
// kill (SPEC §3.13) and the Q12 fix
// ---------------------------------------------------------------------------

func TestActionKillUsesTheSameRowsAsSwitch(t *testing.T) {
	installFake(t, staticReply("keep @ 1 windows\nwork @ 3 windows\n"))
	fzf := installFakeFzf(t, &fakeFzf{code: fzfExitInterrupt})

	if code := actionKill("work"); code != 0 {
		t.Fatalf("exit code = %d, want 0", code)
	}

	got := strings.Split(strings.TrimRight(fzf.stdin, "\n"), "\n")
	// Q12 FIX: the current session is pinned and numbered, and there is NO
	// literal "[current]" row next to it any more.
	want := []string{"[1] work @ 3 windows", "[2] keep @ 1 windows", "[cancel]"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("items = %#v, want %#v", got, want)
	}
}

func TestActionKillDeletesInReverseOrder(t *testing.T) {
	f := installFake(t, staticReply("kill_a @ 1 windows\nkill_b @ 1 windows\nwork @ 3 windows\n"))
	installFakeFzf(t, &fakeFzf{
		stdout: "[2] kill_a @ 1 windows\n[3] kill_b @ 1 windows\n",
		code:   fzfExitOk,
	})

	if code := actionKill("work"); code != 0 {
		t.Fatalf("exit code = %d, want 0", code)
	}

	var killed []string
	for _, call := range f.calls {
		if len(call) >= 4 && call[1] == "kill-session" {
			killed = append(killed, call[3])
		}
	}
	if want := []string{"kill_b", "kill_a"}; !reflect.DeepEqual(killed, want) {
		t.Errorf("killed %v, want %v (Q14: reverse lexicographic)", killed, want)
	}
}

func TestActionKillRejectsABadTargetBeforeKillingAnything(t *testing.T) {
	f := installFake(t, staticReply("good @ 1 windows\nwork @ 3 windows\n"))
	installFakeFzf(t, &fakeFzf{
		stdout: "[2] good @ 1 windows\n[3] bad:name @ 1 windows\n",
		code:   fzfExitOk,
	})

	if code := actionKill("work"); code != 1 {
		t.Fatalf("exit code = %d, want 1", code)
	}
	for _, call := range f.calls {
		if len(call) >= 2 && call[1] == "kill-session" {
			t.Errorf("nothing may be killed when one target is invalid: %#v", call)
		}
	}
}

func TestActionKillCancelRow(t *testing.T) {
	f := installFake(t, staticReply("work @ 3 windows\n"))
	installFakeFzf(t, &fakeFzf{stdout: "[cancel]\n", code: fzfExitOk})

	if code := actionKill("work"); code != 0 {
		t.Fatalf("exit code = %d, want 0", code)
	}
	for _, call := range f.calls {
		if len(call) >= 2 && call[1] == "kill-session" {
			t.Errorf("[cancel] must kill nothing, got %#v", call)
		}
	}
}

// ---------------------------------------------------------------------------
// rename (SPEC §3.12) and the Q12 fix
// ---------------------------------------------------------------------------

// TestActionRenameEndToEnd drives the real FIFO exactly the way
// tests/helpers/workflow.py:32 does: it only OPENS the path for writing. The
// binary must have created it first, and it must kill the prompt pane before
// the selector is drawn.
func TestActionRenameEndToEnd(t *testing.T) {
	f := installFake(t, func(argv []string) (string, error) {
		switch {
		case len(argv) >= 2 && argv[1] == "display-message":
			return "%0\n", nil
		case len(argv) >= 2 && argv[1] == "split-window":
			return "%7\n", nil // the id of the new prompt pane
		case len(argv) >= 2 && argv[1] == "list-sessions":
			return "old_name @ 1 windows\nwork @ 3 windows\n", nil
		}
		return "", nil
	})
	installFakeFzf(t, &fakeFzf{stdout: "[2] old_name @ 1 windows\n", code: fzfExitOk})

	prepareFifo()
	defer func() { fifoReady = false }()
	writeFifoLine(t, fifoPath, "new_name")

	if code := actionRename("work"); code != 0 {
		t.Fatalf("exit code = %d, want 0", code)
	}

	var order []string
	for _, call := range f.calls {
		if len(call) >= 2 {
			order = append(order, call[1])
		}
	}
	// SPEC §9.2.1 step 7: the prompt pane must die BEFORE the selector runs,
	// or it would eat every keystroke meant for fzf.
	killAt, listAt := indexOf(order, "kill-pane"), indexOf(order, "list-sessions")
	if killAt < 0 {
		t.Fatalf("no kill-pane call: %v", order)
	}
	if listAt >= 0 && killAt > listAt {
		t.Errorf("kill-pane came after list-sessions: %v", order)
	}

	want := []string{"tmux", "rename-session", "-t", "old_name", "new_name"}
	found := false
	for _, call := range f.calls {
		if len(call) >= 2 && call[1] == "rename-session" {
			found = true
			if !reflect.DeepEqual(call, want) {
				t.Errorf("argv = %#v, want %#v", call, want)
			}
		}
	}
	if !found {
		t.Errorf("no rename-session call: %v", order)
	}
}

func TestActionRenameCancelledSelection(t *testing.T) {
	f := installFake(t, func(argv []string) (string, error) {
		if len(argv) >= 2 && argv[1] == "list-sessions" {
			return "work @ 3 windows\n", nil
		}
		return "", nil
	})
	installFakeFzf(t, &fakeFzf{stdout: "[cancel]\n", code: fzfExitOk})

	prepareFifo()
	defer func() { fifoReady = false }()
	writeFifoLine(t, fifoPath, "new_name")

	if code := actionRename("work"); code != 0 {
		t.Fatalf("exit code = %d, want 0", code)
	}
	for _, call := range f.calls {
		if len(call) >= 2 && call[1] == "rename-session" {
			t.Errorf("[cancel] must rename nothing, got %#v", call)
		}
	}
}

// TestActionNewEndToEnd is the same shape for `new` (SPEC §3.8).
func TestActionNewEndToEnd(t *testing.T) {
	f := installFake(t, func(argv []string) (string, error) {
		if len(argv) >= 2 && argv[1] == "split-window" {
			return "%7\n", nil
		}
		return "", nil
	})

	prepareFifo()
	defer func() { fifoReady = false }()
	writeFifoLine(t, fifoPath, "fresh_session")

	if code := actionNew(); code != 0 {
		t.Fatalf("exit code = %d, want 0", code)
	}

	var interesting [][]string
	for _, call := range f.calls {
		if len(call) >= 2 && (call[1] == "new-session" || call[1] == "switch-client") {
			interesting = append(interesting, call)
		}
	}
	want := [][]string{
		{"tmux", "new-session", "-d", "-s", "fresh_session"},
		{"tmux", "switch-client", "-t", "fresh_session"},
	}
	if !reflect.DeepEqual(interesting, want) {
		t.Errorf("calls = %#v, want %#v", interesting, want)
	}
}

// writeFifoLine opens the FIFO for writing in the background and sends one
// line, then closes. Opening blocks until the reader arrives, which is exactly
// what the Python helper does.
func writeFifoLine(t *testing.T, path, line string) {
	t.Helper()
	done := make(chan struct{})
	go func() {
		defer close(done)
		f, err := os.OpenFile(path, os.O_WRONLY, 0)
		if err != nil {
			return
		}
		_, _ = f.WriteString(line + "\n")
		_ = f.Close()
	}()
	t.Cleanup(func() {
		select {
		case <-done:
		case <-time.After(5 * time.Second):
			t.Error("the FIFO writer never finished; nobody opened the read end")
		}
	})
}

// ---------------------------------------------------------------------------
// kill-single (SPEC §3.7, M9)
// ---------------------------------------------------------------------------

func TestActionKillSingleNeedsAName(t *testing.T) {
	installFake(t, nil)
	if code := actionKillSingle(""); code != 1 {
		t.Errorf("exit code = %d, want 1", code)
	}
}

func TestActionKillSingleRejectsABadName(t *testing.T) {
	f := installFake(t, nil)
	if code := actionKillSingle("bad:name"); code != 1 {
		t.Errorf("exit code = %d, want 1", code)
	}
	if len(f.calls) != 0 {
		t.Errorf("a bad name must not reach tmux: %#v", f.calls)
	}
}

func TestActionKillSingleMissingSession(t *testing.T) {
	f := installFake(t, func(argv []string) (string, error) {
		if len(argv) >= 2 && argv[1] == "has-session" {
			return "", errors.New("can't find session")
		}
		return "", nil
	})
	if code := actionKillSingle("ghost"); code != 1 {
		t.Errorf("exit code = %d, want 1", code)
	}
	last := f.calls[len(f.calls)-1]
	want := []string{"tmux", "display-message", "Session ghost does not exist"}
	if !reflect.DeepEqual(last, want) {
		t.Errorf("last call = %#v, want %#v", last, want)
	}
}
