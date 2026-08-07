package main

import (
	"errors"
	"reflect"
	"strings"
	"testing"
)

// ---------------------------------------------------------------------------
// The fzf seam fake
// ---------------------------------------------------------------------------

type fakeFzf struct {
	argv   []string
	stdin  string
	calls  int
	stdout string
	stderr string
	code   int
	err    error
}

func installFakeFzf(t *testing.T, f *fakeFzf) *fakeFzf {
	t.Helper()
	old := runFzfCmd
	runFzfCmd = func(argv []string, stdin string) (string, string, int, error) {
		f.calls++
		f.argv = append([]string(nil), argv...)
		f.stdin = stdin
		return f.stdout, f.stderr, f.code, f.err
	}
	t.Cleanup(func() { runFzfCmd = old })
	return f
}

// withEnv sets one environment variable for the duration of a test.
func withEnv(t *testing.T, key, value string) {
	t.Helper()
	t.Setenv(key, value)
}

// ---------------------------------------------------------------------------
// buildFzfArgv (SPEC §10.2.1)
// ---------------------------------------------------------------------------

func TestBuildFzfArgvDefaultShape(t *testing.T) {
	withEnv(t, "TMUX_FZF_BIN", "fzf")
	withEnv(t, "TMUX_FZF_OPTIONS", "")

	got, err := buildFzfArgv("", nil)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{
		"fzf",
		"--no-sort",
		"--delimiter", " @ ",
		"--with-nth=1..",
		"--nth=1",
		"--with-shell", "sh -c",
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("argv =\n  %#v\nwant\n  %#v", got, want)
	}
}

func TestBuildFzfArgvFullOrder(t *testing.T) {
	withEnv(t, "TMUX_FZF_BIN", "fzf-tmux -p 80%")
	withEnv(t, "TMUX_FZF_OPTIONS", "--multi --height 40%")

	got, err := buildFzfArgv("Select an action.", []string{"ctrl-a:select-all", "ctrl-b:up"})
	if err != nil {
		t.Fatal(err)
	}
	want := []string{
		// 1: TMUX_FZF_BIN, shell-split
		"fzf-tmux", "-p", "80%",
		// 2: TMUX_FZF_OPTIONS, shell-split
		"--multi", "--height", "40%",
		// 3-7: our own options
		"--no-sort",
		"--delimiter", " @ ",
		"--with-nth=1..",
		"--nth=1",
		"--with-shell", "sh -c",
		// 8: the header
		"--header", "Select an action.",
		// 9: one --bind pair per binding
		"--bind", "ctrl-a:select-all",
		"--bind", "ctrl-b:up",
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("argv =\n  %#v\nwant\n  %#v", got, want)
	}
}

// SPEC §0.9.2 / §10.2.1: the delimiter is the three characters space, @, space.
// A copied shell quote here is the highest-risk bug in the port and nothing else
// catches it — the UI still looks right and only the ordering goes wrong.
func TestBuildFzfArgvDelimiterHasNoQuotes(t *testing.T) {
	withEnv(t, "TMUX_FZF_BIN", "fzf")
	withEnv(t, "TMUX_FZF_OPTIONS", "")

	argv, err := buildFzfArgv("", nil)
	if err != nil {
		t.Fatal(err)
	}
	i := indexOf(argv, "--delimiter")
	if i < 0 || i+1 >= len(argv) {
		t.Fatal("--delimiter is missing from the argv")
	}
	if argv[i+1] != " @ " {
		t.Errorf("delimiter = %q, want %q", argv[i+1], " @ ")
	}
	if argv[i+1] != sessionSep {
		t.Error("the delimiter must be the ONE sessionSep constant")
	}
	for j, a := range argv {
		if strings.ContainsAny(a, `'"`) {
			t.Errorf("argv[%d] = %q holds a quote character (SPEC §0.9.2)", j, a)
		}
	}
}

// The header is its own argv element, so Q9 (the no-op quote escape) disappears
// and a header holding a quote cannot break the option string.
func TestBuildFzfArgvHeaderIsOneElement(t *testing.T) {
	withEnv(t, "TMUX_FZF_BIN", "fzf")
	withEnv(t, "TMUX_FZF_OPTIONS", "")

	argv, err := buildFzfArgv(`say "hi" (1/2)`, nil)
	if err != nil {
		t.Fatal(err)
	}
	i := indexOf(argv, "--header")
	if i < 0 {
		t.Fatal("--header is missing")
	}
	if argv[i+1] != `say "hi" (1/2)` {
		t.Errorf("header = %q, want it verbatim", argv[i+1])
	}
}

func TestBuildFzfArgvOmitsAnEmptyHeader(t *testing.T) {
	withEnv(t, "TMUX_FZF_BIN", "fzf")
	withEnv(t, "TMUX_FZF_OPTIONS", "")

	argv, err := buildFzfArgv("", nil)
	if err != nil {
		t.Fatal(err)
	}
	if indexOf(argv, "--header") >= 0 {
		t.Error("an empty header must not add --header")
	}
}

// SPEC §0.5 / Q17: --with-shell is what makes shellquote.Join provably right
// inside --bind. Without it fzf uses $SHELL, which may be fish or nushell.
//
// The VALUE must be "sh -c", one argv element. fzf's --with-shell takes the
// shell AND its flags and then runs `<those words> <command>`. A bare "sh"
// makes fzf run `sh <command>`, so sh treats the command text as a file name
// and EVERY binding fails silently. Verified against fzf 0.60.3.
func TestBuildFzfArgvAlwaysForcesPosixShell(t *testing.T) {
	withEnv(t, "TMUX_FZF_BIN", "fzf")
	withEnv(t, "TMUX_FZF_OPTIONS", "")

	argv, err := buildFzfArgv("h", []string{"ctrl-a:up"})
	if err != nil {
		t.Fatal(err)
	}
	i := indexOf(argv, "--with-shell")
	if i < 0 {
		t.Fatalf("argv = %#v, want --with-shell", argv)
	}
	if argv[i+1] != "sh -c" {
		t.Errorf("--with-shell value = %q, want %q (the flag is not optional)",
			argv[i+1], "sh -c")
	}
}

// SPEC §0.5 / D9: TMUX_FZF_BIN and TMUX_FZF_OPTIONS are raw SHELL strings.
func TestBuildFzfArgvShellSplitsTheEnvironment(t *testing.T) {
	cases := []struct {
		name string
		bin  string
		opts string
		want []string
	}{
		{"a bin with arguments", "fzf-tmux -p 80%", "", []string{"fzf-tmux", "-p", "80%"}},
		{"quoted options group one word", "fzf", "--bind 'ctrl-a:select-all'",
			[]string{"fzf", "--bind", "ctrl-a:select-all"}},
		{"parentheses survive", "fzf", "--bind 'ctrl-a:execute(foo bar)'",
			[]string{"fzf", "--bind", "ctrl-a:execute(foo bar)"}},
		{"empty options give zero words", "fzf", "", []string{"fzf"}},
		{"a path with a space", `"/opt/my tools/fzf"`, "",
			[]string{"/opt/my tools/fzf"}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			withEnv(t, "TMUX_FZF_BIN", c.bin)
			withEnv(t, "TMUX_FZF_OPTIONS", c.opts)

			argv, err := buildFzfArgv("", nil)
			if err != nil {
				t.Fatal(err)
			}
			head := argv[:len(c.want)]
			if !reflect.DeepEqual(head, c.want) {
				t.Errorf("head = %#v, want %#v", head, c.want)
			}
		})
	}
}

func TestBuildFzfArgvDefaultsToFzf(t *testing.T) {
	withEnv(t, "TMUX_FZF_BIN", "")
	withEnv(t, "TMUX_FZF_OPTIONS", "")

	argv, err := buildFzfArgv("", nil)
	if err != nil {
		t.Fatal(err)
	}
	if argv[0] != defaultFzfBin {
		t.Errorf("argv[0] = %q, want %q", argv[0], defaultFzfBin)
	}
}

func TestBuildFzfArgvRejectsBadInput(t *testing.T) {
	cases := []struct {
		name    string
		bin     string
		opts    string
		header  string
		wantMsg string
	}{
		{
			"an unbalanced quote in TMUX_FZF_BIN",
			`fzf "oops`, "", "",
			"TMUX_FZF_BIN is not valid shell text",
		},
		{
			"an unbalanced quote in TMUX_FZF_OPTIONS",
			"fzf", "--bind 'oops", "",
			"TMUX_FZF_OPTIONS is not valid shell text",
		},
		// A null byte in TMUX_FZF_OPTIONS cannot be tested through the process
		// environment: os.Setenv rejects it before we ever see it. The
		// assertValidFzfOptions guard is covered by TestAssertValidFzfOptions.
		{
			"a whitespace-only bin gives zero words",
			"   ", "", "",
			"TMUX_FZF_RUN command is empty.",
		},
		{
			"a newline in the header",
			"fzf", "", "a\nb",
			"Header cannot contain newlines",
		},
		{
			"a too long bin",
			strings.Repeat("f", 1001), "", "",
			"TMUX_FZF_BIN exceeds max length of 1000 (got 1001)",
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			withEnv(t, "TMUX_FZF_BIN", c.bin)
			withEnv(t, "TMUX_FZF_OPTIONS", c.opts)

			_, err := buildFzfArgv(c.header, nil)
			if err == nil {
				t.Fatalf("want an error mentioning %q", c.wantMsg)
			}
			if !strings.Contains(err.Error(), c.wantMsg) {
				t.Errorf("error = %q, want it to mention %q", err.Error(), c.wantMsg)
			}
		})
	}
}

// ---------------------------------------------------------------------------
// runFzf (SPEC §10.1, §12)
// ---------------------------------------------------------------------------

func TestRunFzfWritesItemsToStdin(t *testing.T) {
	withEnv(t, "TMUX_FZF_BIN", "fzf")
	withEnv(t, "TMUX_FZF_OPTIONS", "")
	f := installFakeFzf(t, &fakeFzf{stdout: "[1] work @ 3 windows\n", code: 0})

	got, err := runFzf([]string{"[1] work @ 3 windows", "[cancel]"}, headerSwitch, nil)
	if err != nil {
		t.Fatal(err)
	}
	if f.stdin != "[1] work @ 3 windows\n[cancel]\n" {
		t.Errorf("stdin = %q", f.stdin)
	}
	if got != "[1] work @ 3 windows" {
		t.Errorf("selection = %q", got)
	}
}

// SPEC §12: 0, 1 and 130 are all normal. Only other codes are errors.
func TestRunFzfExitCodes(t *testing.T) {
	cases := []struct {
		name    string
		code    int
		stdout  string
		want    string
		wantErr bool
	}{
		{"0 ExitOk", 0, "picked @ 1 windows\n", "picked @ 1 windows", false},
		{"1 ExitNoMatch", 1, "", "", false},
		{"130 ExitInterrupt", 130, "", "", false},
		{"2 ExitError", 2, "", "", true},
		{"126 ExitBecome", 126, "", "", true},
		{"127 command not found", 127, "", "", true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			withEnv(t, "TMUX_FZF_BIN", "fzf")
			withEnv(t, "TMUX_FZF_OPTIONS", "")
			installFakeFzf(t, &fakeFzf{stdout: c.stdout, stderr: "boom", code: c.code})

			got, err := runFzf([]string{"a", "[cancel]"}, "h", nil)
			if c.wantErr {
				if err == nil {
					t.Fatalf("code %d must be an error", c.code)
				}
				return
			}
			if err != nil {
				t.Fatalf("code %d must be normal, got %v", c.code, err)
			}
			if got != c.want {
				t.Errorf("selection = %q, want %q", got, c.want)
			}
		})
	}
}

func TestRunFzfTrimsTrailingWhitespaceOnly(t *testing.T) {
	withEnv(t, "TMUX_FZF_BIN", "fzf")
	withEnv(t, "TMUX_FZF_OPTIONS", "")
	installFakeFzf(t, &fakeFzf{stdout: "  [1] my session @ 2 windows  \n\n", code: 0})

	got, err := runFzf([]string{"a", "[cancel]"}, "h", nil)
	if err != nil {
		t.Fatal(err)
	}
	// trimEnd only: the leading spaces survive, exactly like the .mjs.
	if got != "  [1] my session @ 2 windows" {
		t.Errorf("selection = %q", got)
	}
}

func TestRunFzfRejectsAnEmptyItemList(t *testing.T) {
	installFakeFzf(t, &fakeFzf{code: 0})
	_, err := runFzf(nil, "h", nil)
	if err == nil || err.Error() != "fzf items cannot be empty" {
		t.Errorf("got %v, want \"fzf items cannot be empty\"", err)
	}
}

func TestRunFzfReportsASpawnFailure(t *testing.T) {
	withEnv(t, "TMUX_FZF_BIN", "fzf")
	withEnv(t, "TMUX_FZF_OPTIONS", "")
	installFakeFzf(t, &fakeFzf{code: -1, err: errors.New("exec: \"fzf\": not found")})

	if _, err := runFzf([]string{"a"}, "h", nil); err == nil {
		t.Error("a spawn failure must reach the caller")
	}
}

// ---------------------------------------------------------------------------
// Bindings (SPEC §3.11, Q17)
// ---------------------------------------------------------------------------

func TestSwitchBindingsOrderAndShape(t *testing.T) {
	got := switchBindings("/app/session-zx")
	want := []string{
		"del:execute(/app/session-zx kill-single-from-line {})" +
			"+reload(/app/session-zx reload-sessions)",
		"ctrl-n:down+execute-silent(/app/session-zx switch-from-line {})",
		"ctrl-p:up+execute-silent(/app/session-zx switch-from-line {})",
		"1:pos(1)+accept,2:pos(2)+accept,3:pos(3)+accept,4:pos(4)+accept," +
			"5:pos(5)+accept,6:pos(6)+accept,7:pos(7)+accept,8:pos(8)+accept," +
			"9:pos(9)+accept",
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("bindings =\n  %#v\nwant\n  %#v", got, want)
	}
}

func TestPreviewBindingsHaveNoDelKey(t *testing.T) {
	got := previewBindings("/app/session-zx")
	if len(got) != 2 {
		t.Fatalf("got %d bindings, want 2", len(got))
	}
	for _, b := range got {
		if strings.HasPrefix(b, "del:") {
			t.Error("worktree-switch and capital-switch must NOT bind DEL (SPEC §3.9)")
		}
	}
	if !strings.HasPrefix(got[0], "ctrl-n:down+") {
		t.Errorf("got[0] = %q", got[0])
	}
	if !strings.HasPrefix(got[1], "ctrl-p:up+") {
		t.Errorf("got[1] = %q", got[1])
	}
}

// Q17: the binary path is quoted for the POSIX sh that fzf runs the binding
// under. A space used to split the command silently.
func TestSwitchBindingsQuoteAwkwardPaths(t *testing.T) {
	cases := []struct {
		name string
		self string
		want string
	}{
		{"a space", "/opt/my tools/session-zx", "'/opt/my tools/session-zx'"},
		// shellquote.Join escapes a bare "'" with a backslash rather than the
		// '\'' dance. Both are correct POSIX; the round-trip below is the real
		// assertion.
		{"a single quote", "/opt/it's/session-zx", `/opt/it\'s/session-zx`},
		{"brackets need no quoting for sh word splitting", "/home/u/[work]/session-zx", ""},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := switchBindings(c.self)
			if c.want != "" && !strings.Contains(got[0], c.want) {
				t.Errorf("binding = %q, want it to contain %q", got[0], c.want)
			}
			// Whatever the quoting, the command inside execute(...) must split
			// back into exactly our two words under POSIX sh.
			inner := between(got[0], "execute(", " {})")
			words, err := splitShellWords(inner)
			if err != nil {
				t.Fatalf("splitShellWords(%q) = %v", inner, err)
			}
			wantWords := []string{c.self, "kill-single-from-line"}
			if !reflect.DeepEqual(words, wantWords) {
				t.Errorf("inner %q split to %#v, want %#v", inner, words, wantWords)
			}
		})
	}
}

// The {} placeholder is fzf's own and must never be shell-quoted by us.
func TestSwitchBindingsLeaveThePlaceholderBare(t *testing.T) {
	for _, b := range switchBindings("/opt/my tools/session-zx") {
		if strings.Contains(b, `'{}'`) || strings.Contains(b, `"{}"`) {
			t.Errorf("binding %q quoted fzf's {} placeholder", b)
		}
	}
}

func TestNumberBindingsCoverOneToNine(t *testing.T) {
	got := numberBindings()
	parts := strings.Split(got, ",")
	if len(parts) != 9 {
		t.Fatalf("got %d number bindings, want 9", len(parts))
	}
	if parts[0] != "1:pos(1)+accept" || parts[8] != "9:pos(9)+accept" {
		t.Errorf("bindings = %q", got)
	}
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

func indexOf(argv []string, want string) int {
	for i, a := range argv {
		if a == want {
			return i
		}
	}
	return -1
}

func between(s, open, close string) string {
	i := strings.Index(s, open)
	if i < 0 {
		return ""
	}
	rest := s[i+len(open):]
	j := strings.Index(rest, close)
	if j < 0 {
		return rest
	}
	return rest[:j]
}
