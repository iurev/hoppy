"""Parsing utilities."""


def parse_lines(text: str | None) -> list[str]:
    """Split text into trimmed non-empty lines."""
    if not text:
        return []

    return [line.strip() for line in text.split("\n") if line.strip()]

