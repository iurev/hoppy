// sessions.go — building and ordering the session list.
//
// Pure logic where possible: everything here takes already-fetched tmux output
// (or the `run` seam from tmux.go) and returns rows the fzf layer can display.
//
// Row shape (SPEC §4.1, §4.3): "[1] name @ 3 windows".
//
// Planned functions:
//
//	getSessionsList(current string) ([]string, error) -- SPEC §4.1; excludeCurrent is DELETED (D3)
//	columnFormat(lines []string, sep string) []string -- SPEC §4.1 step 5
//	orderByFrecency(lines []string, now time.Time, st *frecencyState) []string -- §4.1 step 6, SliceStable
//	selectorItems(lines []string, current string, includeCurrent bool) []string -- §4.2
//	filterCapital(lines []string) []string            -- SPEC §3.10 step 2
//	filterByWorktrees(lines []string, worktrees []string, panePaths map[string][]string) []string -- §6.3
//	attachedSessionNames() (map[string]bool, error)   -- §6.4, with the Q3 fix
//
// Notes for the implementer:
//   - Use sort.SliceStable. sort.Slice is NOT stable and ties must keep tmux order.
//   - reload-sessions must produce the SAME rows as the initial list (Q7 FIX):
//     current pinned to the top, [cancel] appended.
//
// NOT IMPLEMENTED YET.
package main

// Row separator used by tmux's -F format and by fzf's --delimiter.
// It is passed to fzf as a bare argv element: "--delimiter", " @ ".
// Never write it with quotes around it (SPEC §0.9.2).
const rowSep = " @ "
