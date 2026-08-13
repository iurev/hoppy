package main

import (
	"errors"
	"os/exec"
	"reflect"
	"strings"
	"testing"
)

// ---------------------------------------------------------------------------
// The fake runner. Every test in the package can use it: it records the exact
// argv of each call and replies with canned output. No tmux, no git, no fzf.
// ---------------------------------------------------------------------------

type fakeRun struct {
	calls [][]string
	reply func(argv []string) (string, error)
}

// installFake swaps the package-level `run` for the duration of one test.
func installFake(t *testing.T, reply func(argv []string) (string, error)) *fakeRun {
	t.Helper()
	f := &fakeRun{reply: reply}
	old := run
	run = func(argv ...string) (string, error) {
		call := append([]string(nil), argv...)
		f.calls = append(f.calls, call)
		if f.reply != nil {
			return f.reply(call)
		}
		return "", nil
	}
	t.Cleanup(func() { run = old })
	return f
}

// only returns the single call the test expects, and fails otherwise.
func (f *fakeRun) only(t *testing.T) []string {
	t.Helper()
	if len(f.calls) != 1 {
		t.Fatalf("got %d calls, want exactly 1: %#v", len(f.calls), f.calls)
	}
	return f.calls[0]
}

// staticReply always answers with the same output.
func staticReply(out string) func([]string) (string, error) {
	return func([]string) (string, error) { return out, nil }
}

// ---------------------------------------------------------------------------
// SPEC §0.9.1 — one argv test per row.
//
// This table IS the safety net. SPEC §0.9.2 is explicit: if a shell quote is
// copied into an argv element, the integration tests STILL PASS and the bug
// only surfaces later as wrong ordering. Nothing else catches it.
// ---------------------------------------------------------------------------

func TestSpec091ArgvTable(t *testing.T) {
	cases := []struct {
		row  int
		name string
		call func()
		want []string
	}{
		{
			row:  1,
			name: "list-sessions with the session format",
			call: func() { _, _ = tmuxListSessions() },
			want: []string{"tmux", "list-sessions", "-F", "#S @ #{session_windows} windows"},
		},
		{
			row:  2,
			name: "list-panes with the tab format",
			call: func() { _, _ = tmuxListPanePaths() },
			want: []string{"tmux", "list-panes", "-a", "-F", "#{session_name}\t#{pane_current_path}"},
		},
		{
			row:  3,
			name: "display-message -p #S",
			call: func() { _, _ = tmuxCurrentSession() },
			want: []string{"tmux", "display-message", "-p", "#S"},
		},
		{
			row:  4,
			name: "display-message -p pane_current_path",
			call: func() { _, _ = tmuxPaneCurrentPath() },
			want: []string{"tmux", "display-message", "-p", "#{pane_current_path}"},
		},
		{
			row:  5,
			name: "the missing-session message is ONE argv element",
			call: func() { _ = tmuxDisplayMessage(tmuxSessionMissingMessage("my session")) },
			want: []string{"tmux", "display-message", "Session my session does not exist"},
		},
		{
			row:  6,
			name: "not in a git repository",
			call: func() { _ = tmuxDisplayMessage(msgNotInGitRepo) },
			want: []string{"tmux", "display-message", "Not in a git repository"},
		},
		{
			row:  7,
			name: "no worktree sessions, apostrophe is plain text",
			call: func() { _ = tmuxDisplayMessage(msgNoWorktreeSess) },
			want: []string{"tmux", "display-message", "No sessions found for this project's worktrees"},
		},
		{
			row:  8,
			name: "no CAPITAL sessions",
			call: func() { _ = tmuxDisplayMessage(msgNoCapitalSess) },
			want: []string{"tmux", "display-message", "No CAPITAL sessions found"},
		},
		{
			row:  9,
			name: "display-popup is 17 elements and SESSIONS has no quotes",
			call: func() { _ = tmuxDisplayPopup("SESSIONS", "/app/hoppy", "switch") },
			want: []string{
				"tmux", "display-popup", "-E",
				"-w", "60%", "-h", "90%",
				"-x", "R", "-y", "C",
				"-T", "SESSIONS", "-b", "rounded",
				"/app/hoppy", "switch",
			},
		},
		{
			row:  10,
			name: "kill-session keeps a spaced name as one element",
			call: func() { _ = tmuxKillSession("my session") },
			want: []string{"tmux", "kill-session", "-t", "my session"},
		},
		{
			row:  11,
			name: "rename-session takes old then new",
			call: func() { _ = tmuxRenameSession("old name", "new name") },
			want: []string{"tmux", "rename-session", "-t", "old name", "new name"},
		},
		{
			row:  12,
			name: "git worktree list --porcelain",
			call: func() { _ = gitWorktrees("/home/yu/my project") },
			want: []string{"git", "-C", "/home/yu/my project", "worktree", "list", "--porcelain"},
		},
	}

	if len(cases) != 12 {
		t.Fatalf("SPEC §0.9.1 has 12 rows, the table has %d", len(cases))
	}

	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			f := installFake(t, nil)
			c.call()
			got := f.only(t)
			if !reflect.DeepEqual(got, c.want) {
				t.Errorf("§0.9.1 row %d argv =\n  %#v\nwant\n  %#v", c.row, got, c.want)
			}
			assertNoShellQuotes(t, got)
		})
	}
}

// assertNoShellQuotes is the §0.9.2 guard. A copied shell quote always shows up
// as an argv element wrapped in ' or ".
func assertNoShellQuotes(t *testing.T, argv []string) {
	t.Helper()
	for i, a := range argv {
		if len(a) >= 2 {
			if (strings.HasPrefix(a, "'") && strings.HasSuffix(a, "'")) ||
				(strings.HasPrefix(a, `"`) && strings.HasSuffix(a, `"`)) {
				t.Errorf("argv[%d] = %q is wrapped in shell quotes (SPEC §0.9.2)", i, a)
			}
		}
	}
}

// The two format strings are the exact place where the quote bug bites.
func TestFormatConstantsCarryNoQuotes(t *testing.T) {
	for _, f := range []string{sessionListFormat, panePathFormat, attachedFormat} {
		if strings.ContainsAny(f, `'"`) {
			t.Errorf("format %q contains a quote character", f)
		}
	}
	if sessionListFormat != "#S @ #{session_windows} windows" {
		t.Errorf("sessionListFormat = %q", sessionListFormat)
	}
	// SPEC §0.9.1 note on row 2: tmux must receive a REAL tab (U+0009),
	// not a backslash followed by "t".
	tab := string(rune(0x09))
	if !strings.Contains(panePathFormat, tab) {
		t.Error("panePathFormat must hold a real TAB character")
	}
	if strings.Contains(panePathFormat, `\t`) {
		t.Error("panePathFormat holds a literal backslash-t, not a TAB")
	}
	if !strings.Contains(attachedFormat, tab) {
		t.Error("attachedFormat must hold a real TAB character")
	}
}

// ---------------------------------------------------------------------------
// The remaining commands. Not in §0.9.1, but the argv still has to be right.
// ---------------------------------------------------------------------------

func TestOtherCommandArgv(t *testing.T) {
	cases := []struct {
		name string
		call func()
		want []string
	}{
		{
			"switch-client",
			func() { _ = tmuxSwitchClient("my session") },
			[]string{"tmux", "switch-client", "-t", "my session"},
		},
		{
			"new-session detached",
			func() { _ = tmuxNewSessionDetached("fresh_session") },
			[]string{"tmux", "new-session", "-d", "-s", "fresh_session"},
		},
		{
			"detach keeps the session alive",
			func() { _ = tmuxDetachClient("test_session") },
			[]string{"tmux", "detach", "-s", "test_session"},
		},
		{
			"has-session",
			func() { _ = tmuxHasSession("work") },
			[]string{"tmux", "has-session", "-t", "work"},
		},
		{
			"pane id, recorded before the split",
			func() { _, _ = tmuxCurrentPaneID() },
			[]string{"tmux", "display-message", "-p", "#{pane_id}"},
		},
		{
			"kill-pane",
			func() { _ = tmuxKillPane("%3") },
			[]string{"tmux", "kill-pane", "-t", "%3"},
		},
		{
			// SPEC §9.2 / §9.2.1 step 3: the script is ONE argv element.
			// -P -F prints the id of the NEW pane, which step 7 must kill.
			"split-window prompt pane",
			func() {
				_, _ = tmuxSplitPrompt(`printf 'Session Name: '; read n; printf '%s\n' "$n" > /tmp/f`)
			},
			[]string{
				"tmux", "split-window", "-v", "-l", "30%", "-b",
				"-P", "-F", "#{pane_id}",
				"sh", "-c", `printf 'Session Name: '; read n; printf '%s\n' "$n" > /tmp/f`,
			},
		},
		{
			"select-pane restores the original focus",
			func() { _ = tmuxSelectPane("%0") },
			[]string{"tmux", "select-pane", "-t", "%0"},
		},
		{
			"attached sessions use the Q3 format",
			func() { _, _ = tmuxAttachedSessionNames() },
			[]string{"tmux", "list-sessions", "-F", "#{session_name}\t#{session_attached}"},
		},
		{
			"popup title WORKTREE SESSIONS stays one element",
			func() { _ = tmuxDisplayPopup("WORKTREE SESSIONS", "/app/hoppy", "worktree-switch") },
			[]string{
				"tmux", "display-popup", "-E",
				"-w", "60%", "-h", "90%",
				"-x", "R", "-y", "C",
				"-T", "WORKTREE SESSIONS", "-b", "rounded",
				"/app/hoppy", "worktree-switch",
			},
		},
		{
			"popup title CAPITAL SESSIONS stays one element",
			func() { _ = tmuxDisplayPopup("CAPITAL SESSIONS", "/app/hoppy", "capital-switch") },
			[]string{
				"tmux", "display-popup", "-E",
				"-w", "60%", "-h", "90%",
				"-x", "R", "-y", "C",
				"-T", "CAPITAL SESSIONS", "-b", "rounded",
				"/app/hoppy", "capital-switch",
			},
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			f := installFake(t, nil)
			c.call()
			got := f.only(t)
			if !reflect.DeepEqual(got, c.want) {
				t.Errorf("argv =\n  %#v\nwant\n  %#v", got, c.want)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// Parsing of the command output
// ---------------------------------------------------------------------------

func TestTmuxListSessionsParsing(t *testing.T) {
	installFake(t, staticReply("work @ 3 windows\nmy session @ 1 windows\n\n"))
	got, err := tmuxListSessions()
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"work @ 3 windows", "my session @ 1 windows"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

func TestTmuxListSessionsPropagatesError(t *testing.T) {
	installFake(t, func([]string) (string, error) {
		return "", errors.New("no server running")
	})
	if _, err := tmuxListSessions(); err == nil {
		t.Error("want an error when tmux fails")
	}
}

func TestTmuxCurrentSessionTrims(t *testing.T) {
	installFake(t, staticReply("work\n"))
	got, err := tmuxCurrentSession()
	if err != nil || got != "work" {
		t.Errorf("got %q, %v; want \"work\", nil", got, err)
	}
}

func TestTmuxListPanePaths(t *testing.T) {
	out := "work\t/home/yu/a\n" +
		"work\t/home/yu/b\n" +
		"work\t/home/yu/a\n" + // duplicate, kept once
		"other\t/home/yu/c\n" +
		"broken line with no tab\n"
	installFake(t, staticReply(out))

	got, err := tmuxListPanePaths()
	if err != nil {
		t.Fatal(err)
	}
	want := map[string][]string{
		"work":  {"/home/yu/a", "/home/yu/b"},
		"other": {"/home/yu/c"},
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

// Q3 (SPEC §6.4, §3.14.1): the old code grepped the default output for the
// word "attached" and always produced an empty filter. The field is read now.
func TestTmuxAttachedSessionNames(t *testing.T) {
	out := "work\t1\n" +
		"idle\t0\n" +
		"my session\t2\n" +
		// An empty flag must never count as "attached". parseLines trims the
		// row first, so this one loses its tab and is dropped as malformed —
		// which is the same outcome. The `f != ""` guard in
		// tmuxAttachedSessionNames is the belt to this braces.
		"blank\t\n" +
		"spaced\t 0 \n" + // whitespace around the flag is trimmed
		"junk\n"
	installFake(t, staticReply(out))

	got, err := tmuxAttachedSessionNames()
	if err != nil {
		t.Fatal(err)
	}
	want := map[string]bool{"work": true, "my session": true}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

func TestTmuxHasSession(t *testing.T) {
	installFake(t, staticReply(""))
	if !tmuxHasSession("work") {
		t.Error("exit 0 must mean the session exists")
	}
	installFake(t, func([]string) (string, error) {
		return "", errors.New("can't find session")
	})
	if tmuxHasSession("gone") {
		t.Error("a non-zero exit must mean the session is missing")
	}
}

func TestGitWorktrees(t *testing.T) {
	out := "worktree /home/yu/my/hoppy\n" +
		"HEAD abc123\n" +
		"branch refs/heads/master\n" +
		"\n" +
		"worktree /home/yu/my/hoppy-feature\n" +
		"HEAD def456\n"
	installFake(t, staticReply(out))

	got := gitWorktrees("/home/yu/my/hoppy")
	want := []string{"/home/yu/my/hoppy", "/home/yu/my/hoppy-feature"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("got %#v, want %#v", got, want)
	}
}

// SPEC §6.1: any git failure gives an empty list and never stops the program.
func TestGitWorktreesSwallowsFailure(t *testing.T) {
	installFake(t, func([]string) (string, error) {
		return "", errors.New("not a git repository")
	})
	got := gitWorktrees("/tmp")
	if len(got) != 0 {
		t.Errorf("got %#v, want an empty list", got)
	}
}

func TestExecRunEmptyArgv(t *testing.T) {
	if _, err := execRun(); err == nil {
		t.Error("execRun with no argv must fail")
	}
}

// The exit status MUST survive execRun's error wrapping.
//
// This is a real bug that was fixed: the stderr branch formatted the cause with
// %s instead of %w, so the *exec.ExitError was dropped and errors.As could not
// get the code back. Every non-zero exit then looked identical, which breaks the
// fzf rule that 0, 1 and 130 are normal and other codes are errors (SPEC §12).
func TestExecRunPreservesTheExitCode(t *testing.T) {
	cases := []struct {
		name string
		cmd  string
		code int
	}{
		{"with stderr output", "echo boom >&2; exit 7", 7},
		{"with no stderr output", "exit 3", 3},
		{"fzf's interrupt code", "echo cancelled >&2; exit 130", 130},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			_, err := execRun("sh", "-c", c.cmd)
			if err == nil {
				t.Fatalf("execRun(sh -c %q) returned nil, want an error", c.cmd)
			}
			var exitErr *exec.ExitError
			if !errors.As(err, &exitErr) {
				t.Fatalf("errors.As could not recover *exec.ExitError from %#v (%v)", err, err)
			}
			if got := exitErr.ExitCode(); got != c.code {
				t.Errorf("exit code = %d, want %d", got, c.code)
			}
		})
	}
}

// The stderr text must still reach the message, for log message 16.
func TestExecRunFoldsStderrIntoTheMessage(t *testing.T) {
	_, err := execRun("sh", "-c", "echo no server running >&2; exit 1")
	if err == nil {
		t.Fatal("want an error")
	}
	if !strings.Contains(err.Error(), "no server running") {
		t.Errorf("error = %q, want it to carry the stderr text", err.Error())
	}
	if !strings.HasPrefix(err.Error(), "sh: ") {
		t.Errorf("error = %q, want it to start with the command name", err.Error())
	}
}

// A command that cannot start at all is a different failure: there is no exit
// code to recover, and the caller must not read one.
func TestExecRunMissingBinary(t *testing.T) {
	_, err := execRun("this-binary-does-not-exist-hoppy")
	if err == nil {
		t.Fatal("want an error for a missing binary")
	}
	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) {
		t.Error("a missing binary must not look like a non-zero exit")
	}
}
