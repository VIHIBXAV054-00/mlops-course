"""Command-line entry point: argument parsing and printing. You do not need to read it.

    uv run python src/main.py build-data               # Setup: merge the batches in data/raw/
    uv run python src/main.py verify-data              # what is on disk?
    uv run python src/main.py check-file PATH          # Ex 1, 2: check a CSV against RawMeasurements
    uv run python src/main.py model-input              # Ex 3: ModelInput before and after to_nullable
    uv run python src/main.py validate                 # Ex 4: DVC stage 0, the gate
    uv run python src/main.py prepare                  # DVC stage 1
    uv run python src/main.py train                    # DVC stage 2
    uv run python src/main.py evaluate                 # DVC stage 3
    uv run python src/main.py predict --payload NAME   # Ex 6: one request
    uv run python src/main.py runs-for-data            # runs trained on this data version
    uv run python src/main.py register                 # register the latest run's model
    uv run python src/main.py promote                  # move the aliases to it
    uv run python src/main.py trace                    # Ex 6: the full chain
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import inference, pipeline
from .config import Settings, load_settings
from .data import load_measurements
from .datasets import batch_paths, build_measurements, file_md5
from .dvc_meta import pointer_path, read_pointer, remote_object_key
from .registry import (
    latest_version,
    promote_to_staging,
    register_best_model,
    trace_alias,
)
from .schemas import MODEL_INPUT_COLUMNS, ModelInput, RawMeasurements
from .tracking import mlflow_available, search_runs_by_data_version
from .validation import (
    format_report,
    read_raw,
    sentinel_counts,
    to_nullable,
    validate_frame,
)


def _rel(settings: Settings, path) -> str:
    """Path relative to the lab directory, for readable output."""
    try:
        return str(path.relative_to(settings.project_root))
    except ValueError:
        return str(path)


def cmd_build_data(settings: Settings, args) -> None:
    """Merge the batches in data/raw/ into data/measurements.csv."""
    batches = batch_paths(settings.raw_dir)
    rows = build_measurements(settings.raw_dir, settings.measurements_path)
    names = ", ".join(path.name for path in batches)
    print(f"Built the dataset from {len(batches)} batch(es) ({names}): {rows} rows")
    print(f"  path : {_rel(settings, settings.measurements_path)}")
    print(f"  md5  : {file_md5(settings.measurements_path)}")
    print()


def cmd_verify_data(settings: Settings, args) -> None:
    """Report what is on disk versus what the DVC pointer claims."""
    path = settings.measurements_path
    print("Workspace")
    if path.exists():
        rows = sum(1 for _ in path.open()) - 1
        print(f"  {path.name:<20} {rows} rows, md5 {file_md5(path)}")
    else:
        print(f"  {path.name:<20} ABSENT (run `make build-data` or `make dvc-pull`)")

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


def cmd_check_file(settings: Settings, args) -> None:
    """Check any CSV against RawMeasurements and print the report. Writes no file."""
    path = Path(args.path) if args.path else settings.measurements_path
    if not path.is_absolute():
        path = settings.project_root / path
    if not path.exists():
        raise FileNotFoundError(f"No such file: {_rel(settings, path)}")

    frame = read_raw(path)
    report = validate_frame(frame, RawMeasurements, source=path.name)
    print(format_report(report, limit=40))
    if report["passed"]:
        print(f"  zeros in the sentinel columns: {sentinel_counts(frame)}")
    else:
        print()
        print("  by check :", json.dumps(report["by_check"]))
        print("  by column:", json.dumps(report["by_column"]))
    print()


def cmd_model_input(settings: Settings, args) -> None:
    """Check the dataset against ModelInput, before and after to_nullable."""
    source = settings.measurements_path
    if not source.exists():
        raise FileNotFoundError(f"{source.name} is missing. Run `make build-data`.")

    frame = load_measurements(source)[MODEL_INPUT_COLUMNS]
    print(f"Zeros in the sentinel columns: {sentinel_counts(frame)}")
    print()
    print("1. ModelInput on the data as it is")
    before = validate_frame(frame, ModelInput, source=source.name)
    print(format_report(before, limit=5))
    print()
    print("2. ModelInput after to_nullable")
    converted = to_nullable(frame)
    after = validate_frame(converted, ModelInput, source=f"{source.name}, converted")
    print(format_report(after, limit=5))
    print(f"  missing values now: {int(converted.isna().sum().sum())}")
    print()


def cmd_validate(settings: Settings, args) -> None:
    """DVC stage 0. Exits with code 1 when the data fails its contract."""
    report = pipeline.validate(settings)
    print(format_report(report))
    print(f"  report: {_rel(settings, settings.validation_report_path)}")
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

            print(f"  DVC md5       : {pointer_md5(settings.measurements_path)}")
        except FileNotFoundError:
            print("  (no DVC pointer yet — run `dvc add data/measurements.csv`)")
    else:
        print("  MLflow not reachable — model written, no run recorded.")
        print("  Start the stack with `make up` and run `make link`.")
    print()


def cmd_evaluate(settings: Settings, args) -> None:
    result = pipeline.evaluate(settings)
    print("evaluate:")
    print(json.dumps(result["metrics"], indent=2))
    if result["run_id"]:
        print(f"  metrics also logged to MLflow run {result['run_id']}")
    print()


def cmd_predict(settings: Settings, args) -> None:
    """Send one request to `inference.predict_one` and print what comes back."""
    if args.payload in inference.PAYLOADS:
        payload, label = inference.PAYLOADS[args.payload], args.payload
    else:
        payload, label = inference.load_payload(args.payload), "custom"

    print(f"request ({label}): {json.dumps(payload)}")
    result = inference.predict_one(payload, settings.models_dir / "model.pkl")
    if result["report"]:
        print(format_report(result["report"], limit=10))
    if result["prediction"] is None:
        print("  no prediction: the request was rejected")
    else:
        print(f"  prediction  : {result['prediction']}")
        print(f"  probability : {result['probability']}")
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
    columns = [c for c in ["run_id", "tags.mlflow.runName", "tags.data_validation",
                           "metrics.f1", "tags.git_commit"] if c in frame.columns]
    print(frame[columns].to_string(index=False))
    print()
    print(f"  {len(frame)} run(s).")
    print()


def cmd_register(settings: Settings, args) -> None:
    run_id = pipeline.read_run_id(settings)
    if not run_id:
        print("No MLflow run recorded yet. Run `make link` first.")
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
    print(f"6. Validation   : {chain['data_validation'] or '(not recorded)'}"
          f"  (contract v{chain['schema_version'] or '?'}, "
          f"{chain['n_failure_cases'] or '0'} failure case(s))")
    print("7. Params:")
    print(json.dumps(chain["params"], indent=6))
    print()
    if not chain["data_validation"]:
        print("Step 6 is empty: this run was logged before the validation tags existed.")
        print("Run `make link`, then `make register` and `make promote`.")
        print()


COMMANDS = {
    "build-data": cmd_build_data,
    "verify-data": cmd_verify_data,
    "check-file": cmd_check_file,
    "model-input": cmd_model_input,
    "validate": cmd_validate,
    "prepare": cmd_prepare,
    "train": cmd_train,
    "evaluate": cmd_evaluate,
    "predict": cmd_predict,
    "runs-for-data": cmd_runs_for_data,
    "register": cmd_register,
    "promote": cmd_promote,
    "trace": cmd_trace,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="week-05-data-validation",
        description="Week 5 lab — data contracts and a validation gate with Pandera.",
    )
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument(
        "path", nargs="?", default=None,
        help="check-file: the CSV to check (default: data/measurements.csv)",
    )
    parser.add_argument(
        "--payload", default="example",
        help="predict: example, illegal, swapped, incomplete, a JSON string or a .json file",
    )
    args = parser.parse_args()

    settings = load_settings()
    try:
        COMMANDS[args.command](settings, args)
    except (FileNotFoundError, KeyError, RuntimeError, ValueError) as error:
        # Exit non-zero, so that `dvc repro` stops when a stage fails.
        print()
        print(f"Cannot run `{args.command}`:")
        print(f"  {error}")
        print()
        raise SystemExit(1)
