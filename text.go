// text.go — pure string helpers and validators. No I/O, no processes.
//
// Everything here is table-testable with stdlib `testing`.
// SPEC §4.3-§4.7 (helpers), §11 (validators), §0.5 (shell splitting).
package main

import (
	"errors"
	"fmt"
	"regexp"
	"strings"
	"unicode/utf8"

	shellquote "github.com/kballard/go-shellquote"
)

// sessionNameRe is SPEC §11.3.1 rule 8, the effective accepted character set.
// Do NOT use Go's \s here: Go's \s is five ASCII characters, JavaScript's is 18
// more code points, and narrowing it is a user-visible change.
// Compiled once at package level: this runs on every keypress path.
var sessionNameRe = regexp.MustCompile(
	`^[A-Za-z0-9_\-\x{0020}\x{00A0}\x{1680}\x{2000}-\x{200A}\x{2028}\x{2029}\x{202F}\x{205F}\x{3000}\x{FEFF}]+$`)

// numberPrefixRe strips the "[N] " prefix in extractSessionName (SPEC §4.4).
var numberPrefixRe = regexp.MustCompile(`^\[\d+\] `)

// controlCharRe is rule 6 of SPEC §11.3: ASCII control characters.
var controlCharRe = regexp.MustCompile(`[\x00-\x1F\x7F]`)

// sessionSep is the separator tmux prints between the name and the window
// count. It comes from the -F format "#S @ #{session_windows} windows".
const sessionSep = " @ "

// ---------------------------------------------------------------------------
// Pure helpers
// ---------------------------------------------------------------------------

// parseLines splits text on "\n", trims every line and drops the empty ones
// (SPEC §4.6). Empty input gives an empty slice, never nil.
func parseLines(text string) []string {
	out := []string{}
	if text == "" {
		return out
	}
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(line)
		if line != "" {
			out = append(out, line)
		}
	}
	return out
}

// ensureTrailingNewline adds one "\n" if the text does not end with one.
// Used when we write items to fzf's stdin.
func ensureTrailingNewline(text string) string {
	if strings.HasSuffix(text, "\n") {
		return text
	}
	return text + "\n"
}

// normalizeAtColumns normalises the spacing around "@" (SPEC §4.1 step 5):
// "ADC  @  3 windows" becomes "ADC @ 3 windows". A line with no "@" is trimmed.
//
// The name says "At", not "delimiter", on purpose. The split and the join are
// DIFFERENT strings and that asymmetry is load-bearing: the split is on the
// single character "@", the join is " @ ". A delimiter parameter would look
// right, compile, and silently corrupt any row holding a bare "@".
//
// Bug-compatible with the .mjs: splitting on EVERY "@" turns "a@b@c" into
// "a @ b @ c". tmux allows a session named "e@mail"; the name validator does not.
func normalizeAtColumns(lines []string) []string {
	out := []string{}
	if len(lines) == 0 {
		return out
	}
	for _, line := range lines {
		parts := strings.Split(line, "@")
		if len(parts) < 2 {
			out = append(out, strings.TrimSpace(line))
			continue
		}
		for i := range parts {
			parts[i] = strings.TrimSpace(parts[i])
		}
		out = append(out, strings.Join(parts, sessionSep))
	}
	return out
}

// addNumberPrefixes turns the first 9 normal rows into "[1] row" … "[9] row"
// (SPEC §4.3).
//
// M12: the test is a plain leading-"[" test, so ANY item starting with "[" is
// pushed through unchanged and does NOT consume a number. tmux allows a session
// named "[work]", so "[work] @ 3 windows" stays unnumbered. Keep this.
func addNumberPrefixes(items []string) []string {
	out := make([]string, 0, len(items))
	numberIndex := 1
	for _, item := range items {
		switch {
		case strings.HasPrefix(item, "["):
			out = append(out, item)
		case numberIndex <= 9:
			out = append(out, fmt.Sprintf("[%d] %s", numberIndex, item))
			numberIndex++
		default:
			out = append(out, item)
		}
	}
	return out
}

// stripNumberPrefix removes a leading "[N] " if there is one.
func stripNumberPrefix(line string) string {
	return numberPrefixRe.ReplaceAllString(line, "")
}

// extractSessionName takes the session name out of one fzf row (SPEC §4.4).
// It drops a "[N] " prefix, then keeps everything before the first " @ ".
// A row with no " @ " is returned whole, so "[cancel]" stays "[cancel]".
func extractSessionName(line string) string {
	cleaned := stripNumberPrefix(line)
	if i := strings.Index(cleaned, sessionSep); i >= 0 {
		return cleaned[:i]
	}
	return cleaned
}

// parseTargets turns an fzf selection into session names (SPEC §4.5).
// Any "[cancel]" row cancels the whole selection.
//
// M14: the "[current]" swap is a SUBSTRING replace of the FIRST occurrence,
// not a whole-row match. A row "x[current]y @ 2 windows" becomes
// "x<current> @ y @ 2 windows" and yields "x<current>". Keep it bug-compatible.
func parseTargets(selection, currentSession string) []string {
	lines := parseLines(selection)
	out := []string{}
	if len(lines) == 0 {
		return out
	}
	for _, line := range lines {
		if line == "[cancel]" {
			return []string{}
		}
	}
	for _, line := range lines {
		line = strings.Replace(line, "[current]", currentSession+sessionSep, 1)
		if name := extractSessionName(line); name != "" {
			out = append(out, name)
		}
	}
	return out
}

// dedupe keeps the first occurrence of every item and preserves order
// (SPEC §4.7).
func dedupe(items []string) []string {
	seen := make(map[string]struct{}, len(items))
	out := make([]string, 0, len(items))
	for _, item := range items {
		if _, ok := seen[item]; ok {
			continue
		}
		seen[item] = struct{}{}
		out = append(out, item)
	}
	return out
}

// splitShellWords splits a POSIX shell command line into words, for
// TMUX_FZF_BIN and TMUX_FZF_OPTIONS (SPEC §0.5). No expansion, no substitution,
// no globbing. An unbalanced quote is an error, never a guess.
func splitShellWords(s string) ([]string, error) {
	return shellquote.Split(s)
}

// joinShellWords quotes words so a POSIX sh reparses them as the same words,
// for the fzf --bind inner command (SPEC Q17).
// Never pass fzf's {} placeholder through this — fzf quotes it itself.
func joinShellWords(words ...string) string {
	return shellquote.Join(words...)
}

// ---------------------------------------------------------------------------
// Validators (SPEC §11). The .mjs `typeof value !== 'string'` branch is
// unreachable in Go, so its message is gone; every other message is kept word
// for word. Length is counted in runes, not UTF-16 code units.
// ---------------------------------------------------------------------------

// assertNonEmptyString rejects an empty value (SPEC §11.1).
func assertNonEmptyString(value, field string) error {
	if len(value) == 0 {
		return fmt.Errorf("%s cannot be empty", field)
	}
	return nil
}

// assertMaxLength rejects an empty or too long value (SPEC §11.2).
func assertMaxLength(value, field string, max int) error {
	if err := assertNonEmptyString(value, field); err != nil {
		return err
	}
	if n := utf8.RuneCountInString(value); n > max {
		return fmt.Errorf("%s exceeds max length of %d (got %d)", field, max, n)
	}
	return nil
}

// assertValidSessionName runs the 8 rules of SPEC §11.3, in that exact order.
// Rule 8 makes rules 3-7 redundant, but the messages differ, so keep them all.
func assertValidSessionName(name string) error {
	if err := assertMaxLength(name, "Session name", 100); err != nil {
		return err
	}
	if strings.Contains(name, ":") {
		return errors.New("Session name cannot contain colons (:)")
	}
	if strings.Contains(name, ".") {
		return errors.New("Session name cannot contain periods (.)")
	}
	if strings.Contains(name, "\n") || strings.Contains(name, "\r") {
		return errors.New("Session name cannot contain newlines")
	}
	if controlCharRe.MatchString(name) {
		return errors.New("Session name cannot contain control characters")
	}
	// Deliberately unreachable: rule 6 above already rejects \x00 as a control
	// character, so this branch can never fire. It is kept because the .mjs has
	// it in this exact position and we stay bug-compatible with the rule order
	// (SPEC §11.3). Do not "clean it up".
	if strings.Contains(name, "\x00") {
		return errors.New("Session name cannot contain null bytes")
	}
	if !sessionNameRe.MatchString(name) {
		return errors.New("Session name can only contain letters, numbers, underscore, hyphen, and spaces")
	}
	return nil
}

// assertValidAction checks the action against validActions (SPEC §2.1, §11.4).
// The three helper actions are routed before this gate, so they are absent
// from the list on purpose (Q15).
func assertValidAction(action string) error {
	for _, valid := range validActions {
		if action == valid {
			return nil
		}
	}
	return fmt.Errorf("Invalid action: %s. Must be one of: %s",
		action, strings.Join(validActions, ", "))
}

// assertValidItemsArray checks an fzf item list (SPEC §11.5).
// The per-item check runs before the total-count check, like the .mjs.
func assertValidItemsArray(items []string, field string) error {
	if len(items) == 0 {
		return fmt.Errorf("%s cannot be empty", field)
	}
	for i, item := range items {
		if utf8.RuneCountInString(item) > 1000 {
			return fmt.Errorf("%s[%d] exceeds max length of 1000 characters", field, i)
		}
	}
	if len(items) > 10000 {
		return fmt.Errorf("%s has too many items: %d (max 10000)", field, len(items))
	}
	return nil
}

// assertValidFzfOptions checks a raw fzf option string (SPEC §11.6).
// An empty value is fine here — it simply produces zero words.
func assertValidFzfOptions(value, field string) error {
	if utf8.RuneCountInString(value) > 10000 {
		return fmt.Errorf("%s exceeds max length of 10000 characters", field)
	}
	if strings.Contains(value, "\x00") {
		return fmt.Errorf("%s cannot contain null bytes", field)
	}
	return nil
}

// assertValidHeader checks an fzf header (SPEC §11.7).
// An empty header stands for the .mjs null/undefined case and is allowed.
func assertValidHeader(header string) error {
	if header == "" {
		return nil
	}
	if utf8.RuneCountInString(header) > 500 {
		return errors.New("Header exceeds max length of 500 characters")
	}
	if strings.Contains(header, "\n") {
		return errors.New("Header cannot contain newlines")
	}
	return nil
}
