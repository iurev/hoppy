"""End-to-end tests for worktree-switch and popup-worktree-switch (SPEC §3.9).

The list is built from two sources: the git worktrees of the CURRENT pane's
directory, and the directory of every tmux pane. Only sessions with a pane
inside one of those worktrees are shown.
"""
import os
import time

from .helpers.workflow import (
    MSG_NOT_IN_GIT,
    MSG_NO_WORKTREE_SESSIONS,
    add_git_worktree,
    create_git_repo,
    create_repo_with_detached_git_dir,
    reset_dir,
)

REPO = "/tmp/zx_wt_repo"
FEATURE = "/tmp/zx_wt_feature"
OUTSIDE = "/tmp/zx_wt_outside"


def build_worktree_world():
    """Make a repo, a linked worktree, and one directory outside both."""
    create_git_repo(REPO)
    add_git_worktree(REPO, FEATURE, "feature")
    reset_dir(OUTSIDE)


def test_worktree_switch_lists_only_worktree_sessions(tmux):
    """Only sessions whose pane sits in a worktree of this repo are listed.

    Sessions: test_session (in the repo), wt_feat (in the linked worktree),
    wt_other (outside). So 2 of 3 are kept.

    Breaks if: the worktree filter stops filtering (wt_other would show up), if
    a real worktree session is dropped, if the '<kept>/<all>' header counts
    change, or if picking a row no longer switches the client.
    """
    build_worktree_world()
    os.system(f"tmux new-session -d -s wt_feat -c {FEATURE}")
    os.system(f"tmux new-session -d -s wt_other -c {OUTSIDE}")
    time.sleep(0.6)

    tmux.run_command(f"cd {REPO}")
    time.sleep(0.8)

    tmux.run_command("/app/session-zx worktree-switch")
    assert tmux.wait_for_text("Worktree sessions (2/3)", timeout=8), (
        f"Wrong or missing worktree header. Content:\n{tmux.get_output()}"
    )

    content = tmux.strip_ansi(tmux.get_output())
    assert "wt_feat @" in content, f"Worktree session missing. Content:\n{content}"
    assert "test_session @" in content, f"Repo session missing. Content:\n{content}"
    assert "wt_other @" not in content, (
        f"Session outside every worktree was listed. Content:\n{content}"
    )

    tmux.send_keys("wt_feat")
    time.sleep(0.5)
    tmux.press_enter()

    assert tmux.wait_for_session_switch("wt_feat", timeout=4), (
        f"Did not switch to wt_feat. Current: {tmux.get_current_session()}"
    )


def test_popup_worktree_switch_switches_session(tmux):
    """popup-worktree-switch opens the same filtered list inside a popup.

    Breaks if: the popup command or its inner action changes, if the popup
    never starts fzf, or if the pick stops switching the client.
    """
    build_worktree_world()
    os.system(f"tmux new-session -d -s wt_feat -c {FEATURE}")
    os.system(f"tmux new-session -d -s wt_other -c {OUTSIDE}")
    time.sleep(0.6)

    tmux.run_command(f"cd {REPO}")
    time.sleep(0.8)

    tmux.run_command("/app/session-zx popup-worktree-switch")
    assert tmux.wait_for_fzf_process(), "worktree popup did not start fzf"

    tmux.send_keys("wt_feat")
    time.sleep(0.5)
    tmux.press_enter()

    assert tmux.wait_for_session_switch("wt_feat", timeout=4), (
        f"Popup worktree switch failed. Current: {tmux.get_current_session()}"
    )


def test_worktree_switch_outside_git_repository_shows_message(tmux):
    """No git repo under the pane: tell the user and stop (SPEC §3.9 step 2).

    Breaks if: the empty-worktree-list guard goes away (a selector would open
    instead), or the message text changes.
    """
    reset_dir("/tmp/zx_not_a_repo")

    tmux.run_command("cd /tmp/zx_not_a_repo")
    time.sleep(0.8)
    tmux.run_command("/app/session-zx worktree-switch")

    assert tmux.wait_for_client_message(MSG_NOT_IN_GIT), (
        f"tmux never showed '{MSG_NOT_IN_GIT}'"
    )
    assert "Worktree sessions (" not in tmux.strip_ansi(tmux.get_output()), (
        f"A selector opened outside a git repository. Content:\n{tmux.get_output()}"
    )
    assert tmux.last_exit_code() == 0, "this path must exit 0"


def test_worktree_switch_without_matching_sessions_shows_message(tmux):
    """A repo whose worktree path holds no pane: tell the user and stop.

    `git init --separate-git-dir` makes `git worktree list` report the GIT DIR
    as the worktree path, so no tmux pane can be inside it and the filter drops
    every session (SPEC §3.9 step 5).

    Breaks if: the empty-filter guard goes away (a selector with only a
    '[cancel]' row would open), if the message text changes, or if
    filterSessionsByWorktrees stops filtering and lists sessions that hold no
    worktree pane.
    """
    create_repo_with_detached_git_dir("/tmp/zx_sep_work", "/tmp/zx_sep_gitdir")
    os.system("tmux new-session -d -s wt_elsewhere -c /tmp")
    time.sleep(0.6)

    tmux.run_command("cd /tmp/zx_sep_work")
    time.sleep(0.8)
    tmux.run_command("/app/session-zx worktree-switch")

    assert tmux.wait_for_client_message(MSG_NO_WORKTREE_SESSIONS), (
        f"tmux never showed '{MSG_NO_WORKTREE_SESSIONS}'"
    )
    assert "Worktree sessions (" not in tmux.strip_ansi(tmux.get_output()), (
        f"A selector opened with no matching session. Content:\n{tmux.get_output()}"
    )
    assert tmux.last_exit_code() == 0, "this path must exit 0"
