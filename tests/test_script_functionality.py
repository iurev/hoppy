"""Test the reload-sessions stdout contract.

Focuses on:
- Output formatting (real [N] number prefixes, ' @ ' delimiter, window counts)
- Session listing accuracy
- Handling of special characters
- The Q7 FIX: reload-sessions ends with a [cancel] row (SPEC §3.3)
"""
import os
import re
import time

# A numbered row looks exactly like this (SPEC §4.1, §4.3).
ROW_RE = re.compile(r"^\[(\d+)\] (.+) @ (\d+) windows$")


def run_script_reload():
    """Run the script's reload-sessions action and return output."""
    return os.popen("/app/session-zx reload-sessions").read()


def reload_rows():
    """Run reload-sessions and return its non-empty rows."""
    return [line for line in run_script_reload().split("\n") if line.strip()]


def test_script_lists_sessions_correctly():
    """reload-sessions prints real '[N] name @ K windows' rows.

    Breaks if: the number prefixes go away or stop counting from 1, the ' @ '
    delimiter or the 'N windows' suffix changes, or a session is dropped.
    (The old version only checked that '[' and ']' appeared somewhere, which
    the '[cancel]' row alone satisfied.)
    """
    os.system("tmux new-session -d -s script_test_alpha")
    os.system("tmux new-session -d -s script_test_beta")
    time.sleep(0.5)

    try:
        rows = reload_rows()

        assert rows[-1] == "[cancel]", f"Last row must be '[cancel]'. Rows: {rows}"

        numbered = rows[:-1]
        assert len(numbered) == 2, f"Expected 2 session rows. Rows: {rows}"

        matches = [ROW_RE.match(row) for row in numbered]
        assert all(matches), (
            f"Every row must look like '[N] name @ K windows'. Rows: {rows}"
        )
        assert [m.group(1) for m in matches] == ["1", "2"], (
            f"Number prefixes must be [1] then [2]. Rows: {rows}"
        )
        assert {m.group(2) for m in matches} == {
            "script_test_alpha", "script_test_beta",
        }, f"Wrong session names. Rows: {rows}"

    finally:
        os.system("tmux kill-session -t script_test_alpha 2>/dev/null")
        os.system("tmux kill-session -t script_test_beta 2>/dev/null")


def test_script_shows_window_counts():
    """Test that the script shows accurate window counts.

    Breaks if: the tmux format string stops asking for #{session_windows}, or
    the count is rendered differently.
    """
    os.system("tmux new-session -d -s window_test")
    time.sleep(0.3)
    # Add 2 more windows (total 3)
    os.system("tmux new-window -t window_test")
    os.system("tmux new-window -t window_test")
    time.sleep(0.3)

    try:
        output = run_script_reload()

        # The output format is like "[1] window_test @ 3 windows"
        assert "window_test @ 3 windows" in output, (
            f"Expected 'window_test @ 3 windows' in output, got:\n{output}"
        )

    finally:
        os.system("tmux kill-session -t window_test 2>/dev/null")


def test_special_characters_handling():
    """Test handling of sessions with dashes, underscores and spaces.

    Breaks if: a name with a space or a dash is split, quoted or dropped while
    the row is built.
    """
    # tmux converts dots to underscores, so we test what persists
    names = ["test-dash", "test_underscore", "test with space"]

    for n in names:
        os.system(f"tmux new-session -d -s '{n}'")
    time.sleep(0.5)

    try:
        rows = reload_rows()
        found = {ROW_RE.match(row).group(2) for row in rows if ROW_RE.match(row)}

        for n in names:
            assert n in found, f"Session '{n}' not found in rows: {rows}"

    finally:
        for n in names:
            os.system(f"tmux kill-session -t '{n}' 2>/dev/null")


def test_reload_sessions_ends_with_cancel_row():
    """Q7 FIX: reload-sessions prints the SAME rows as the initial switch list.

    The .mjs printed no '[cancel]' row here, so the list changed shape after the
    first DEL press. The Go port appends it (SPEC §3.3). Run from OUTSIDE tmux,
    so no literal '[current]' row is ever added either.

    Breaks if: the '[cancel]' row is dropped again, a '[current]' row appears,
    or a session goes missing from the list.
    """
    os.system("tmux new-session -d -s current_one")
    os.system("tmux new-session -d -s other_one")
    time.sleep(0.5)

    try:
        rows = reload_rows()

        assert rows[-1] == "[cancel]", (
            f"reload-sessions must end with a '[cancel]' row. Rows: {rows}"
        )
        assert "[current]" not in rows, (
            f"reload-sessions must never add a '[current]' row. Rows: {rows}"
        )

        names = {ROW_RE.match(row).group(2) for row in rows if ROW_RE.match(row)}
        assert names == {"current_one", "other_one"}, (
            f"Expected both sessions and nothing else. Rows: {rows}"
        )

    finally:
        os.system("tmux kill-session -t current_one 2>/dev/null")
        os.system("tmux kill-session -t other_one 2>/dev/null")
