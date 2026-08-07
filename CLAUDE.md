you MUST use simple English B1; you MUST use simple conscise sentences.
you MUST use "uv" project manager for Python.

# Python and uv run only in Docker
you MUST NEVER run uv, python, python3, or pytest on this PC (the host).
this PC must never run uv.
you MUST run Python and uv ONLY inside Docker.
run tests and any Python/uv command like this:
  docker compose run --rm test                 # run the test suite (pytest)
  docker compose run --rm test pytest -k name  # run one test
  docker compose run --rm test uv sync         # any uv command
  docker compose build                         # rebuild after dep changes
a hook (.claude/hooks/block-host-python.py) blocks host uv/python/pytest. this is by design; do not bypass it.
