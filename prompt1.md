You are planning a Python rewrite of an existing tmux/fzf CLI tool.

Context:
- Existing implementation: `session-zx.mjs`
- Existing integration tests: `tests/`
- Goal of the product: quickly switch and preview tmux sessions via fzf

Task (planning only):
- Create `plan.md` (or improve it if it already exists).
- Do not implement the Python rewrite yet.
- Do not modify production code or tests in this step; planning artifacts only.

Hard constraints:
- Architecture must be modular and SOLID.
- Functions should be very small, clearly named, and have at most one explicit branch (`if/else`) where practical (prefer guard clauses and composition).
- Plan for 100% test coverage (line + branch) for new Python code.
- Use Docker-based command strategy only; do not use `python` or `uv` directly in this repo.
- If you need docs, use web search and prefer primary sources (official docs/specs); include links.
- Enforce atomic commits:
  - 1 small function + its unit tests at 100% coverage = 1 commit
  - 1 fix for a broken behavior/test = 1 commit

`plan.md` must include:
1. Scope and non-goals for this phase.
2. Behavioral parity matrix: current `.mjs` behavior vs planned Python behavior.
3. Proposed package/module structure with responsibilities and dependency direction.
4. Function catalog:
   - function name
   - input/output contracts
   - side effects
   - decision points (must stay minimal)
5. End-to-end data flow (from user command to tmux/fzf interaction and result handling).
6. Error/edge-case strategy (missing tmux, empty sessions, canceled fzf, broken env, non-zero exits, etc.).
7. Testing strategy:
   - mapping of each planned function/module to tests
   - unit vs integration boundaries
   - coverage gating plan (100% line + branch) and Docker commands to enforce it
8. Incremental implementation phases with acceptance criteria per phase.
9. Risk register and mitigations.
10. Open questions/assumptions that must be resolved before coding.
11. Atomic commit strategy with concrete commit slicing rules for implementation and fixes.

Definition of done:
- `plan.md` is implementation-ready, specific, and executable by another engineer without ambiguity.
- The plan explicitly shows data flow and test coverage enforcement.
