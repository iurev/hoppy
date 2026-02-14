# Local Codex Guardrails

In this repository (`/home/yu/my/hoppy`), Codex must execute commands using only:

- `docker`
- `docker-compose`

Direct host commands are not allowed for project tasks in this folder.

Codex must not execute:

- `uv`
- `python`

These prohibitions are strict and apply even if approvals are bypassed or sandboxing is disabled.

If a task appears to require a disallowed command, Codex should stop and ask for a Docker-based alternative.
