"""Offline tests for the command line and the git provenance it records.

No stack needed: these check that your choices from Exercises 4-7 actually
reach the code, and that the git helpers return tag-shaped strings.
"""

from week_03_mlflow_integration.cli import build_parser
from week_03_mlflow_integration.tracking import git_commit, git_dirty


def test_default_command_is_all() -> None:
    args = build_parser().parse_args([])
    assert args.command == "all"
    assert args.metric == "f1"
    assert args.run_id is None and args.version is None and args.reason is None


def test_register_takes_the_run_you_chose() -> None:
    args = build_parser().parse_args(["register", "--run-id", "abc123"])
    assert args.run_id == "abc123"


def test_promote_takes_version_and_reason() -> None:
    args = build_parser().parse_args(
        ["promote", "--version", "2", "--reason", "highest ROC-AUC"]
    )
    assert (args.version, args.reason) == ("2", "highest ROC-AUC")


def test_best_ranks_by_a_chosen_metric() -> None:
    assert build_parser().parse_args(["best", "--metric", "roc_auc"]).metric == "roc_auc"


def test_git_helpers_return_tag_values() -> None:
    assert git_commit()  # a short SHA, or "unknown" outside a checkout
    assert git_dirty() in {"true", "false", "unknown"}
