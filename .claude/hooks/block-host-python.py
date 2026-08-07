#!/usr/bin/env python3
"""PreToolUse hook: block running uv / python / pytest on the host.

Rule for THIS project: never run Python or uv on this PC directly.
Run them only inside Docker (docker compose / docker exec).

A Bash command is blocked when it invokes one of the guarded tools
(uv, uvx, python, python3, pytest) AND the command does not go through
docker. Docker commands are always allowed, so running uv/python INSIDE
a container is fine.
"""

import json
import re
import sys

GUARDED = re.compile(r"(?:^|[\s;&|/(])(uv|uvx|python3?|pytest)(?:\s|$)")


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # cannot parse -> do not block

    if data.get("tool_name") != "Bash":
        return 0

    command = data.get("tool_input", {}).get("command", "") or ""

    # Docker commands are allowed: uv/python may run inside a container.
    if re.search(r"(?:^|[\s;&|/])docker(?:-compose)?\b", command):
        return 0

    if not GUARDED.search(command):
        return 0

    msg = (
        "Blocked: this project must NEVER run uv/python/pytest on the host.\n"
        "Run them ONLY inside Docker. Examples:\n"
        "  docker compose run --rm test            # run the test suite\n"
        "  docker compose run --rm test pytest -k name\n"
        "  docker compose build                    # rebuild image after dep changes\n"
        "See CLAUDE.md ('Python and uv run only in Docker')."
    )
    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": msg,
        }
    }
    print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
