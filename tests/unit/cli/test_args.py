from session_zx.cli.args import parse_cli_args


def test_parse_cli_args_returns_none_and_empty_args_for_empty_argv() -> None:
    action, rest = parse_cli_args([])

    assert action is None
    assert rest == []


def test_parse_cli_args_returns_first_value_as_action_and_rest_as_strings() -> None:
    action, rest = parse_cli_args(["switch", "line", 42])

    assert action == "switch"
    assert rest == ["line", "42"]
