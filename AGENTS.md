# Local Gemini Guardrails

In this repository (`/home/yu/my/hoppy`), Gemini must not execute:

- `uv`
- `python`

These prohibitions are strict and apply even if approvals are bypassed or sandboxing is disabled.

If a task appears to require a disallowed command, Gemini should stop and ask for a Docker-based alternative.
