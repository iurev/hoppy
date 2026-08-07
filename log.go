// log.go — the append-only event log and its in-place rotation.
//
// SPEC §13, §13.2 (the ~20 events we keep) and §13.3 (the wipe bug we must fix).
//
// Line format, byte-identical to the .mjs:
//
//	<ISO-8601 UTC, milliseconds, Z> <space> <message> \n
//	2026-07-20T11:06:44.123Z action=switch: complete
//
// Go format string: "2006-01-02T15:04:05.000Z" on a UTC time.
//
// Failure policy: swallow every error. Logging must never break the tool, so
// logEvent returns nothing.
//
// Rotation, checked before every append:
//
//	stat; if size <= LOG_MAX_BYTES do nothing.
//	Else walk lines backwards, keeping newest, up to LOG_TRIM_TARGET bytes.
//	M10 fix rules:
//	  - never produce an empty result while lines still fit
//	  - if the newest line alone is over the target, keep THAT ONE line
//	  - if the newest line alone is over LOG_MAX_BYTES, truncate the LINE
//	  - write the trimmed file atomically (writeAtomic in state.go)
//
// Planned functions:
//
//	logEvent(msg string)
//	rotate(path string) error
//	trimLines(lines []string, target, max int) []string  -- pure, table-tested
//
// NOT IMPLEMENTED YET.
package main

const (
	logFileName = "session-zx.log"
	// LOG_MAX_BYTES = 256 * 1024
	logMaxBytes = 262144
	// LOG_TRIM_TARGET = floor(262144 * 0.8)
	logTrimTarget = 209715
	// logTimeLayout is the exact .mjs toISOString() shape.
	logTimeLayout = "2006-01-02T15:04:05.000Z"
)
