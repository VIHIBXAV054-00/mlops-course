"""Command-line entry point: argument parsing and printing. You do not need to read it.

    uv run python src/main.py next-batch               # Ex 2, 4: the next batch arrives
    uv run python src/main.py build-data               # Ex 2, 4: merge the arrived batches
    uv run python src/main.py verify-data              # Ex 3, 4, 7: what is on disk?
    uv run python src/main.py prepare                  # Ex 5: DVC stage 1
    uv run python src/main.py train                    # Ex 5-7: DVC stage 2
    uv run python src/main.py evaluate                 # Ex 5: DVC stage 3
    uv run python src/main.py runs-for-data            # Ex 6: query by data version
    uv run python src/main.py register                 # Week 3 mechanics
    uv run python src/main.py promote                  # Week 3 mechanics
    uv run python src/main.py trace                    # Ex 6: the full chain
"""

from __future__ import annotations

import argparse
import json

from . import pipeline
from .config import Settings, load_settings
from .datasets import batch_paths, build_measurements, file_md5, next_batch
from .dvc_meta import pointer_path, read_pointer, remote_object_key
from .registry import (
    latest_version,
    promote_to_staging,
    register_best_model,
    trace_alias,
)
from .tracking import mlflow_available, search_runs_by_data_version


def _rel(settings: Settings, path) -> str:
    """Path relative to the lab directory, for readable output."""
    try:
        return str(path.relative_to(settings.project_root))
    except ValueError:
        return str(path)


def cmd_next_batch(settings: Settings, args) -> None:
    """Copy the next batch from data/incoming/ to data/raw/."""
    arrived = next_batch(settings.incoming_dir, settings.raw_dir)
    if arrived is None:
        print("Every batch has arrived: data/incoming/ has no new file.")
        print()
        return
    rows = sum(1 for _ in arrived.open()) - 1
    print(f"{arrived.name} arrived: {rows} rows in {_rel(settings, arrived)}")
    print()
    print("Next: `make build-data` to merge the batches into the dataset.")
    print()


def cmd_build_data(settings: Settings, args) -> None:
    """Merge the batches in data/raw/ into data/measurements.csv."""
    batches = batch_paths(settings.raw_dir)
    rows = build_measurements(settings.raw_dir, settings.measurements_path)
    if not rows or not settings.measurements_path.exists():
        print("Not implemented yet — see the TODO in datasets.py (Exercise 2).")
        print()
        return
    names = ", ".join(path.name for path in batches)
    print(f"Built the dataset from {len(batches)} batch(es) ({names}): {rows} rows")
    print(f"  path : {_rel(settings, settings.measurements_path)}")
    print(f"  md5  : {file_md5(settings.measurements_path)}")
    print()
    print("Next: `dvc add data/measurements.csv` to record this version.")
    print()


def cmd_verify_data(settings: Settings, args) -> None:
    """Report what is on disk versus what the DVC pointer claims."""
    path = settings.measurements_path
    print("Workspace")
    if path.exists():
        rows = sum(1 for _ in path.open()) - 1
        print(f"  {path.name:<20} {rows} rows, md5 {file_md5(path)}")
    else:
        print(f"  {path.name:<20} ABSENT (run `make dvc-pull` or `make build-data`)")

    print("DVC pointer")
    try:
        out = read_pointer(path)
        print(f"  {pointer_path(path).name:<20} md5 {out['md5']}, {out['size']} bytes")
        print(f"  remote object        {remote_object_key(out['md5'])}")
        if path.exists():
            match = file_md5(path) == out["md5"]
            print(f"  workspace matches pointer: {match}")
    except (FileNotFoundError, ValueError) as error:
        print(f"  {error}")
    print()


def cmd_prepare(settings: Settings, args) -> None:
    result = pipeline.prepare(settings)
    print(
        f"prepare: {result['rows_in']} rows -> "
        f"{result['rows_train']} train / {result['rows_test']} test"
    )


def cmd_train(settings: Settings, args) -> None:
    result = pipeline.train(settings)
    print(f"train: wrote {result['model_path']}")
    if result["run_id"]:
        print(f"  MLflow run    : {result['run_id']}")
        print(f"  MLflow digest : {result['mlflow_digest']}")
        try:
            from .dvc_meta import pointer_md5

            md5 = pointer_md5(settings.measurements_path)
            print(f"  DVC md5       : {md5}")
        except FileNotFoundError:
            print("  (no DVC pointer yet — run `dvc add data/measurements.csv`)")
    else:
        print("  MLflow not reachable — model written, no run recorded.")
        print("  Start the stack with `make up` and re-run `make link`.")
    print()


def cmd_evaluate(settings: Settings, args) -> None:
    result = pipeline.evaluate(settings)
    print("evaluate:")
    print(json.dumps(result["metrics"], indent=2))
    if result["run_id"]:
        print(f"  metrics also logged to MLflow run {result['run_id']}")
    print()


def cmd_runs_for_data(settings: Settings, args) -> None:
    """Which runs trained on the data version currently checked out?"""
    from .dvc_meta import pointer_md5

    if not mlflow_available(settings):
        print("MLflow not reachable — start the stack with `make up`.")
        print()
        return
    md5 = pointer_md5(settings.measurements_path)
    print(f"Searching for runs with tags.dvc_md5 = '{md5}'")
    frame = search_runs_by_data_version(settings, md5)
    if frame.empty:
        print("  No runs found for this data version. Run `make link` first.")
        print()
        return
    columns = [c for c in ["run_id", "tags.mlflow.runName", "params.C",
                           "metrics.f1", "tags.git_commit"] if c in frame.columns]
    print(frame[columns].to_string(index=False))
    print()
    print(f"  {len(frame)} run(s).")
    print()


def cmd_register(settings: Settings, args) -> None:
    run_id = pipeline.read_run_id(settings)
    if not run_id:
        print("No MLflow run recorded yet. Run `make link` first (Exercise 6).")
        print()
        return
    version = register_best_model(settings, run_id)
    print(f"Registered {version.name} version {version.version}")
    print(f"  source run: {version.run_id}")
    print()


def cmd_promote(settings: Settings, args) -> None:
    if not mlflow_available(settings):
        print("MLflow not reachable — start the stack with `make up`.")
        print()
        return
    try:
        version = latest_version(settings)
    except RuntimeError as error:
        print(error)
        print()
        return
    promoted = promote_to_staging(settings, version.version)
    print(f"Version {promoted.version} now carries aliases: {list(promoted.aliases)}")
    print()


def cmd_trace(settings: Settings, args) -> None:
    """Print the traceability chain for the aliased model."""
    if not mlflow_available(settings):
        print("MLflow not reachable — start the stack with `make up`.")
        print()
        return
    chain = trace_alias(settings)
    print("── Traceability chain ──")
    print(f"1. Model URI    : {chain['model_uri']}")
    print(f"2. Version      : {chain['version']}  (aliases: {chain['aliases']})")
    print(f"3. Run          : {chain['run_id']}  ({chain['run_name']})")
    print(f"4. Git commit   : {chain['git_commit']}")
    print(f"5. Data version : {chain['dvc_md5']}")
    print(f"   Data location: {chain['dvc_url']}")
    print("6. Params:")
    print(json.dumps(chain["params"], indent=6))
    print()
    if not chain["dvc_md5"]:
        print("Step 5 is empty: this run was logged without a data version.")
        print("Implement dvc_link.py (Exercise 6), then run `make link`.")
        print()


COMMANDS = {
    "next-batch": cmd_next_batch,
    "build-data": cmd_build_data,
    "verify-data": cmd_verify_data,
    "prepare": cmd_prepare,
    "train": cmd_train,
    "evaluate": cmd_evaluate,
    "runs-for-data": cmd_runs_for_data,
    "register": cmd_register,
    "promote": cmd_promote,
    "trace": cmd_trace,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="week-04-dvc-introduction",
        description="Week 4 lab — DVC data versioning with Silo.",
    )
    parser.add_argument("command", choices=sorted(COMMANDS))
    args = parser.parse_args()

    settings = load_settings()
    try:
        COMMANDS[args.command](settings, args)
    except (FileNotFoundError, KeyError, RuntimeError, ValueError) as error:
        # Exit non-zero, so that `dvc repro` stops when a stage fails.
        print()
        print(f"Cannot run `{args.command}` yet:")
        print(f"  {error}")
        print()
        raise SystemExit(1)
