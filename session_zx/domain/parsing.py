"""Parsing utilities."""

import re


_NUMBER_PREFIX_PATTERN = re.compile(r"^\[\d+\] ")


def parse_lines(text: str | None) -> list[str]:
    """Split text into trimmed non-empty lines."""
    if not text:
        return []

    return [line.strip() for line in text.split("\n") if line.strip()]


def parse_env_output(raw: str) -> dict[str, str]:
    """Parse ``env`` command output into a key/value mapping."""
    parsed: dict[str, str] = {}
    for line in raw.split("\n"):
        if not line:
            continue

        key, separator, value = line.partition("=")
        if not separator:
            continue

        parsed[key] = value

    return parsed


def ensure_trailing_newline(text: str) -> str:
    """Return text with exactly one trailing newline boundary."""
    if text.endswith("\n"):
        return text

    return f"{text}\n"


def extract_session_name(row: str) -> str:
    """Extract the session name from a tmux/fzf row."""
    cleaned = _NUMBER_PREFIX_PATTERN.sub("", row, count=1)
    name, separator, _ = cleaned.partition(" @ ")
    if not separator:
        return cleaned

    return name


def parse_targets(selection: str | None, current_session: str) -> list[str]:
    """Parse selected lines into session targets."""
    lines = parse_lines(selection)
    if not lines or "[cancel]" in lines:
        return []

    return [
        target
        for target in (
            extract_session_name(line.replace("[current]", f"{current_session} @ ", 1))
            for line in lines
        )
        if target
    ]
