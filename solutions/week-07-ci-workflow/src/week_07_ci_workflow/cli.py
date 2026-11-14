"""Command-line entry point: one subcommand per pipeline stage. You do not need to read it.

    uv run python src/main.py validate                 # DVC stage 0
    uv run python src/main.py check-file --path P      # validate any CSV
    uv run python src/main.py model-input              # the training contract
    uv run python src/main.py prepare                  # DVC stage 1
    uv run python src/main.py train                    # DVC stage 2
    uv run python src/main.py evaluate                 # DVC stage 3: metrics and slices
    uv run python src/main.py slices                   # print the slice table
    uv run python src/main.py gate                     # DVC stage 4: go or no-go
    uv run python src/main.py fairness                 # the fairness gaps per axis
    uv run python src/main.py baseline                 # the recorded champion
    uv run python src/main.py baseline-sync            # score the champion again
    uv run python src/main.py predict [--payload ...]  # validate a request, then predict
    uv run python src/main.py build-data --version N   # build the dataset (make data-v2)
    uv run python src/main.py verify-data              # data on disk versus the DVC pointer
    uv run python src/main.py runs-for-data            # runs trained on this data version
    uv run python src/main.py register                 # register after a GO
    uv run python src/main.py promote [--champion]     # move the aliases
    uv run python src/main.py trace                    # the full chain
    uv run python src/main.py ci-explain               # the workflows and their action pins
    uv run python src/main.py gate-summary             # the gate verdict as Markdown, for the job summary

`validate` and `gate` exit non-zero on a bad outcome, because DVC runs them as stages.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import inference, pipeline
from .baseline import (
    baseline_from_registry,
    format_baseline,
    read_baseline,
    write_baseline,
)
from .config import Settings, load_settings
from .datasets import MAX_VERSION, build_measurements, file_md5
from .dvc_meta import pointer_path, read_pointer, remote_object_key
from .evaluation import format_slices
from .fairness import format_fairness
from .gates import format_gate, format_gate_markdown
from .schemas import MODEL_INPUT_COLUMNS, SENTINEL_COLUMNS, ModelInput, RawMeasurements
from .workflows import audit, format_audit
from .validation import (
    format_report,
    read_raw,
    sentinel_counts,
    to_nullable,
    validate_frame,
)
from .registry import (
    champion_version,
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


def cmd_build_data(settings: Settings, args) -> None:
    """Build the dataset from the committed raw batches."""
    rows = build_measurements(args.version, settings.raw_dir, settings.measurements_path)
    if not rows or not settings.measurements_path.exists():
        print("Nothing was built.")
        print()
        return
    print(f"Built dataset version {args.version}: {rows} rows")
    print(f"  path : {_rel(settings, settings.measurements_path)}")
    print(f"  md5  : {file_md5(settings.measurements_path)}")
    print()
    print("Next: `make verify-data` compares it with the DVC pointer.")
    print()


def cmd_verify_data(settings: Settings, args) -> None:
    """Report what is on disk versus what the DVC pointer claims."""
    path = settings.measurements_path
    print("Workspace")
    if path.exists():
        rows = sum(1 for _ in path.open()) - 1
        print(f"  {path.name:<20} {rows} rows, md5 {file_md5(path)}")
    else:
        print(f"  {path.name:<20} ABSENT (run `make data-v2`)")

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


def cmd_validate(settings: Settings, args) -> None:
    """DVC stage 0: run the ingestion contract and write the report.

    Exits 1 when the data fails; the report is written either way.
    """
    report = pipeline.validate(settings)
    print(format_report(report))
    print()
    print(f"  report: {_rel(settings, settings.validation_report_path)}")
    zeros = report.get("sentinel_zeros") or {}
    if zeros:
        print(f"  sentinel zeros still present: {zeros}")
        print("  The ingestion contract TOLERATES these (ge=0). The training")
        print("  contract does not — see `model-input`.")
    print()


def cmd_check_file(settings: Settings, args) -> None:
    """Validate any CSV against the ingestion contract, without writing a report. Exits 0 either way."""
    path = Path(args.path) if args.path else settings.quality_dir / "broken_batch.csv"
    if not path.is_absolute():
        candidate = settings.project_root / path
        path = candidate if candidate.exists() else path
    if not path.exists():
        raise FileNotFoundError(
            f"No such file: {path}. Run `scripts/sync_datasets.sh` from the "
            "repository root if data/quality/broken_batch.csv is missing."
        )

    frame = read_raw(path)
    report = validate_frame(frame, RawMeasurements, source=str(path.name))
    print(format_report(report, limit=40))
    print()
    if not report:
        return
    if not report["passed"]:
        print("  by check :", json.dumps(report["by_check"]))
        print("  by column:", json.dumps(report["by_column"]))
        print()
        print("  Two summaries because they answer different questions:")
        print("  'what rule broke' tells you how to fix the data;")
        print("  'which column'    tells you who to talk to.")
        print()


def cmd_model_input(settings: Settings, args) -> None:
    """Run `ModelInput` on the raw data and again after `to_nullable`."""
    source = settings.measurements_path
    if not source.exists():
        raise FileNotFoundError(
            f"{source.name} is missing. Run `make data-v2`."
        )

    frame = read_raw(source)[MODEL_INPUT_COLUMNS]
    print(f"Sentinel zeros in {source.name}: {sentinel_counts(frame)}")
    print(f"  (columns treated as sentinel-bearing: {list(SENTINEL_COLUMNS)})")
    print()

    print("1. ModelInput on the RAW frame — zeros intact")
    before = validate_frame(frame, ModelInput, source=f"{source.name} (raw)")
    print(format_report(before, limit=5))
    print()

    print("2. ModelInput after to_nullable — the same zeros, now nulls")
    after = validate_frame(
        to_nullable(frame), ModelInput, source=f"{source.name} (nullable)"
    )
    print(format_report(after))
    print()
    if not before or not after:
        return
    print(f"  {before['n_failure_cases']} violations -> "
          f"{after['n_failure_cases']}. Nothing was invented and nothing was")
    print("  filled in: `gt=0, nullable=True` means missing is honest, zero is")
    print("  a lie. Filling the nulls is the MODEL's job — see model.py.")
    print()


def cmd_predict(settings: Settings, args) -> None:
    """Validate a request payload, then predict — in that order."""
    named = {
        "example": inference.EXAMPLE_PAYLOAD,
        "illegal": inference.ILLEGAL_PAYLOAD,
        "swapped": inference.SWAPPED_PAYLOAD,
        "incomplete": inference.INCOMPLETE_PAYLOAD,
    }
    if args.payload in named:
        payload = named[args.payload]
        label = args.payload
    elif args.payload:
        payload = inference.load_payload(args.payload)
        label = "custom"
    else:
        payload = inference.EXAMPLE_PAYLOAD
        label = "example"

    print(f"payload ({label}): {json.dumps(payload)}")
    print()
    model_path = settings.models_dir / "model.pkl"
    result = inference.predict_one(payload, model_path)
    print(format_report(result["report"], limit=10))
    print()
    if not result["report"]:
        return
    if result["report"]["passed"]:
        print(f"  prediction  : {result['prediction']}")
        print(f"  probability : {result['probability']}")
        print()
        print("  The same schema object guarded the training data. That is the")
        print("  whole point — one contract, both boundaries.")
    else:
        print("  REJECTED. The model was never called.")
        print("  A model cannot tell you its input was nonsense; it answers")
        print("  anyway, confidently, and the metrics never mention it.")
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
            print()
            print("  These describe the same file and they do not match.")
            print("  MLflow's digest hashes PARSED VALUES of the first 10,000")
            print("  rows plus the row count and column names, truncated to 8")
            print("  characters. DVC's md5 hashes the FILE'S BYTES, all 32.")
            print("  Only one of them proves 'these exact bytes'.")
        except FileNotFoundError:
            print("  (no DVC pointer: data/measurements.csv.dvc is missing)")
    else:
        print("  MLflow not reachable — model written, no run recorded.")
        print("  Start the stack with `make up` and re-run `make link`.")
    print()


def cmd_evaluate(settings: Settings, args) -> None:
    result = pipeline.evaluate(settings)
    print("evaluate:")
    print(json.dumps(result["metrics"], indent=2))
    slices = result.get("slices") or {}
    if slices:
        n_groups = sum(len(g) for g in slices.get("slices", {}).values())
        print(
            f"  {n_groups} slice group(s) across "
            f"{len(slices.get('slices', {}))} axes -> "
            f"{_rel(settings, settings.slices_path)}"
        )
    if result["run_id"]:
        print(f"  metrics also logged to MLflow run {result['run_id']}")
    print()


def cmd_slices(settings: Settings, args) -> None:
    """Print the slice table that `evaluate` wrote. Exits 0."""
    report = pipeline.read_slices(settings)
    metrics = pipeline.read_metrics(settings)
    if not report and not metrics:
        print("No evaluation on record. Run `make repro` first.")
        print()
        return
    print(format_slices(report, metrics))
    print()
    if report:
        print("  Read `n` and `pos` before you read any metric on the same row.")
        print()


def cmd_fairness(settings: Settings, args) -> None:
    """Print the fairness gaps per axis. Exits 0."""
    report = pipeline.read_slices(settings)
    if not report:
        print("No evaluation on record. Run `make repro` first.")
        print()
        return
    gated = settings.acceptance.get("fairness") or {}
    print(format_fairness(report.get("fairness") or {}, gated_axes=gated))
    print()
    print("  Three gaps, and they disagree on purpose. Demographic parity asks")
    print("  whether we ACT equally often; equal opportunity asks whether we")
    print("  FIND the true cases equally often. A model can pass one and fail")
    print("  the other on the same rows, and no library will tell you which one")
    print("  your problem needs — that is a judgement about consequences.")
    print()
    print("  And the axes you cannot check: this dataset has no sex, ethnicity,")
    print("  income or clinic column. Every subject is female, of Pima heritage,")
    print("  at least 21. You cannot audit a group you did not record.")
    print()


def cmd_gate(settings: Settings, args) -> None:
    """DVC stage 4: print the verdict. Exits 1 on a NO-GO; the report is written either way."""
    report = pipeline.gate(settings)
    print(format_gate(report))
    print()
    print(f"  report: {_rel(settings, settings.gate_report_path)}")
    print()


def cmd_baseline(settings: Settings, args) -> None:
    """Print the recorded champion."""
    print(format_baseline(read_baseline(settings.baseline_path)))
    print()
    print(f"  file: {_rel(settings, settings.baseline_path)}")
    print("  The pipeline reads this FILE, never the registry. A stage whose")
    print("  result depends on a database in another container is not")
    print("  reproducible, and `dvc.lock` would be recording a lie.")
    print()


def cmd_baseline_sync(settings: Settings, args) -> None:
    """Rewrite `metrics/baseline.json` from the champion alias.

    This is the only command that reads the registry to set a threshold.
    """
    if not mlflow_available(settings):
        print("MLflow not reachable — start the stack with `make up`.")
        print()
        return
    previous = read_baseline(settings.baseline_path)
    try:
        payload = baseline_from_registry(settings)
    except Exception as error:  # noqa: BLE001 — reported, not swallowed
        print(f"Could not read {settings.registered_model_name}@"
              f"{settings.champion_alias}: {error}")
        print()
        print("  Nothing was written. Promote a champion first:")
        print("    make register && make promote-champion")
        print()
        return

    write_baseline(payload, settings.baseline_path)
    print(f"Baseline updated from {payload['source']} "
          f"(version {payload['model_version']})")
    print()
    for key in sorted(payload["metrics"]):
        before = (previous.get("metrics") or {}).get(key)
        after = payload["metrics"][key]
        if before is None:
            print(f"  {key:<12} {after:.4f}   (no previous value)")
        else:
            print(f"  {key:<12} {before:.4f} -> {after:.4f}  ({after - before:+.4f})")
    print()
    print("  The bar has moved. Re-run `make gate` and the SAME model can now")
    print("  be a NO-GO against a champion it used to beat. That is a ratchet,")
    print("  and it only turns one way — which is the point and also the risk.")
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
    print(f"  {len(frame)} run(s). This is the question Week 3 could not ask:")
    print("  not 'which run scored best' but 'which runs saw THIS data'.")
    print()


def cmd_register(settings: Settings, args) -> None:
    run_id = pipeline.read_run_id(settings)
    if not run_id:
        print("No MLflow run recorded yet. Run `make link` first.")
        print()
        return
    # A NO-GO raises GateFailed (a RuntimeError); `main` prints it and exits 1.
    version = register_best_model(settings, run_id)
    print(f"Registered {version.name} version {version.version}")
    print(f"  source run: {version.run_id}")
    print(f"  gate      : {version.tags.get('gate')} "
          f"(criteria v{version.tags.get('gate_criteria_version')})")
    print()


def cmd_promote(settings: Settings, args) -> None:
    if not mlflow_available(settings):
        print("MLflow not reachable — start the stack with `make up`.")
        print()
        return
    # Check the gate before the version lookup, so that a NO-GO is reported first.
    pipeline.require_go(settings)
    try:
        version = latest_version(settings)
    except RuntimeError as error:
        print(error)
        print()
        return
    promoted = promote_to_staging(settings, version.version, champion=args.champion)
    print(f"Version {promoted.version} now carries aliases: {list(promoted.aliases)}")
    if args.champion:
        print()
        print("  `champion` moved too. That alias is the bar every future model")
        print("  is measured against, so moving it is a deliberate act and not a")
        print("  side effect of promoting to staging. Next: `make baseline-sync`")
        print("  to write the new champion's scores into metrics/baseline.json,")
        print("  which is what the gate actually reads.")
    else:
        print()
        print("  `staging` moved; `champion` did not. Use `make promote-champion`")
        print("  to raise the bar — see the note in registry.promote_to_staging.")
    print()


def cmd_trace(settings: Settings, args) -> None:
    """Print the traceability chain from the alias to the gate verdict."""
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
    print(f"8. Gate         : {chain['gate'] or '(not recorded)'}"
          f"  (criteria v{chain['gate_criteria_version'] or '?'}, "
          f"{chain['gate_checks_failed'] or '0'} failed, "
          f"{chain['gate_checks_skipped'] or '0'} skipped)")
    champion = champion_version(settings)
    print(f"   Champion     : version {champion.version}" if champion
          else "   Champion     : (no champion alias set)")
    print()
    if not chain["dvc_md5"]:
        print("Step 5 is empty — the run was logged before the DVC linkage")
        print("existed. Run `make link` to create a run that records it.")
    elif not chain["data_validation"]:
        print("Step 6 is empty — the run predates the validation linkage.")
        print("Run `make link` to create a run that records the verdict.")
    elif not chain["gate"]:
        print("Step 8 is empty — the run predates the gate linkage.")
        print("Run `make repro` so the gate stage stamps its verdict on it.")
    else:
        print("Steps 6 and 8 are the two gates, and they answer opposite")
        print("questions. Step 6: was the DATA allowed IN? Step 8: is the MODEL")
        print("allowed OUT? Step 5 sits between them and says which bytes we")
        print("are talking about — a hash alone certifies garbage exactly as")
        print("confidently as it certifies gold.")
        print()
        print("Read the SKIPPED count on step 8 before you read the verdict. A")
        print("GO with eight unchecked criteria is a different claim from a GO")
        print("with none, and only one of them is reassuring.")
    print()


def cmd_gate_summary(settings: Settings, args) -> None:
    """Print the recorded gate verdict as Markdown, for `$GITHUB_STEP_SUMMARY`."""
    print(format_gate_markdown(pipeline.read_gate(settings)))


def cmd_ci_explain(settings: Settings, args) -> None:
    """List the lab's workflows, the ones GitHub runs, and their action pins."""
    root = Path(__file__).resolve().parents[2]
    repo = root
    while repo != repo.parent and not (repo / ".git").is_dir():
        repo = repo.parent

    lab = sorted((root / ".github" / "workflows").glob("*.yml"))
    installed = sorted((repo / ".github" / "workflows").glob("*.yml"))
    grader = sorted((repo / "scripts" / "templates").glob("autograde.yml"))

    print("Workflows in this lab (GitHub does not run them from here):")
    for path in lab:
        print(f"  {path.relative_to(root)}")
    if not lab:
        print("  none yet")
    print()
    print("Workflows GitHub runs (.github/workflows at the repository root):")
    for path in installed:
        print(f"  {path.relative_to(repo)}")
    if not installed:
        print("  none: run `make install-ci`")
    print()
    print(format_audit(audit(lab + installed + grader)))


COMMANDS = {
    "validate": cmd_validate,
    "check-file": cmd_check_file,
    "model-input": cmd_model_input,
    "predict": cmd_predict,
    "slices": cmd_slices,
    "fairness": cmd_fairness,
    "gate": cmd_gate,
    "baseline": cmd_baseline,
    "baseline-sync": cmd_baseline_sync,
    "build-data": cmd_build_data,
    "verify-data": cmd_verify_data,
    "prepare": cmd_prepare,
    "train": cmd_train,
    "evaluate": cmd_evaluate,
    "runs-for-data": cmd_runs_for_data,
    "register": cmd_register,
    "promote": cmd_promote,
    "trace": cmd_trace,
    "ci-explain": cmd_ci_explain,
    "gate-summary": cmd_gate_summary,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="week-07-ci-workflow",
        description="Week 7 lab — CI and CT workflows for the diabetes pipeline.",
    )
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument(
        "--version",
        type=int,
        default=MAX_VERSION,
        help=f"dataset version for build-data (1..{MAX_VERSION}; default {MAX_VERSION})",
    )
    parser.add_argument(
        "--path",
        default=None,
        help="CSV to validate with check-file (default: data/quality/broken_batch.csv)",
    )
    parser.add_argument(
        "--payload",
        default=None,
        help="predict: example|illegal|swapped|incomplete, a JSON string, or a .json path",
    )
    parser.add_argument(
        "--champion",
        action="store_true",
        help="promote: move the `champion` alias too, raising the bar",
    )
    args = parser.parse_args()

    settings = load_settings()
    try:
        COMMANDS[args.command](settings, args)
    except (FileNotFoundError, KeyError, RuntimeError, ValueError) as error:
        # RuntimeError covers ValidationFailed and GateFailed. Exit non-zero:
        # DVC runs these subcommands as stages.
        print()
        print(f"Cannot run `{args.command}` yet:")
        print(f"  {error}")
        print()
        raise SystemExit(1)
