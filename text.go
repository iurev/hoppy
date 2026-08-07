// text.go — pure string helpers and validators. No I/O, no processes.
//
// Everything here is table-testable with stdlib `testing`.
//
// Planned functions:
//
//	parseLines(text string) []string                        -- SPEC §4.6
//	dedupe(items []string) []string                         -- SPEC §4.7
//	addNumberPrefixes(items []string) []string              -- SPEC §4.3 (leading "[" test only, M12)
//	extractSessionName(line string) string                  -- SPEC §4.4
//	parseTargets(selection, current string) []string        -- SPEC §4.5 (substring replace, M14)
//	splitShellWords(s string) ([]string, error)             -- SPEC §0.5
//	joinShellWords(words ...string) string                  -- SPEC Q17
//	assertNonEmptyString(v, field string) error             -- SPEC §11.1
//	assertMaxLength(v, field string, max int) error         -- SPEC §11.2
//	assertValidSessionName(name string) error               -- SPEC §11.3
//	assertValidAction(action string) error                  -- SPEC §11.4 / §2.1
//	assertValidItemsArray(items []string, field string) error -- SPEC §11.5
//	assertValidFzfOptions(v, field string) error            -- SPEC §11.6
//	assertValidHeader(header string) error                  -- SPEC §11.7
//
// NOT IMPLEMENTED YET (except splitShellWords, which proves the dependency).
package main

import (
	"regexp"

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

// splitShellWords splits a POSIX shell command line into words.
// Used for TMUX_FZF_BIN and TMUX_FZF_OPTIONS (SPEC §0.5).
// No variable expansion, no command substitution, no globbing, no redirection.
// An unbalanced quote is an error, never a guess.
func splitShellWords(s string) ([]string, error) {
	return shellquote.Split(s)
}

// joinShellWords quotes words so a POSIX sh reparses them as the same words.
// Used to build the fzf --bind inner command (SPEC Q17).
// Never pass fzf's {} placeholder through this — fzf quotes it itself.
func joinShellWords(words ...string) string {
	return shellquote.Join(words...)
}
