// sessions.go — building, ordering and filtering the session list.
// Row shape: "[1] name @ 3 windows". See SPEC §4.1 (list), §4.2 (selector
// items), §6.3 (worktree filter), §3.10 (CAPITAL filter).
//
// The separator is `sessionSep` from text.go, and there is exactly ONE
// definition of it: the frecency lookup, the current-session pin and fzf's
// --delimiter must all agree, and a second copy is how they stop agreeing.
package main

import (
	"regexp"
	"sort"
	"strings"
	"time"
)

// capitalNameRe is the CAPITAL filter of SPEC §3.10 step 2 (`.mjs:384`),
// `^[A-Z0-9_\-\s]+$`. As in text.go, JavaScript's `\s` is spelled out: Go's `\s`
// is only five ASCII characters and would reject names the .mjs accepts.
// Unlike sessionNameRe this class DOES include \t\n\v\f\r, because no earlier
// rule filters them out here.
var capitalNameRe = regexp.MustCompile(
	`^[A-Z0-9_\-\x{0009}-\x{000D}\x{0020}\x{00A0}\x{1680}\x{2000}-\x{200A}\x{2028}\x{2029}\x{202F}\x{205F}\x{3000}\x{FEFF}]+$`)

// hasUpperRe is the second half of the same test: at least one A-Z.
var hasUpperRe = regexp.MustCompile(`[A-Z]`)

// getSessionsList returns every tmux session as one normalised row, ordered by
// frecency score, descending (SPEC §4.1).
//
// D3: no excludeCurrent, no TMUX_FZF_SWITCH_CURRENT — the current session is
// always in the list. Q4: TMUX_FZF_SESSION_FORMAT is deleted, so §4.1 step 2
// is gone.
func getSessionsList(current string, st frecencyState, now time.Time) ([]string, error) {
	// Step 1: validate the current session name, but only warn (SPEC §1.1).
	if current != "" {
		if err := assertValidSessionName(current); err != nil {
			logEvent("Warning: Current session name is invalid: " + err.Error())
		}
	}

	raw, err := tmuxListSessions()
	if err != nil {
		return nil, err
	}
	return orderByFrecency(normalizeAtColumns(raw), st, now), nil
}

// orderByFrecency sorts rows by frecency score, highest first (SPEC §4.1 step 6).
//
// sort.SliceStable, never sort.Slice. Every score is 0 on a fresh checkout, so
// with an unstable sort the whole list order would be arbitrary and the [1]..[9]
// shortcuts would move between runs.
func orderByFrecency(lines []string, st frecencyState, now time.Time) []string {
	out := make([]string, len(lines))
	copy(out, lines)

	scores := make(map[string]int, len(out))
	for _, line := range out {
		name := extractSessionName(line)
		if _, ok := scores[name]; ok {
			continue
		}
		scores[name] = score(st.selectedAt(name), now)
	}

	sort.SliceStable(out, func(i, j int) bool {
		return scores[extractSessionName(out[i])] > scores[extractSessionName(out[j])]
	})
	return out
}

// selectorItems builds the rows fzf actually shows (SPEC §4.2): the current
// session's own row first when it has one, otherwise the rows unchanged. No
// literal "[current]" row is ever added here — that belongs to `detach` only
// (pinCurrentRow).
//
// Numbering runs first, then the literal "[cancel]" row, so "[cancel]" never
// takes a number and under D3 the pinned current session is always "[1]".
func selectorItems(lines []string, current string) []string {
	items := make([]string, 0, len(lines)+1)
	if pinned := indexOfCurrentRow(lines, current); pinned >= 0 {
		items = append(items, lines[pinned])
		items = append(items, lines[:pinned]...)
		items = append(items, lines[pinned+1:]...)
	} else {
		items = append(items, lines...)
	}
	return append(addNumberPrefixes(items), "[cancel]")
}

// indexOfCurrentRow returns the position of the row that belongs to the current
// session, or -1 when there is none. The test is the same everywhere: the row
// starts with "<current> @ ".
func indexOfCurrentRow(lines []string, current string) int {
	if current == "" {
		return -1
	}
	prefix := current + sessionSep
	for i, line := range lines {
		if strings.HasPrefix(line, prefix) {
			return i
		}
	}
	return -1
}

// pinCurrentRow puts the current session's own row first, and falls back to the
// literal "[current]" row only when the current session has no row at all.
//
// This is the `detach` list of SPEC §3.14.1 (Q12 FIX). Adding "[current]"
// unconditionally would list the current session twice, once as "[current]" and
// once as its own row. No numbers and no "[cancel]": actionDetach adds those.
func pinCurrentRow(lines []string, current string) []string {
	out := make([]string, 0, len(lines)+1)
	if i := indexOfCurrentRow(lines, current); i >= 0 {
		out = append(out, lines[i])
		out = append(out, lines[:i]...)
		return append(out, lines[i+1:]...)
	}
	out = append(out, "[current]")
	return append(out, lines...)
}

// filterCapital keeps only rows whose session name is all-uppercase-ish
// (SPEC §3.10 step 2). Input order is preserved.
func filterCapital(lines []string) []string {
	out := []string{}
	for _, line := range lines {
		name := extractSessionName(line)
		if capitalNameRe.MatchString(name) && hasUpperRe.MatchString(name) {
			out = append(out, line)
		}
	}
	return out
}

// filterByWorktrees keeps rows whose session has at least one pane inside one of
// the worktree directories (SPEC §6.3). Input order is preserved; a session with
// no panes is dropped.
func filterByWorktrees(lines, worktrees []string, panePaths map[string][]string) []string {
	// Step 1: strip every trailing "/" from each worktree path.
	normalized := make([]string, 0, len(worktrees))
	for _, wt := range worktrees {
		normalized = append(normalized, strings.TrimRight(wt, "/"))
	}

	out := []string{}
	for _, line := range lines {
		paths := panePaths[extractSessionName(line)]
		if len(paths) == 0 {
			continue
		}
		if anyPathUnder(paths, normalized) {
			out = append(out, line)
		}
	}
	return out
}

// anyPathUnder is step 2 of §6.3: p == wt, or p starts with wt + "/".
// The "/" matters: /repo-backup must not count as being inside /repo.
func anyPathUnder(paths, worktrees []string) bool {
	for _, p := range paths {
		for _, wt := range worktrees {
			if p == wt || strings.HasPrefix(p, wt+"/") {
				return true
			}
		}
	}
	return false
}
