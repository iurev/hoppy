from pathlib import Path

from session_zx.app.context import (
    AppContext,
    apply_env_defaults,
    build_app_context,
    load_runtime_env,
)


class StubEnvPort:
    def __init__(self, values: dict[object, object]) -> None:
        self.values = values
        self.paths: list[Path] = []

    def load_first_existing(self, paths: list[Path]) -> dict[object, object]:
        self.paths = list(paths)
        return self.values


def test_load_runtime_env_returns_empty_dict_when_loader_returns_no_values() -> None:
    env_port = StubEnvPort({})
    candidates = [Path("/tmp/one"), Path("/tmp/two")]

    loaded = load_runtime_env(env_port, candidates)

    assert loaded == {}
    assert env_port.paths == candidates


def test_load_runtime_env_normalizes_key_and_value_types_to_strings() -> None:
    env_port = StubEnvPort({"TMUX_FZF_BIN": "fzf", "COUNT": 3, 42: False})

    loaded = load_runtime_env(env_port, [Path("/tmp/.envs")])

    assert loaded == {
        "TMUX_FZF_BIN": "fzf",
        "COUNT": "3",
        "42": "False",
    }


def test_apply_env_defaults_sets_defaults_when_required_values_are_missing() -> None:
    resolved = apply_env_defaults({}, "(^_^)")

    assert resolved == {
        "TMUX_FZF_BIN": "fzf",
        "TMUX_FZF_OPTIONS": "",
        "FZF_DEFAULT_OPTS": "",
        "KAOMOJI_PREVIEW_TEXT": "(^_^)",
    }


def test_apply_env_defaults_treats_empty_values_as_missing() -> None:
    resolved = apply_env_defaults(
        {
            "TMUX_FZF_BIN": "",
            "TMUX_FZF_OPTIONS": "",
            "FZF_DEFAULT_OPTS": "",
            "TMUX_FZF_PREVIEW_OPTIONS": "",
        },
        "(x_x)",
    )

    assert resolved["TMUX_FZF_BIN"] == "fzf"
    assert resolved["TMUX_FZF_OPTIONS"] == ""
    assert resolved["FZF_DEFAULT_OPTS"] == ""
    assert resolved["KAOMOJI_PREVIEW_TEXT"] == "(x_x)"


def test_apply_env_defaults_keeps_existing_values_when_present() -> None:
    env = {
        "TMUX_FZF_BIN": "sk",
        "TMUX_FZF_OPTIONS": "--ansi",
        "FZF_DEFAULT_OPTS": "--layout=reverse",
        "TMUX_FZF_PREVIEW_OPTIONS": "--preview 'echo ok'",
        "KAOMOJI_PREVIEW_TEXT": "(o_o)",
    }

    resolved = apply_env_defaults(env, "(^_^)")

    assert resolved == env
    assert resolved is not env


def test_build_app_context_copies_inputs_and_keeps_action_and_deps() -> None:
    parsed_args = ("switch", ["first", "second"])
    env = {"TMUX_FZF_BIN": "fzf"}
    deps = object()

    context = build_app_context(parsed_args, deps, env)

    parsed_args[1].append("third")
    env["TMUX_FZF_OPTIONS"] = "--ansi"

    assert isinstance(context, AppContext)
    assert context.action == "switch"
    assert context.argv == ("first", "second")
    assert context.env == {"TMUX_FZF_BIN": "fzf"}
    assert context.deps is deps
