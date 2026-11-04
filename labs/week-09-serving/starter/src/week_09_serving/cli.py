"""Command-line entry point (`uv run python src/main.py <command>`); you do not need to read it.

`validate` and `gate` exit 1 on a bad result, so `dvc repro` stops at that stage.
"""

from __future__ import annotations

import argparse
import json
import shlex
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
    """Build the versioned dataset from the git-committed raw batches."""
    rows = build_measurements(args.version, settings.raw_dir, settings.measurements_path)
    if not rows or not settings.measurements_path.exists():
        print("build-data wrote no rows: check data/raw/.")
        print()
        return
    print(f"Built dataset version {args.version}: {rows} rows")
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
        print(f"  {path.name:<20} ABSENT (run `make dvc-pull` or `make data-v2`)")

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
    """DVC stage 0: run the ingestion contract and write the verdict."""
    report = pipeline.validate(settings)
    print(format_report(report))
    print()
    print(f"  report: {_rel(settings, settings.validation_report_path)}")
    zeros = report.get("sentinel_zeros") or {}
    if zeros:
        print(f"  sentinel zeros still present: {zeros}")
        print("  The ingestion contract allows these (ge=0); the training contract")
        print("  does not (see `model-input`).")
    print()


def cmd_check_file(settings: Settings, args) -> None:
    """Validate any CSV against the ingestion contract, without writing a report."""
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


def cmd_model_input(settings: Settings, args) -> None:
    """Show the training contract failing, then passing, on the same data."""
    source = settings.measurements_path
    if not source.exists():
        raise FileNotFoundError(
            f"{source.name} is missing. Run `make dvc-pull` or `make data-v2`."
        )

    frame = read_raw(source)[MODEL_INPUT_COLUMNS]
    print(f"Sentinel zeros in {source.name}: {sentinel_counts(frame)}")
    print(f"  (columns treated as sentinel-bearing: {list(SENTINEL_COLUMNS)})")
    print()

    print("1. ModelInput on the raw frame, zeros intact")
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
    print(f"  {before['n_failure_cases']} violations -> {after['n_failure_cases']}.")
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
    else:
        print("  Rejected. The model was never called.")
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
            print("  MLflow's digest hashes parsed values; DVC's md5 hashes the file's bytes.")
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
    """The slice table that `evaluate` wrote, the same one the gate read."""
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
    """The three fairness gaps, per axis."""
    report = pipeline.read_slices(settings)
    if not report:
        print("No evaluation on record. Run `make repro` first.")
        print()
        return
    gated = settings.acceptance.get("fairness") or {}
    print(format_fairness(report.get("fairness") or {}, gated_axes=gated))
    print()


def cmd_gate(settings: Settings, args) -> None:
    """DVC stage 4: the go/no-go decision."""
    report = pipeline.gate(settings)
    print(format_gate(report))
    print()
    print(f"  report: {_rel(settings, settings.gate_report_path)}")
    print()


def cmd_baseline(settings: Settings, args) -> None:
    """The recorded champion scores that the gate compares against."""
    print(format_baseline(read_baseline(settings.baseline_path)))
    print()
    print(f"  file: {_rel(settings, settings.baseline_path)}")
    print()


def cmd_baseline_sync(settings: Settings, args) -> None:
    """Write the current champion's scores into `metrics/baseline.json`."""
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
    print(f"  {len(frame)} run(s) trained on this data version.")
    print()


def cmd_register(settings: Settings, args) -> None:
    run_id = pipeline.read_run_id(settings)
    if not run_id:
        print("No MLflow run recorded yet. Run `make link` first.")
        print()
        return
    # register_best_model calls pipeline.require_go, which raises GateFailed —
    # a RuntimeError — and main() turns that into a clean message and exit 1.
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
    # Check the gate first, so a NO-GO is reported even when the registry is empty.
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
        print("  `champion` moved too. Next: `make baseline-sync` to update metrics/baseline.json.")
    else:
        print("  `staging` moved; `champion` did not. `make promote-champion` moves both.")
    print()


def cmd_trace(settings: Settings, args) -> None:
    """Print the chain from the alias back to the run, the data and the gate verdict."""
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
        print("Read the skipped count on step 8 before the verdict.")
    print()


def cmd_gate_summary(settings: Settings, args) -> None:
    """The recorded gate verdict as markdown, for `$GITHUB_STEP_SUMMARY`."""
    report = pipeline.read_gate(settings)
    print(format_gate_markdown(report))


def cmd_flow(settings: Settings, args) -> None:
    """Run the training flow."""
    from .flows import training_flow
    from .tracking import prefect_available

    if not prefect_available(settings):
        raise RuntimeError(
            f"No Prefect server at {settings.prefect_api_url} — start the stack with "
            "`make up`."
        )

    verdict = training_flow(
        push=args.push,
        register_model_version=args.register,
        require_committed_params=args.require_committed,
    )
    print()
    print(f"flow finished — verdict {verdict.get('verdict', '?')}")


def cmd_serve(settings: Settings, args) -> None:
    """Serve `scheduled_flow` on a cron schedule until you press Ctrl-C."""
    from .flows import scheduled_flow

    print(f"Serving `diabetes-training-with-pull` on cron `{args.cron}`.")
    print(f"Open the UI at {settings.prefect_api_url.replace('/api', '')} to watch it.")
    print("Ctrl-C to stop.")
    scheduled_flow.serve(name="weekly-retrain", cron=args.cron)


def bake_values(verdict: str | None, run_id: str | None, champion) -> dict:
    """Exercise 4 — the values `make image` writes into the image.

    The image claims a registry version only when the champion was trained by
    the same run as the local `models/model.pkl`.
    """
    if champion is not None and champion.run_id == run_id:
        version, source = str(champion.version), "registry champion"
    elif champion is not None:
        version, source = "unknown", "local models/model.pkl (not the champion)"
    else:
        version, source = "unknown", "local models/model.pkl"
    return {
        "MODEL_VERSION": version,
        "RUN_ID": run_id or "unknown",
        "GATE_VERDICT": verdict or "unknown",
        "MODEL_SOURCE": source,
    }


def cmd_bake_info(settings: Settings, args) -> None:
    """Exercise 4 — print what `make image` bakes in, as `KEY=value` lines for the shell."""
    from . import registry

    verdict = pipeline.read_gate(settings).get("verdict")
    run_id = pipeline.read_run_id(settings)
    try:
        champion = registry.champion_version(settings)
    except Exception:  # noqa: BLE001 -- the stack being down is an ordinary state
        champion = None

    # Quoted, because the Makefile runs these lines with `eval`.
    for key, value in bake_values(verdict, run_id, champion).items():
        print(f"{key}={shlex.quote(str(value))}")


def cmd_bench(settings: Settings, args) -> None:
    """Exercise 3 — batch versus online, on the same rows and the same model."""
    from .bench import format_comparison, run_bench

    result = run_bench(settings)
    print()
    print(format_comparison(result["batch"], result["online"]))
    print()


def cmd_serve_api(settings: Settings, args) -> None:
    """Exercise 2 — run the FastAPI app with uvicorn."""
    import uvicorn

    port = args.port or 5541
    print(f"Serving on http://127.0.0.1:{port}  (docs at /docs)")
    uvicorn.run("week_09_serving.api:app", host="127.0.0.1", port=port, log_level="info")


def cmd_ci_explain(settings: Settings, args) -> None:
    """List the lab's workflows, the installed ones and the grader, and audit them."""
    root = Path(__file__).resolve().parents[2]
    repo = root
    while repo != repo.parent and not (repo / ".git").is_dir():
        repo = repo.parent

    lab = sorted((root / ".github" / "workflows").glob("*.yml"))
    installed = sorted((repo / ".github" / "workflows").glob("*.yml"))
    grader = sorted((repo / "scripts" / "templates").glob("autograde.yml"))

    print("Workflows authored in this lab (not executed until installed):")
    for path in lab:
        print(f"  {path.relative_to(root)}")
    if not lab:
        print("  none.")
    print()
    print("Workflows GitHub will actually run (repository root):")
    for path in installed:
        print(f"  {path.relative_to(repo)}")
    if not installed:
        print("  none — run `make install-ci`.")
    print()
    print("  GitHub runs only the workflows in .github/workflows at the repository root.")
    print()

    rows = audit(lab + installed + grader)
    print(format_audit(rows))


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
    "bench": cmd_bench,
    "bake-info": cmd_bake_info,
    "serve-api": cmd_serve_api,
    "flow": cmd_flow,
    "serve": cmd_serve,
    "gate-summary": cmd_gate_summary,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="week-09-serving",
        description="Week 9 lab — the pipeline, the flow, and the prediction service.",
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
        help="promote: move the `champion` alias too",
    )
    parser.add_argument("--push", action="store_true", help="flow: dvc push after the run")
    parser.add_argument("--register", action="store_true", help="flow: register on a GO")
    parser.add_argument("--require-committed", action="store_true", dest="require_committed",
                        help="flow: refuse an uncommitted params.yaml")
    parser.add_argument("--port", type=int, default=None, help="serve-api: port (default 5541)")
    parser.add_argument("--cron", default="0 3 * * 1", help="serve: schedule (default Mon 03:00)")
    args = parser.parse_args()

    settings = load_settings()
    try:
        COMMANDS[args.command](settings, args)
    except (FileNotFoundError, KeyError, RuntimeError, ValueError) as error:
        # A failed gate or a missing input is not a crash: print it and exit 1 so dvc repro stops.
        print()
        print(f"Cannot run `{args.command}` yet:")
        print(f"  {error}")
        print()
        raise SystemExit(1)
