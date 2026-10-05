"""Command-line entry point — one subcommand per lab exercise.

    uv run python src/main.py run                     # Exercises 1-2: one fully-logged run
    uv run python src/main.py sweep                   # Exercise 3: parent + six children
    uv run python src/main.py best [--metric roc_auc] # Exercise 4: server-side run search
    uv run python src/main.py register [--run-id ID]  # Exercise 5: register the run you chose
    uv run python src/main.py promote [--version N] [--reason TEXT]   # Exercise 6
    uv run python src/main.py trace                   # Exercise 6: walk the chain back
    uv run python src/main.py rollback --version N --reason TEXT      # Exercise 7
    uv run python src/main.py query --filter STR [--order-by STR]     # stretch
    uv run python src/main.py all                     # Exercises 1-6, in order (the default)

All printing lives here. The modules stay quiet so they remain testable.
"""

from __future__ import annotations

import argparse
import json

from .config import Settings, load_settings
from .data import build_dataset, load_dataframe
from .registry import (
    latest_version,
    load_aliased_model,
    promote_to_staging,
    register_best_model,
    roll_back,
    trace_alias,
)
from .tracking import (
    SWEEP_GRID,
    connect,
    find_best_run,
    format_comparison_table,
    log_training_run,
    query_runs,
    run_sweep,
    search_sweep_runs,
)


def _banner(settings: Settings) -> None:
    frame = load_dataframe(settings)
    print("Week 3 — MLflow experiment tracking and model registry")
    print("=" * 54)
    print(f"Dataset:          {settings.data_path.name} ({len(frame)} patients)")
    print(f"Diabetes rate:    {frame['outcome'].mean():.1%}")
    print(f"Random seed:      {settings.random_seed}")
    print(f"Tracking server:  {settings.mlflow_tracking_uri}")
    print(f"Experiment:       {settings.mlflow_experiment_name}")
    print(f"Registered model: {settings.registered_model_name}")
    print()


def cmd_run(settings: Settings, args: argparse.Namespace) -> None:
    """Exercises 1-2 — one deliberate, fully-instrumented run."""
    print("── Exercise 1-2: one fully-logged run ──")
    connect(settings)
    result = log_training_run(settings, "logreg", {"C": 1.0})
    print(f"Run name:  {result.run_name}")
    print(f"Run ID:    {result.run_id}")
    print("Metrics:")
    print(json.dumps(result.metrics, indent=2))
    print()
    print(f"Open the run: {settings.mlflow_tracking_uri}")
    print("  -> the Artifacts tab has plots/roc_curve.png and")
    print("     plots/confusion_matrix.png; the model has a populated Schema tab.")
    print()


def cmd_sweep(settings: Settings, args: argparse.Namespace) -> None:
    """Exercise 3 — the parameter sweep."""
    print(f"── Exercise 3: sweeping {len(SWEEP_GRID)} configurations ──")
    results = run_sweep(settings)
    for result in results:
        print(
            f"  {result.run_name:<26} "
            f"f1={result.metrics['f1']:.4f}  "
            f"roc_auc={result.metrics['roc_auc']:.4f}"
        )
    print()
    print(f"{len(results)} child runs logged under one parent run.")
    print("In the UI: select all the children -> Compare -> Parallel Coordinates.")
    print()


def cmd_best(settings: Settings, args: argparse.Namespace) -> None:
    """Exercise 4 — rank the latest sweep with a server-side query."""
    print(f"── Exercise 4: the latest sweep, ranked by {args.metric} ──")
    frame = search_sweep_runs(settings, metric=args.metric, min_f1=args.min_f1)
    print(format_comparison_table(frame))
    print()
    if not frame.empty:
        print(f"Top by {args.metric}: {frame.iloc[0]['run_id']}")
        print("Register the run YOU chose: make register RUN_ID=<run_id>")
        print()


def cmd_register(settings: Settings, args: argparse.Namespace) -> None:
    """Exercise 5 — register the run you chose in Exercise 4."""
    print("── Exercise 5: register a run's model ──")
    run_id = args.run_id
    if run_id is None:
        run_id = find_best_run(settings)
        print("No RUN_ID given, so registering the top-F1 run by default.")
        print("Exercise 4 asked whether that is the right choice: make register RUN_ID=<id>")
    version = register_best_model(settings, run_id)
    print(f"Registered:  {version.name}")
    print(f"Version:     {version.version}")
    print(f"Source run:  {version.run_id or '(none — this version cannot be traced)'}")
    print()


def cmd_promote(settings: Settings, args: argparse.Namespace) -> None:
    """Exercise 6 — promote a version, with the evidence and your reason."""
    print(f"── Exercise 6: promote to @{settings.model_alias} ──")
    version = args.version or latest_version(settings).version
    if args.version is None:
        print(f"No VERSION given, so promoting the newest one (version {version}).")
    if not args.reason:
        print('No REASON given. Record why: make promote VERSION=<n> REASON="..."')
    promoted = promote_to_staging(settings, version, reason=args.reason)
    print(f"Version {promoted.version} now carries aliases: {list(promoted.aliases)}")
    print("Governance tags:")
    print(json.dumps(promoted.tags, indent=2))
    print()


def _describe_commit(chain: dict) -> str:
    dirty = chain.get("git_dirty")
    if dirty == "false":
        return "(clean tree: this commit IS the code that ran)"
    if dirty == "true":
        return "(DIRTY tree: this commit is NOT the code that ran)"
    return "(tree state not recorded: nothing says this commit is the code that ran)"


def cmd_trace(settings: Settings, args: argparse.Namespace) -> None:
    """Exercise 6 — walk the traceability chain backwards."""
    print("── Exercise 6: traceability walk-back ──")
    chain = trace_alias(settings)
    print(f"1. Model URI:   {chain['model_uri']}")
    print(f"2. Version:     {chain['version']}  (aliases: {chain['aliases']})")
    print(f"3. Run ID:      {chain['run_id']}  ({chain['run_name']})")
    print(f"4. Git commit:  {chain['git_commit']}  {_describe_commit(chain)}")
    print("5. Params that produced it:")
    print(json.dumps(chain["params"], indent=6))
    print("   Version tags (the promotion evidence):")
    print(json.dumps(chain["version_tags"], indent=6))
    print()
    print(f"Take hop 4 yourself:  git diff --stat {chain['git_commit']} -- .")
    print()

    # The alias resolves through the artifact proxy — no Silo credentials here.
    model = load_aliased_model(settings)
    _, x_test, _, _ = build_dataset(settings)
    predictions = model.predict(x_test.head(5))
    print(f"Loaded via the alias and predicted 5 rows: {predictions.tolist()}")
    print()


def cmd_rollback(settings: Settings, args: argparse.Namespace) -> None:
    """Exercise 7 — move both aliases back to an earlier version."""
    print(f"── Exercise 7: roll @{settings.model_alias} back to version {args.version} ──")
    try:
        previous, restored = roll_back(settings, args.version, args.reason)
    except ValueError as refusal:
        print(f"Refused: {refusal}")
        print()
        raise SystemExit(1)
    print(f"Rolled back from version {previous} to version {restored.version}.")
    print(f"Version {restored.version} now carries aliases: {list(restored.aliases)}")
    print(f"Version {previous} is tagged with why — the registry keeps no alias history.")
    print()


def cmd_query(settings: Settings, args: argparse.Namespace) -> None:
    """Stretch — run any search_runs filter against the whole experiment."""
    print(f"── Query: {args.filter} ──")
    print(format_comparison_table(query_runs(settings, args.filter, args.order_by)))
    print()


def cmd_all(settings: Settings, args: argparse.Namespace) -> None:
    """Exercises 1-6, in order, with every choice left at its default."""
    defaults = build_parser().parse_args(["all"])
    for command in (cmd_run, cmd_sweep, cmd_best, cmd_register, cmd_promote, cmd_trace):
        command(settings, defaults)


COMMANDS = {
    "run": cmd_run,
    "sweep": cmd_sweep,
    "best": cmd_best,
    "register": cmd_register,
    "promote": cmd_promote,
    "trace": cmd_trace,
    "rollback": cmd_rollback,
    "query": cmd_query,
    "all": cmd_all,
}


def build_parser() -> argparse.ArgumentParser:
    """The argument parser, separate from main() so the tests can exercise it."""
    parser = argparse.ArgumentParser(
        prog="week-03-mlflow-integration",
        description="Week 3 lab — MLflow experiment tracking and model registry.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="all",
        choices=sorted(COMMANDS),
        help="which exercise to run (default: all)",
    )
    parser.add_argument(
        "--metric",
        default="f1",
        choices=["f1", "roc_auc", "accuracy", "recall", "precision"],
        help="best: the metric to rank by",
    )
    parser.add_argument("--min-f1", type=float, default=0.0, help="best: F1 threshold")
    parser.add_argument("--run-id", help="register: the run you chose in Exercise 4")
    parser.add_argument("--version", help="promote / rollback: the version to act on")
    parser.add_argument("--reason", help="promote / rollback: why, recorded as a tag")
    parser.add_argument("--filter", help="query: a search_runs filter string")
    parser.add_argument("--order-by", help="query: e.g. 'metrics.roc_auc DESC'")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "rollback" and not (args.version and args.reason):
        parser.error('rollback needs both: make rollback VERSION=<n> REASON="..."')
    if args.command == "query" and not args.filter:
        parser.error('query needs a filter: make query FILTER="metrics.recall > 0.55"')

    settings = load_settings()
    _banner(settings)
    COMMANDS[args.command](settings, args)
