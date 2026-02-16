"""CLI argument parsing helpers."""


def parse_cli_args(argv: list[object]) -> tuple[str | None, list[str]]:
    """Return action and remaining positional arguments from argv."""
    if not argv:
        return None, []

    return str(argv[0]), [str(value) for value in argv[1:]]
