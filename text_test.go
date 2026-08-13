package main

import (
	"reflect"
	"strings"
	"testing"
)

func TestParseLines(t *testing.T) {
	cases := []struct {
		name string
		in   string
		want []string
	}{
		{"empty", "", []string{}},
		{"only newlines", "\n\n\n", []string{}},
		{"trims each line", "  a  \n b\n", []string{"a", "b"}},
		{"drops blank lines", "a\n\n\nb", []string{"a", "b"}},
		{"no trailing newline", "a\nb", []string{"a", "b"}},
		{"tabs are trimmed too", "\ta\t\n", []string{"a"}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := parseLines(c.in)
			if !reflect.DeepEqual(got, c.want) {
				t.Errorf("parseLines(%q) = %#v, want %#v", c.in, got, c.want)
			}
		})
	}
}

func TestEnsureTrailingNewline(t *testing.T) {
	cases := []struct{ in, want string }{
		{"", "\n"},
		{"a", "a\n"},
		{"a\n", "a\n"},
		{"a\n\n", "a\n\n"},
		{"a\nb", "a\nb\n"},
	}
	for _, c := range cases {
		if got := ensureTrailingNewline(c.in); got != c.want {
			t.Errorf("ensureTrailingNewline(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestNormalizeAtColumns(t *testing.T) {
	cases := []struct {
		name string
		in   []string
		want []string
	}{
		{"empty input", []string{}, []string{}},
		{"already normal", []string{"ADC @ 3 windows"}, []string{"ADC @ 3 windows"}},
		{"extra spaces", []string{"ADC  @  3 windows"}, []string{"ADC @ 3 windows"}},
		{"no delimiter is only trimmed", []string{"  plain  "}, []string{"plain"}},
		{"name with space", []string{"my session @ 1 windows"}, []string{"my session @ 1 windows"}},
		{"two delimiters rejoin", []string{"a@b@c"}, []string{"a @ b @ c"}},
		{"no separators at all", []string{"aaa"}, []string{"aaa"}},
		{
			// A tmux row that already carries " @ ". Splitting on the single
			// character "@" and rejoining with " @ " must be a no-op here.
			// This is the case that the old columnFormat(lines, " @ ")
			// signature invited callers to get wrong.
			"a row that is already \" @ \" separated is unchanged",
			[]string{"work @ 3 windows", "my session @ 12 windows"},
			[]string{"work @ 3 windows", "my session @ 12 windows"},
		},
		{
			// A BARE "@" inside the session name. The .mjs splits on EVERY "@",
			// so the row gains a column. We stay bug-compatible. tmux allows the
			// name; assertValidSessionName does not.
			"a bare @ in the session name adds a column",
			[]string{"e@mail @ 3 windows"},
			[]string{"e @ mail @ 3 windows"},
		},
		{
			"a leading @ produces an empty first column",
			[]string{"@work @ 1 windows"},
			[]string{" @ work @ 1 windows"},
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := normalizeAtColumns(c.in)
			if !reflect.DeepEqual(got, c.want) {
				t.Errorf("normalizeAtColumns(%#v) = %#v, want %#v", c.in, got, c.want)
			}
		})
	}
}

// normalizeAtColumns runs on rows that may already be normal (reload-sessions
// re-lists the same sessions), so it has to be idempotent for real tmux rows.
func TestNormalizeAtColumnsIsIdempotent(t *testing.T) {
	in := []string{"work @ 3 windows", "  spaced   @   1 windows ", "plain"}
	once := normalizeAtColumns(in)
	twice := normalizeAtColumns(once)
	if !reflect.DeepEqual(once, twice) {
		t.Errorf("not idempotent: %#v then %#v", once, twice)
	}
}

func TestAddNumberPrefixes(t *testing.T) {
	cases := []struct {
		name string
		in   []string
		want []string
	}{
		{
			"plain rows",
			[]string{"a @ 1 windows", "b @ 2 windows"},
			[]string{"[1] a @ 1 windows", "[2] b @ 2 windows"},
		},
		{
			"special rows are skipped and do not consume a number",
			[]string{"[current]", "a @ 1 windows", "[cancel]"},
			[]string{"[current]", "[1] a @ 1 windows", "[cancel]"},
		},
		{
			// M12: the test is a plain leading-"[" test, so a session really
			// named "[work]" gets no number and does not consume one either.
			"M12 session named [work]",
			[]string{"a @ 1 windows", "[work] @ 3 windows", "b @ 2 windows"},
			[]string{"[1] a @ 1 windows", "[work] @ 3 windows", "[2] b @ 2 windows"},
		},
		{"empty input", []string{}, []string{}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := addNumberPrefixes(c.in)
			if !reflect.DeepEqual(got, c.want) {
				t.Errorf("addNumberPrefixes(%#v) = %#v, want %#v", c.in, got, c.want)
			}
		})
	}
}

func TestAddNumberPrefixesStopsAtNine(t *testing.T) {
	in := make([]string, 12)
	for i := range in {
		in[i] = "s @ 1 windows"
	}
	got := addNumberPrefixes(in)
	if got[8] != "[9] s @ 1 windows" {
		t.Errorf("item 9 = %q, want %q", got[8], "[9] s @ 1 windows")
	}
	for i := 9; i < 12; i++ {
		if got[i] != "s @ 1 windows" {
			t.Errorf("item %d = %q, want it unnumbered", i+1, got[i])
		}
	}
}

func TestStripNumberPrefix(t *testing.T) {
	cases := []struct{ in, want string }{
		{"[1] work @ 3 windows", "work @ 3 windows"},
		{"[12] work", "work"},
		{"[cancel]", "[cancel]"},
		{"[1]work", "[1]work"}, // no space, so no match
		{"work", "work"},
	}
	for _, c := range cases {
		if got := stripNumberPrefix(c.in); got != c.want {
			t.Errorf("stripNumberPrefix(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestExtractSessionName(t *testing.T) {
	cases := []struct{ in, want string }{
		{"[1] work @ 3 windows", "work"},
		{"work @ 3 windows", "work"},
		{"my session @ 1 windows", "my session"},
		{"[cancel]", "[cancel]"},
		{"[current]", "[current]"},
		{"plain", "plain"},
		{"[1] plain", "plain"},
		// only the FIRST " @ " splits
		{"a @ b @ c", "a"},
		// the quote-bug shape from SPEC §0.9.2: a leading quote survives
		{"'work @ 3 windows'", "'work"},
	}
	for _, c := range cases {
		if got := extractSessionName(c.in); got != c.want {
			t.Errorf("extractSessionName(%q) = %q, want %q", c.in, got, c.want)
		}
	}
}

func TestParseTargets(t *testing.T) {
	cases := []struct {
		name      string
		selection string
		current   string
		want      []string
	}{
		{"empty selection", "", "cur", []string{}},
		{"single row", "[1] work @ 3 windows", "cur", []string{"work"}},
		{
			"multi select",
			"[1] a @ 1 windows\n[2] b @ 2 windows",
			"cur",
			[]string{"a", "b"},
		},
		{"cancel alone", "[cancel]", "cur", []string{}},
		{
			"cancel anywhere cancels everything",
			"[1] a @ 1 windows\n[cancel]",
			"cur",
			[]string{},
		},
		{"current row maps to the current session", "[current]", "cur", []string{"cur"}},
		{
			// M14: substring replace of the FIRST occurrence, not a row match.
			"M14 substring replace",
			"x[current]y @ 2 windows",
			"cur",
			[]string{"xcur"},
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got := parseTargets(c.selection, c.current)
			if !reflect.DeepEqual(got, c.want) {
				t.Errorf("parseTargets(%q, %q) = %#v, want %#v",
					c.selection, c.current, got, c.want)
			}
		})
	}
}

func TestDedupe(t *testing.T) {
	got := dedupe([]string{"b", "a", "b", "c", "a"})
	want := []string{"b", "a", "c"}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("dedupe = %#v, want %#v", got, want)
	}
	if got := dedupe([]string{}); len(got) != 0 {
		t.Errorf("dedupe([]) = %#v, want empty", got)
	}
}

// ---------------------------------------------------------------------------
// Shell words
// ---------------------------------------------------------------------------

func TestSplitShellWords(t *testing.T) {
	cases := []struct {
		name    string
		in      string
		want    []string
		wantErr bool
	}{
		{"empty gives zero words", "", []string{}, false},
		{"plain words", "fzf-tmux -p 80%", []string{"fzf-tmux", "-p", "80%"}, false},
		{"multi and height", "--multi --height 40%", []string{"--multi", "--height", "40%"}, false},
		{
			"single quotes group one word",
			"--bind 'ctrl-a:select-all'",
			[]string{"--bind", "ctrl-a:select-all"},
			false,
		},
		{
			// SPEC §0.5: inside double quotes \ escapes only " \ ` $.
			// So "a\b" must stay a\b. google/shlex would give "ab".
			"backslash inside double quotes stays literal",
			`"a\b"`,
			[]string{`a\b`},
			false,
		},
		{
			"double quote escape is honoured",
			`"a\"b"`,
			[]string{`a"b`},
			false,
		},
		{
			"parentheses are plain characters",
			"--bind 'ctrl-a:execute(foo)'",
			[]string{"--bind", "ctrl-a:execute(foo)"},
			false,
		},
		{
			"redirection and semicolons are plain characters",
			"'a;b>c|d'",
			[]string{"a;b>c|d"},
			false,
		},
		{
			"variables are not expanded",
			"'$HOME'",
			[]string{"$HOME"},
			false,
		},
		{"unbalanced quote is an error", `--bind 'oops`, nil, true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got, err := splitShellWords(c.in)
			if c.wantErr {
				if err == nil {
					t.Fatalf("splitShellWords(%q) = %#v, want an error", c.in, got)
				}
				return
			}
			if err != nil {
				t.Fatalf("splitShellWords(%q) returned %v", c.in, err)
			}
			if len(got) != len(c.want) {
				t.Fatalf("splitShellWords(%q) = %#v, want %#v", c.in, got, c.want)
			}
			for i := range got {
				if got[i] != c.want[i] {
					t.Errorf("word %d = %q, want %q", i, got[i], c.want[i])
				}
			}
		})
	}
}

func TestJoinShellWordsRoundTrip(t *testing.T) {
	cases := [][]string{
		{"/app/hoppy", "kill-single-from-line"},
		{"/path with space/hoppy", "switch-from-line"},
		{"/path'with'quote/hoppy", "switch"},
		{"/app/hoppy", "kill-single", "my session"},
	}
	for _, words := range cases {
		joined := joinShellWords(words...)
		back, err := splitShellWords(joined)
		if err != nil {
			t.Fatalf("splitShellWords(%q) returned %v", joined, err)
		}
		if !reflect.DeepEqual(back, words) {
			t.Errorf("round trip of %#v gave %q -> %#v", words, joined, back)
		}
	}
}

// ---------------------------------------------------------------------------
// Validators
// ---------------------------------------------------------------------------

func TestAssertNonEmptyString(t *testing.T) {
	if err := assertNonEmptyString("", "Field"); err == nil ||
		err.Error() != "Field cannot be empty" {
		t.Errorf("got %v, want \"Field cannot be empty\"", err)
	}
	if err := assertNonEmptyString("x", "Field"); err != nil {
		t.Errorf("got %v, want nil", err)
	}
}

func TestAssertMaxLength(t *testing.T) {
	if err := assertMaxLength("abcd", "Field", 3); err == nil ||
		err.Error() != "Field exceeds max length of 3 (got 4)" {
		t.Errorf("got %v, want \"Field exceeds max length of 3 (got 4)\"", err)
	}
	if err := assertMaxLength("abc", "Field", 3); err != nil {
		t.Errorf("got %v, want nil", err)
	}
	if err := assertMaxLength("", "Field", 3); err == nil ||
		err.Error() != "Field cannot be empty" {
		t.Errorf("empty should fail the non-empty rule first, got %v", err)
	}
}

func TestAssertValidSessionName(t *testing.T) {
	cases := []struct {
		name    string
		in      string
		wantErr string // "" means accept
	}{
		{"plain", "work", ""},
		{"digits and underscore", "proj_1", ""},
		{"hyphen", "test-dash", ""},
		{"ascii space", "my session", ""},
		{"empty", "", "Session name cannot be empty"},
		{
			"too long",
			strings.Repeat("a", 101),
			"Session name exceeds max length of 100 (got 101)",
		},
		{"exactly 100 runes is accepted", strings.Repeat("a", 100), ""},
		{
			// Length is counted in RUNES, not bytes. 100 three-byte ideographic
			// spaces are 300 bytes and must still pass rule 2.
			"exactly 100 multi-byte runes is accepted",
			strings.Repeat(string(rune(0x3000)), 100),
			"",
		},
		{
			"101 multi-byte runes is rejected with the rune count",
			strings.Repeat(string(rune(0x3000)), 101),
			"Session name exceeds max length of 100 (got 101)",
		},
		{"colon", "a:b", "Session name cannot contain colons (:)"},
		{"period", "a.b", "Session name cannot contain periods (.)"},
		{"newline", "a\nb", "Session name cannot contain newlines"},
		{"carriage return", "a\rb", "Session name cannot contain newlines"},
		{"tab is a control character", "a\tb", "Session name cannot contain control characters"},
		{"del is a control character", "a\x7fb", "Session name cannot contain control characters"},
		{
			"bracket is rejected by rule 8",
			"[work]",
			"Session name can only contain letters, numbers, underscore, hyphen, and spaces",
		},
		{
			"at sign is rejected by rule 8",
			"a@b",
			"Session name can only contain letters, numbers, underscore, hyphen, and spaces",
		},
		{
			"accented letters are rejected",
			"café",
			"Session name can only contain letters, numbers, underscore, hyphen, and spaces",
		},
		{
			"cyrillic is rejected",
			"работа",
			"Session name can only contain letters, numbers, underscore, hyphen, and spaces",
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			err := assertValidSessionName(c.in)
			if c.wantErr == "" {
				if err != nil {
					t.Errorf("assertValidSessionName(%q) = %v, want nil", c.in, err)
				}
				return
			}
			if err == nil || err.Error() != c.wantErr {
				t.Errorf("assertValidSessionName(%q) = %v, want %q", c.in, err, c.wantErr)
			}
		})
	}
}

// jsWhitespaceInNames are the code points JavaScript's \s accepts and Go's
// does not (SPEC §11.3.1). The runes are built numerically on purpose: the Go
// source then stays pure ASCII and no tool can normalise them away.
var jsWhitespaceInNames = []struct {
	name string
	r    rune
}{
	{"U+00A0 no-break space", 0x00A0},
	{"U+1680 ogham space mark", 0x1680},
	{"U+2000 en quad", 0x2000},
	{"U+2005 four-per-em space", 0x2005}, // inside the U+2000-U+200A range
	{"U+200A hair space", 0x200A},
	{"U+2028 line separator", 0x2028},
	{"U+2029 paragraph separator", 0x2029},
	{"U+202F narrow no-break space", 0x202F},
	{"U+205F medium mathematical space", 0x205F},
	{"U+3000 ideographic space", 0x3000},
	{"U+FEFF byte order mark", 0xFEFF},
}

func TestAssertValidSessionNameAcceptsJSWhitespace(t *testing.T) {
	for _, c := range jsWhitespaceInNames {
		t.Run(c.name, func(t *testing.T) {
			name := "a" + string(c.r) + "b"
			if err := assertValidSessionName(name); err != nil {
				t.Errorf("U+%04X was rejected: %v", c.r, err)
			}
		})
	}
	// U+200B is not whitespace in JavaScript either, so it stays rejected.
	if err := assertValidSessionName("a" + string(rune(0x200B)) + "b"); err == nil {
		t.Error("U+200B zero width space must be rejected")
	}
}

func TestSessionNameRegexIsNotGoWhitespace(t *testing.T) {
	// A guard against someone "simplifying" the class back to \s.
	// Go's \s covers only \t \n \f \r and space. Rules 5 and 6 reject the
	// first four before rule 8 runs, so the visible difference is the 10
	// Unicode spaces below.
	for _, r := range []rune{
		0x00A0, 0x1680, 0x2000, 0x200A, 0x2028, 0x2029, 0x202F, 0x205F, 0x3000, 0xFEFF,
	} {
		if !sessionNameRe.MatchString(string(r)) {
			t.Errorf("rule 8 rejected U+%04X; the class was narrowed", r)
		}
	}
	if sessionNameRe.MatchString("a\tb") {
		t.Error("rule 8 must not accept a tab")
	}
}

func TestAssertValidAction(t *testing.T) {
	for _, a := range validActions {
		if err := assertValidAction(a); err != nil {
			t.Errorf("assertValidAction(%q) = %v, want nil", a, err)
		}
	}
	// Helper actions are routed before the gate, so the gate rejects them (Q15).
	for _, a := range []string{"switch-from-line", "kill-single-from-line", "delayed-switch"} {
		if err := assertValidAction(a); err == nil {
			t.Errorf("assertValidAction(%q) = nil, want an error", a)
		}
	}
	want := "Invalid action: bogus. Must be one of: switch, new, rename, detach, " +
		"kill, kill-single, reload-sessions, popup-switch, worktree-switch, " +
		"popup-worktree-switch, capital-switch, popup-capital-switch"
	err := assertValidAction("bogus")
	if err == nil || err.Error() != want {
		t.Errorf("assertValidAction(\"bogus\") = %v,\nwant %q", err, want)
	}
}

func TestAssertValidItemsArray(t *testing.T) {
	if err := assertValidItemsArray(nil, "items"); err == nil ||
		err.Error() != "items cannot be empty" {
		t.Errorf("got %v, want \"items cannot be empty\"", err)
	}
	if err := assertValidItemsArray([]string{"a", "b"}, "items"); err != nil {
		t.Errorf("got %v, want nil", err)
	}
	long := []string{"ok", strings.Repeat("x", 1001)}
	if err := assertValidItemsArray(long, "items"); err == nil ||
		err.Error() != "items[1] exceeds max length of 1000 characters" {
		t.Errorf("got %v, want the index-1 length error", err)
	}
	many := make([]string, 10001)
	for i := range many {
		many[i] = "x"
	}
	if err := assertValidItemsArray(many, "items"); err == nil ||
		err.Error() != "items has too many items: 10001 (max 10000)" {
		t.Errorf("got %v, want the too-many-items error", err)
	}
}

func TestAssertValidFzfOptions(t *testing.T) {
	if err := assertValidFzfOptions("", "TMUX_FZF_OPTIONS"); err != nil {
		t.Errorf("empty options should be fine, got %v", err)
	}
	if err := assertValidFzfOptions("--multi", "TMUX_FZF_OPTIONS"); err != nil {
		t.Errorf("got %v, want nil", err)
	}
	if err := assertValidFzfOptions(strings.Repeat("x", 10001), "TMUX_FZF_OPTIONS"); err == nil ||
		err.Error() != "TMUX_FZF_OPTIONS exceeds max length of 10000 characters" {
		t.Errorf("got %v, want the length error", err)
	}
	if err := assertValidFzfOptions("a\x00b", "TMUX_FZF_OPTIONS"); err == nil ||
		err.Error() != "TMUX_FZF_OPTIONS cannot contain null bytes" {
		t.Errorf("got %v, want the null byte error", err)
	}
}

func TestAssertValidHeader(t *testing.T) {
	if err := assertValidHeader(""); err != nil {
		t.Errorf("an empty header is allowed, got %v", err)
	}
	if err := assertValidHeader("Select an action."); err != nil {
		t.Errorf("got %v, want nil", err)
	}
	if err := assertValidHeader(strings.Repeat("x", 501)); err == nil ||
		err.Error() != "Header exceeds max length of 500 characters" {
		t.Errorf("got %v, want the length error", err)
	}
	if err := assertValidHeader("a\nb"); err == nil ||
		err.Error() != "Header cannot contain newlines" {
		t.Errorf("got %v, want the newline error", err)
	}
}
