"""Command-line entry point: one subcommand per pipeline stage and lab command.

`dvc.yaml` and the Makefile call these subcommands. Run with `--help` for the list.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
from pathlib import Path

import pandas as pd

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
    """DVC stage 0: run the ingestion contract, write the report, exit 1 on failure."""
    report = pipeline.validate(settings)
    print(format_report(report))
    print()
    print(f"  report: {_rel(settings, settings.validation_report_path)}")
    zeros = report.get("sentinel_zeros") or {}
    if zeros:
        print(f"  sentinel zeros still present: {zeros}")
        print("  The ingestion contract allows these (ge=0). The training")
        print("  contract does not: see `model-input`.")
    print()


def cmd_check_file(settings: Settings, args) -> None:
    """Validate any CSV against the ingestion contract. Exits 0 even when it fails."""
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

    print("2. ModelInput after to_nullable, the same zeros now nulls")
    after = validate_frame(
        to_nullable(frame), ModelInput, source=f"{source.name} (nullable)"
    )
    print(format_report(after))
    print()
    if not before or not after:
        return
    print(f"  {before['n_failure_cases']} violations -> "
          f"{after['n_failure_cases']}. The model's imputer fills the nulls (model.py).")
    print()


def cmd_predict(settings: Settings, args) -> None:
    """Validate a request payload, then predict."""
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
        print("  REJECTED. The model was never called.")
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
            print("  (no DVC pointer yet: run `dvc add data/measurements.csv`)")
    else:
        print("  MLflow not reachable: model written, no run recorded.")
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
    """Print the slice table that `evaluate` wrote. Always exits 0."""
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
    """Print the three fairness gaps per axis. Always exits 0."""
    report = pipeline.read_slices(settings)
    if not report:
        print("No evaluation on record. Run `make repro` first.")
        print()
        return
    gated = settings.acceptance.get("fairness") or {}
    print(format_fairness(report.get("fairness") or {}, gated_axes=gated))
    print()


def cmd_gate(settings: Settings, args) -> None:
    """DVC stage 4: the go/no-go decision. Exits 1 on a NO-GO."""
    report = pipeline.gate(settings)
    print(format_gate(report))
    print()
    print(f"  report: {_rel(settings, settings.gate_report_path)}")
    print()


def cmd_baseline(settings: Settings, args) -> None:
    """Print the recorded champion baseline the gate compares against."""
    print(format_baseline(read_baseline(settings.baseline_path)))
    print()
    print(f"  file: {_rel(settings, settings.baseline_path)}")
    print()


def cmd_baseline_sync(settings: Settings, args) -> None:
    """Write the current champion's scores into metrics/baseline.json."""
    if not mlflow_available(settings):
        print("MLflow not reachable: start the stack with `make up`.")
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
    print("  The bar has moved. Re-run `make gate` to compare against it.")
    print()


def cmd_runs_for_data(settings: Settings, args) -> None:
    """Which runs trained on the data version currently checked out?"""
    from .dvc_meta import pointer_md5

    if not mlflow_available(settings):
        print("MLflow not reachable: start the stack with `make up`.")
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
        print("No MLflow run recorded yet. Run `make link` first.")
        print()
        return
    # Raises GateFailed (a RuntimeError) on a NO-GO; main() turns it into exit 1.
    version = register_best_model(settings, run_id)
    print(f"Registered {version.name} version {version.version}")
    print(f"  source run: {version.run_id}")
    print(f"  gate      : {version.tags.get('gate')} "
          f"(criteria v{version.tags.get('gate_criteria_version')})")
    print()


def cmd_promote(settings: Settings, args) -> None:
    if not mlflow_available(settings):
        print("MLflow not reachable: start the stack with `make up`.")
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
        print()
        print("  `champion` moved too. Next: `make baseline-sync` to write its scores")
        print("  into metrics/baseline.json, which the gate reads.")
    else:
        print()
        print("  `staging` moved, `champion` did not. Use `make promote-champion`")
        print("  to raise the bar.")
    print()


def cmd_trace(settings: Settings, args) -> None:
    """Print the traceability chain from model alias back to data bytes."""
    if not mlflow_available(settings):
        print("MLflow not reachable: start the stack with `make up`.")
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
        print("Step 5 is empty: the run was logged before the DVC linkage")
        print("existed. Run `make link` to create a run that records it.")
    elif not chain["data_validation"]:
        print("Step 6 is empty: the run predates the validation linkage.")
        print("Run `make link` to create a run that records the verdict.")
    elif not chain["gate"]:
        print("Step 8 is empty: the run predates the gate linkage.")
        print("Run `make repro` so the gate stage stamps its verdict on it.")
    else:
        print("Read the skipped count on step 8 before you read the verdict.")
    print()


def cmd_gate_summary(settings: Settings, args) -> None:
    """Print the recorded gate verdict as markdown, for `$GITHUB_STEP_SUMMARY`."""
    report = pipeline.read_gate(settings)
    print(format_gate_markdown(report))


def cmd_flow(settings: Settings, args) -> None:
    """Run the Prefect training flow."""
    from .flows import training_flow
    from .tracking import prefect_available

    if not prefect_available(settings):
        raise RuntimeError(
            f"No Prefect server at {settings.prefect_api_url}: start the stack with "
            "`make up`."
        )

    verdict = training_flow(
        settings=settings,
        push=args.push,
        register_model_version=args.register,
    )
    print()
    print(f"flow finished — verdict {verdict.get('verdict', '?')}")


def cmd_flow_params(settings: Settings, args) -> None:
    """Run the flow with a runtime override, then restore params.yaml."""
    from .flows import demo_parameterised
    from .tracking import prefect_available

    if not prefect_available(settings):
        raise RuntimeError(
            f"No Prefect server at {settings.prefect_api_url} — start it with `make up`."
        )

    overrides = {}
    if args.C is not None:
        overrides["C"] = args.C
    if args.impute_strategy:
        overrides["impute_strategy"] = args.impute_strategy
    if args.family:
        overrides["family"] = args.family
    if not overrides:
        raise ValueError("pass at least one of --C, --impute-strategy, --family")

    verdict = demo_parameterised(settings, **overrides)
    print()
    print(f"flow finished with {overrides} — verdict {verdict.get('verdict', '?')}")
    print("params.yaml restored (a real scheduled run would leave it changed).")


def cmd_serve(settings: Settings, args) -> None:
    """Serve the training flow as a scheduled Prefect deployment."""
    from .flows import scheduled_flow

    print(f"Serving `diabetes-training-with-pull` on cron `{args.cron}`.")
    print(f"Open the UI at {settings.prefect_api_url.replace('/api', '')} to watch it.")
    print("Ctrl-C to stop.")
    scheduled_flow.serve(name="weekly-retrain", cron=args.cron)


def cmd_bake_info(settings: Settings, args) -> None:
    """Print what `make image` bakes in, as `KEY=value` lines for the shell."""
    from . import registry

    verdict, run_id, version = "unknown", "unknown", "unknown"

    report = pipeline.read_gate(settings)
    if report:
        verdict = report.get("verdict", "unknown")

    run_id = pipeline.read_run_id(settings) or "unknown"

    # Without the registry, bake the local model and say so in MODEL_SOURCE.
    source = "local models/model.pkl"
    try:
        champion = registry.champion_version(settings)
        if champion is not None:
            version = str(champion.version)
            source = "registry champion"
    except Exception:  # noqa: BLE001 -- the stack being down is an ordinary state
        pass

    # Quoted, because the Makefile `eval`s these lines and a value may contain spaces.
    for key, value in (
        ("MODEL_VERSION", version),
        ("RUN_ID", run_id),
        ("GATE_VERDICT", verdict),
        ("MODEL_SOURCE", source),
    ):
        print(f"{key}={shlex.quote(str(value))}")


def cmd_bench(settings: Settings, args) -> None:
    """Compare batch and online scoring on the same rows and model."""
    from .bench import format_comparison, run_bench

    result = run_bench(settings)
    print()
    print(format_comparison(result["batch"], result["online"]))
    print()


def cmd_serve_api(settings: Settings, args) -> None:
    """Run the FastAPI app with uvicorn."""
    import uvicorn

    port = args.port or 5541
    print(f"Serving on http://127.0.0.1:{port}  (docs at /docs)")
    uvicorn.run("week_12_drift_monitoring.api:app", host="127.0.0.1", port=port, log_level="info")


# ── Rollout ──────────────────────────────────────────────────────────────────


def cmd_model_publish(settings: Settings, args) -> None:
    """Put a model version in the store the cluster fetches from."""
    from .rollout import format_versions, list_versions, publish_version

    version = args.store_version or "v1"
    result = publish_version(version, settings=settings, force=args.force)
    print()
    print(f"published {result.version} -> {result.path}")
    if result.forced:
        print()
        print("  FORCED. The recorded gate verdict is "
              f"{result.provenance.get('gate_verdict')!r}, and it has been written into")
        print("  provenance.json, so the pod serving this model will admit it.")
    print()
    print(format_versions(list_versions(settings)))
    print()


def cmd_store_list(settings: Settings, args) -> None:
    """What is in the model store, and what each version claims to be."""
    from .rollout import format_versions, list_versions, store_dir

    print()
    print(f"  {store_dir(settings)}")
    print()
    print(format_versions(list_versions(settings)))
    print()


def _smoke_client(args):
    """A live endpoint if `--url` was given, otherwise this app, in-process."""
    if args.url:
        import httpx

        headers = {"Host": args.host} if args.host else None
        return httpx.Client(base_url=args.url, headers=headers, timeout=15.0), args.url
    from fastapi.testclient import TestClient

    from .api import create_app

    return TestClient(create_app()), "in-process (TestClient)"


def cmd_smoke(settings: Settings, args) -> None:
    """Run the smoke test against the endpoint. Exits 1 unless it passes."""
    from .smoke import DEFAULT_MIN_SPREAD, format_smoke, run_smoke

    client, where = _smoke_client(args)
    min_spread = args.min_spread if args.min_spread is not None else DEFAULT_MIN_SPREAD
    print()
    print(f"  target: {where}")
    report = run_smoke(client, expect_version=args.store_version, min_spread=min_spread)
    print(format_smoke(report))
    print()
    if report["verdict"] != "PASS":
        raise SystemExit(1)


def cmd_release_check(settings: Settings, args) -> None:
    """Is release.yaml complete?"""
    from .release import load_release, problems, release_path

    path = release_path(settings.project_root.resolve())
    release = load_release(path)
    found = problems(release)
    candidate = (release.get("model") or {}).get("candidate")
    provenance = settings.project_root / "model-store" / str(candidate) / "provenance.json"
    if not found and provenance.exists():
        verdict = json.loads(provenance.read_text()).get("gate_verdict")
        if verdict != "GO":
            found.append(f"`model.candidate` {candidate} has the gate verdict {verdict!r} in the store")
    print()
    if found:
        print(f"  {path.name} is not ready:")
        for problem in found:
            print(f"    - {problem}")
        print()
        raise SystemExit(1)
    print(f"  {path.name} is complete.")
    print()


def cmd_release_value(settings: Settings, args) -> None:
    """Print one value from release.yaml, for the Makefile."""
    from .release import load_release, release_path, value

    print(value(load_release(release_path(settings.project_root.resolve())), args.key))


def cmd_split_measure(settings: Settings, args) -> None:
    """Count which revision answered, one request at a time."""
    from .loadtest import format_split, run_load, summarise

    url = args.url or "http://127.0.0.1:5541"
    result = run_load(
        url,
        host=args.host,
        requests=args.requests or 200,
        concurrency=args.concurrency or 1,
    )
    print(format_split(summarise(result), declared=args.declared))
    print()


def cmd_loadtest(settings: Settings, args) -> None:
    """Send the same requests to the endpoint at rising concurrency."""
    from .loadtest import format_against_release, format_load_table, format_split, run_load, summarise

    url = args.url or "http://127.0.0.1:5541"
    levels = [int(c) for c in (args.concurrency_levels or "1,4,16,64").split(",")]
    requests = args.requests or 200
    rows = []
    for concurrency in levels:
        summary = summarise(run_load(url, host=args.host, requests=requests, concurrency=concurrency))
        rows.append(summary)
        last = summary
    print(f"  target: {url}   {requests} requests per level")
    print(format_load_table(rows))
    print()
    if args.max_p95_ms is not None and args.max_error_rate is not None:
        print(format_against_release(rows, args.max_p95_ms, args.max_error_rate))
    print(format_split(last))
    print()


# ── Observability ────────────────────────────────────────────────────────────


def cmd_metrics_show(settings: Settings, args) -> None:
    """Send a few requests in-process, then print the matching /metrics lines."""
    from fastapi.testclient import TestClient
    from prometheus_client import CollectorRegistry

    from .api import create_app
    from .loadtest import PROBE_PATIENT
    from .metrics import render

    registry = CollectorRegistry()
    client = TestClient(create_app(registry=registry))

    client.get("/health")
    for _ in range(3):
        client.post("/predict", json=PROBE_PATIENT)
    client.post("/predict", json={**PROBE_PATIENT, "glucose": 0.0})
    client.get("/does-not-exist")

    interesting = (
        args.filter
        or "http_requests_total|http_request_duration_seconds|model_"
    )
    pattern = re.compile(interesting)

    print()
    print("  5 requests sent in-process (3 valid, 1 contract violation, 1 unmatched path).")
    print(f"  Showing lines matching /{interesting}/. Drop --filter to see everything.")
    print()
    for line in render(registry).splitlines():
        if pattern.search(line):
            print("   ", line)
    print()


def cmd_traffic(settings: Settings, args) -> None:
    """Send traffic with a known mix and cohort to a running API."""
    from .traffic import DEFAULT_COHORT, generate, parse_mix

    url = args.url or f"http://127.0.0.1:{args.port or 5562}"
    mix = parse_mix(args.mix) if args.mix else {"valid": 0.9, "violation": 0.1}
    cohort = args.cohort or DEFAULT_COHORT
    print()
    print(f"  target : {url}")
    print(f"  mix    : {mix}   rate ~{args.rate or 20}/s   seed {args.seed}")
    print(f"  cohort : {cohort}")
    print()
    result = generate(
        url,
        count=args.requests or 300,
        mix=mix,
        rate=args.rate or 20.0,
        seed=args.seed,
        cohort=cohort,
    )
    print(result.summary())
    print()
    if result.errors:
        print("  Nothing was reachable. Is the API container up? `make api-up`.")
        raise SystemExit(1)


def cmd_slo_budget(settings: Settings, args) -> None:
    """Print the SLOs, their error budgets and the burn-rate table."""
    from .slo import format_report, load_slo

    print()
    print(format_report(load_slo()))
    print()


def cmd_cardinality(settings: Settings, args) -> None:
    """Count time series with the route template versus the raw path as the label."""
    from fastapi.testclient import TestClient
    from prometheus_client import CollectorRegistry

    from . import metrics as metrics_module
    from .api import create_app
    from .loadtest import PROBE_PATIENT

    def series_count(use_raw_path: bool, requests: int) -> tuple[int, set[str]]:
        registry = CollectorRegistry()
        original = metrics_module.route_label
        if use_raw_path:
            # Only the label value changes: the raw path instead of the template.
            metrics_module.route_label = lambda request: request.url.path
        try:
            client = TestClient(create_app(registry=registry))
            for index in range(requests):
                client.post("/predict", json=PROBE_PATIENT)
                client.get(f"/patients/{index}")
        finally:
            metrics_module.route_label = original
        names = {
            line.split("{")[0] + "{" + line.split("{", 1)[1].split("}")[0] + "}"
            for line in metrics_module.render(registry).splitlines()
            if line.startswith("http_requests_total{")
        }
        return len(names), names

    requests = args.requests or 50

    template_count, template_names = series_count(False, requests)
    raw_count, _ = series_count(True, requests)

    print()
    print(f"  {requests} POST /predict and {requests} GET /patients/<id>, twice over.")
    print()
    print(f"  route = the route TEMPLATE  ->  {template_count:>5} time series")
    for name in sorted(template_names):
        print(f"        {name}")
    print()
    print(f"  route = the RAW PATH        ->  {raw_count:>5} time series")
    print()
    growth = raw_count / template_count if template_count else float("inf")
    print(f"  {growth:.0f}x, from changing one expression.")
    print()


def cmd_alert_noise(settings: Settings, args) -> None:
    """Replay a simulated day past a naive latency alert and a burn-rate alert."""
    import random

    from .slo import load_slo

    doc = load_slo()
    latency_slo = doc.objective("latency")
    fast = next(alert for alert in doc.burn_alerts if alert.name == "fast")
    threshold = fast.threshold(latency_slo)

    rng = random.Random(args.seed)
    minutes = 24 * 60
    # Fraction of requests slower than the SLO threshold, per minute.
    day = []
    for minute in range(minutes):
        if 600 <= minute < 690:
            # The real incident: 90 minutes where most requests are slow.
            day.append(rng.uniform(0.80, 0.95))
        elif rng.random() < 0.03:
            # A one-minute spike that is over before anyone could act.
            day.append(rng.uniform(0.60, 0.99))
        else:
            day.append(rng.uniform(0.0, 0.04))

    naive_firings = 0
    naive_active = False
    for value in day:
        if value > latency_slo.error_budget and not naive_active:
            naive_firings += 1
            naive_active = True
        elif value <= latency_slo.error_budget:
            naive_active = False

    burn_firings = 0
    burn_active = False
    for minute in range(60, minutes):
        long_window = sum(day[minute - 60 : minute]) / 60
        short_window = sum(day[minute - 5 : minute]) / 5
        firing = long_window > threshold and short_window > threshold
        if firing and not burn_active:
            burn_firings += 1
        burn_active = firing

    print()
    print("  One simulated day (1440 minutes) against the same service:")
    print("  short spikes, plus one 90-minute incident at 10:00.")
    print()
    print(f"    naive   : p95 miss rate > {latency_slo.error_budget:.0%} right now")
    print(f"              -> fired {naive_firings} times")
    print(f"    burn    : 1h AND 5m miss rate > {threshold:.0%} ({fast.burn_rate}x budget)")
    print(f"              -> fired {burn_firings} time(s)")
    print()


def cmd_ci_explain(settings: Settings, args) -> None:
    """List the lab's workflows and the installed ones, then audit them."""
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
        print("  none yet.")
    print()
    print("Workflows GitHub will actually run (repository root):")
    for path in installed:
        print(f"  {path.relative_to(repo)}")
    if not installed:
        print("  none: run `make install-ci`.")
    print()
    print("  GitHub only runs workflows in .github/workflows at the repository root.")
    print()

    rows = audit(lab + installed + grader)
    print(format_audit(rows))


# ── Drift and degradation ────────────────────────────────────────────────────


REFERENCES = ("pinned", "unfiltered", "small", "log")
SMALL_REFERENCE_ROWS = 50


def _reference_window(settings: Settings, args, policy) -> pd.DataFrame:
    """The reference for `--reference`: the pinned one, or one of three bad choices."""
    from .drift import load_reference
    from .prediction_log import read_window

    choice = getattr(args, "reference", None) or "pinned"
    if choice not in REFERENCES:
        raise ValueError(f"unknown reference {choice!r}; expected one of {list(REFERENCES)}")
    if choice == "unfiltered":
        return load_reference(policy, settings.project_root, filtered=False)
    if choice == "small":
        pinned = load_reference(policy, settings.project_root)
        frame = pinned.sample(SMALL_REFERENCE_ROWS, random_state=args.seed)
        frame.attrs.update(pinned.attrs)
        frame.attrs["reference_rows_admissible"] = len(frame)
        return frame.reset_index(drop=True)
    if choice == "log":
        log_path = settings.project_root / "predictions/predictions.jsonl"
        frame = read_window(log_path, window_rows=policy.window_rows)
        if frame.empty:
            raise FileNotFoundError(
                f"{_rel(settings, log_path)} has no rows. Turn on the prediction log "
                f"and send traffic first:\n    make predictions-on && make traffic-drift"
            )
        frame.attrs["reference_path"] = str(log_path)
        frame.attrs["reference_rows_raw"] = len(frame)
        frame.attrs["reference_rows_admissible"] = len(frame)
        return frame
    return load_reference(policy, settings.project_root)


def _drift_windows(settings: Settings, args):
    """Return the policy, the reference, the current window and where it came from.

    `--cohort NAME` reads a committed batch CSV, otherwise the prediction log is read
    (and its age is returned as a fifth item).
    """
    from .drift_policy import contract_admissible, load_policy
    from .prediction_log import read_window, window_age_seconds

    policy = load_policy()
    reference = _reference_window(settings, args, policy)

    if getattr(args, "cohort", None):
        from .traffic import COHORTS

        name = args.cohort
        if name not in COHORTS:
            raise ValueError(
                f"unknown cohort {name!r}; expected one of {sorted(COHORTS)}. "
                f"(`probe` repeats one patient, so it has no distribution to compare.)"
            )
        path = settings.project_root / COHORTS[name]
        frame = contract_admissible(pd.read_csv(path))
        if args.requests:
            # Seeded sampling with replacement, so two sizes draw from the same experiment.
            frame = frame.sample(args.requests, replace=True, random_state=args.seed)
        return policy, reference, frame.reset_index(drop=True), f"cohort {name} ({path.name})"

    log_path = Path(args.path) if args.path else settings.project_root / "predictions/predictions.jsonl"
    frame = read_window(log_path, window_rows=policy.window_rows)
    age = window_age_seconds(frame)
    return policy, reference, frame, f"prediction log {_rel(settings, log_path)}", age


def cmd_drift_report(settings: Settings, args) -> None:
    """Exercise 2: compare the reference and current windows and write the drift report."""
    from .drift import build_report, format_report as format_drift, write_report
    from .prediction_log import window_age_seconds

    windows = _drift_windows(settings, args)
    policy, reference, current, source = windows[0], windows[1], windows[2], windows[3]
    age = windows[4] if len(windows) > 4 else None

    # Which model was serving when these rows were collected.
    provenance = {}
    gate_path = settings.gate_report_path
    if gate_path.exists():
        gate = json.loads(gate_path.read_text())
        provenance = {
            "gate_verdict": gate.get("verdict"),
            "model_family": gate.get("params", {}).get("family"),
        }
    run_id_path = settings.run_id_path
    if run_id_path.exists():
        provenance["run_id"] = json.loads(run_id_path.read_text()).get("run_id")

    degradation = None
    if getattr(args, "impact", False):
        from .drift import measure_degradation

        degradation = measure_degradation(
            settings.models_dir / "model.pkl",
            reference,
            current,
            primary_metric=policy.degradation_metric,
            min_drop=policy.degradation_min_drop,
        )

    print()
    print(f"  reference : {getattr(args, 'reference', None) or 'pinned'}, "
          f"{_rel(settings, Path(str(reference.attrs.get('reference_path'))))}")
    print(
        f"              {reference.attrs.get('reference_rows_admissible')} of "
        f"{reference.attrs.get('reference_rows_raw')} rows used"
    )
    print(f"  current   : {source}, {len(current)} rows")
    print()

    report = build_report(
        policy,
        reference,
        current,
        provenance=provenance,
        degradation=degradation,
        window_age_seconds=age if age is not None else window_age_seconds(current),
        html_path=settings.project_root / "reports/drift.html",
    )
    path = write_report(report, settings.project_root / "reports/drift.json")
    print(format_drift(report))
    print()
    print(f"  written to {_rel(settings, path)}")
    print()
    # Exits 0 even on a drift verdict: drift is a report, not a failed build.


def cmd_drift_policy(settings: Settings, args) -> None:
    """Print the parsed drift policy, with every threshold and its direction."""
    from .drift_policy import METHODS, load_policy

    policy = load_policy()
    print()
    print(f"Drift policy for `{policy.service}`")
    print()
    print(f"  reference   : {policy.reference_path}")
    print(f"                dataset md5 {policy.reference_md5}")
    print(f"  window      : the last {policy.window_rows} rows, at least {policy.min_samples}")
    print()
    print("  feature             method          threshold  drifts when  gated")
    print("  " + "-" * 66)
    for feature in policy.features:
        direction = "value <" if feature.smaller_is_drift else "value >"
        print(
            f"  {feature.column:<18}  {feature.method:<14}  {feature.threshold:<9}  "
            f"{direction:<11}  {'YES' if feature.gated else '-'}"
        )
    print()
    print("  methods available, and what each one answers:")
    for name, spec in sorted(METHODS.items()):
        print(f"    {name:<14} {spec['what']}")
    print()
    print(f"  proxy       : reference positive rate {policy.proxy_reference_rate:.4f}, "
          f"alert beyond ±{policy.proxy_max_deviation:.2f} over {policy.proxy_window}")
    print(f"  staleness   : expected every {policy.staleness_expected_every}, "
          f"stale after {policy.staleness_max_age} ({policy.staleness_severity})")
    print()
    print("  what happens next:")
    for verdict in ("insufficient", "no_drift", "drift", "drift_with_degradation"):
        action = policy.actions[verdict]
        print(f"    {verdict:<24} {action['severity']:<7} {' '.join(str(action['action']).split())}")
    print()


def cmd_drift_sample_size(settings: Settings, args) -> None:
    """Exercise 3: the same two distributions at four sample sizes, K-S versus PSI."""
    from .drift import compute_statistics, load_reference
    from .drift_policy import contract_admissible, load_policy
    from .traffic import COHORTS

    policy = load_policy()
    reference = load_reference(policy, settings.project_root)
    current_all = contract_admissible(
        pd.read_csv(settings.project_root / COHORTS["drifted"])
    )

    print()
    print("=== the same two distributions, sampled at four sizes ===")
    print()
    print("   n_current   glucose K-S p      verdict at 0.05    glucose psi     verdict at 0.15")
    print("  " + "-" * 82)
    ks_policy = DriftPolicyProbe(policy, "ks", 0.05)
    psi_policy = DriftPolicyProbe(policy, "psi", 0.15)
    for n in (100, 200, 400, 800):
        sample = current_all.sample(n, replace=True, random_state=args.seed)
        ks = compute_statistics(reference, sample, ks_policy.policy).values["glucose"]
        psi = compute_statistics(reference, sample, psi_policy.policy).values["glucose"]
        print(
            f"   {n:<11} {ks:<17.3e} {'DRIFT' if ks < 0.05 else '-':<18} "
            f"{psi:<15.4f} {'DRIFT' if psi > 0.15 else '-'}"
        )
    print()


class DriftPolicyProbe:
    """A one-feature copy of a policy, so the experiments use the report's own code."""

    def __init__(self, policy, method: str, threshold: float, column: str = "glucose"):
        from dataclasses import replace

        from .drift_policy import FeaturePolicy

        self.policy = replace(
            policy,
            features=(
                FeaturePolicy(column=column, method=method, threshold=threshold, gated=True),
            ),
        )


def cmd_drift_impact(settings: Settings, args) -> None:
    """Exercise 4: score the model on the labelled cohorts."""
    from .drift import load_reference, measure_degradation
    from .drift_policy import contract_admissible, load_policy
    from .traffic import COHORTS

    policy = load_policy()
    reference = load_reference(policy, settings.project_root)
    model_path = settings.models_dir / "model.pkl"

    print()
    print("=== the model, scored on labelled windows ===")
    print()
    header = f"  {'window':<26} {'n':>5} {'pos':>7} {'acc':>7} {'prec':>7} {'rec':>7} {'f1':>7} {'auc':>7} {'pred+':>7}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    rows = []
    for name, path in COHORTS.items():
        current = contract_admissible(pd.read_csv(settings.project_root / path))
        result = measure_degradation(
            model_path,
            reference,
            current,
            primary_metric=policy.degradation_metric,
            min_drop=policy.degradation_min_drop,
        )
        if not rows:
            rows.append(("reference window (training)", result["reference"]))
        rows.append((f"{name} cohort", result["current"]))
        if name == "drifted":
            drifted_result = result

    for label, scores in rows:
        print(
            f"  {label:<26} {scores['n']:>5} {scores['n_positives'] / scores['n']:>7.4f} "
            f"{scores['accuracy']:>7.4f} {scores['precision']:>7.4f} {scores['recall']:>7.4f} "
            f"{scores['f1']:>7.4f} {scores['roc_auc']:>7.4f} {scores['selection_rate']:>7.4f}"
        )

    print()
    print("=== reference -> drifted cohort ===")
    print()
    print(f"    f1       {drifted_result['reference']['f1']:.4f} -> "
          f"{drifted_result['current']['f1']:.4f}    BETTER")
    print(f"    roc_auc  {drifted_result['reference']['roc_auc']:.4f} -> "
          f"{drifted_result['current']['roc_auc']:.4f}    WORSE")
    print()


def cmd_drift_protocol(settings: Settings, args) -> None:
    """Provided: print the reaction protocol, what happens after a drift signal."""
    from .drift_policy import load_policy

    policy = load_policy()
    print()
    print("=== the reaction protocol ===")
    print()
    print("  signal                      labels?   action                          why")
    print("  " + "-" * 92)
    rows = [
        ("input drift, one feature", "not needed",
         "TICKET: investigate in hours",
         "no action exists at 03:00"),
        ("input drift, every feature", "not needed",
         "TICKET, but suspect the PIPELINE",
         "the world rarely moves all at once"),
        ("proxy: prediction mix moved", "not needed",
         "TICKET: check traffic mix first",
         "confounded by who is calling you"),
        ("contract violations rising", "not needed",
         "TICKET: a caller changed",
         "Week 5's gate, in production"),
        ("drift + measured degradation", "REQUIRED",
         "PAGE, then ROLL BACK (Week 10)",
         "rollback needs no labels and no new model"),
        ("degradation, inputs unmoved", "REQUIRED",
         "concept drift. Retrain or retire.",
         "nothing here can see it without labels"),
        ("drift report went stale", "not needed",
         "TICKET: fix the MONITOR",
         "silence looks exactly like good news"),
    ]
    for signal, labels, action, why in rows:
        print(f"  {signal:<27} {labels:<9} {action:<31} {why}")
    print()
    print("=== the four responses, cheapest first ===")
    print()
    print("  1. Do nothing, and write down why.")
    print("  2. Roll back to the previous model version (needs no labels).")
    print("  3. Collect labels on a sample.")
    print("  4. Retrain, which needs labels for the drifted window and still passes")
    print("     the gate. See `make retrain-trigger`.")
    print()
    print("  Your severity choices, from drift.yaml:")
    for verdict in ("insufficient", "no_drift", "drift", "drift_with_degradation"):
        print(f"    {verdict:<24} {policy.actions[verdict]['severity']}")
    print()


def cmd_predictions_head(settings: Settings, args) -> None:
    """Exercise 1: print the last rows of the prediction log."""
    from .prediction_log import read_window, window_age_seconds

    path = Path(args.path) if args.path else settings.project_root / "predictions/predictions.jsonl"
    frame = read_window(path, window_rows=args.requests or 5)
    print()
    total = sum(1 for _ in path.open()) if path.exists() else 0
    print(f"  {_rel(settings, path)} — the last {len(frame)} of {total} rows")
    print()
    if frame.empty:
        print("  (empty. `make predictions-on` then `make traffic-drift`.)")
        print()
        return
    with pd.option_context("display.width", 200, "display.max_columns", 30):
        print(frame.to_string(index=False))
    print()
    age = window_age_seconds(frame)
    if age is not None:
        print(f"  newest row: {age:.1f}s old")
    skipped = frame.attrs.get("skipped_lines", 0)
    if skipped:
        print(f"  {skipped} malformed line(s) skipped (a file being appended to can end")
        print("  in a partial line).")
    print()


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
    "model-publish": cmd_model_publish,
    "store-list": cmd_store_list,
    "smoke": cmd_smoke,
    "release-check": cmd_release_check,
    "release-value": cmd_release_value,
    "split-measure": cmd_split_measure,
    "loadtest": cmd_loadtest,
    "metrics-show": cmd_metrics_show,
    "traffic": cmd_traffic,
    "slo-budget": cmd_slo_budget,
    "cardinality": cmd_cardinality,
    "alert-noise": cmd_alert_noise,
    "drift-report": cmd_drift_report,
    "drift-policy": cmd_drift_policy,
    "drift-sample-size": cmd_drift_sample_size,
    "drift-impact": cmd_drift_impact,
    "drift-protocol": cmd_drift_protocol,
    "predictions-head": cmd_predictions_head,
    "flow": cmd_flow,
    "flow-params": cmd_flow_params,
    "serve": cmd_serve,
    "gate-summary": cmd_gate_summary,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="week-12-drift-monitoring",
        description="Week 12 lab: drift and degradation.",
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
    parser.add_argument("--C", type=float, default=None, help="flow-params: override train.C")
    parser.add_argument("--impute-strategy", default=None, dest="impute_strategy",
                        help="flow-params: override train.impute_strategy")
    parser.add_argument("--family", default=None, help="flow-params: override train.family")
    parser.add_argument("--port", type=int, default=None, help="serve-api: port (default 5541)")
    parser.add_argument("--cron", default="0 3 * * 1", help="serve: schedule (default Mon 03:00)")
    # Separate from `--version`, which is the dataset version.
    parser.add_argument("--store-version", default=None, dest="store_version",
                        help="model-publish/smoke: the model store version, e.g. v2")
    parser.add_argument("--force", action="store_true",
                        help="model-publish: publish a model the gate refused")
    parser.add_argument("--url", default=None,
                        help="smoke/split-measure/loadtest: endpoint (default: in-process app)")
    parser.add_argument("--host", default=None,
                        help="Host header, for a KServe endpoint behind an ingress gateway")
    parser.add_argument("--requests", type=int, default=None, help="requests per level")
    parser.add_argument("--concurrency", type=int, default=None,
                        help="split-measure: requests in flight (default 1)")
    parser.add_argument("--concurrency-levels", default=None, dest="concurrency_levels",
                        help="loadtest: comma-separated levels (default 1,4,16,64)")
    parser.add_argument("--declared", type=int, default=None,
                        help="split-measure: the canaryTrafficPercent you asked for")
    parser.add_argument("--key", default=None,
                        help="release-value: a dotted key, e.g. canary.percent")
    parser.add_argument("--min-spread", type=float, default=None, dest="min_spread",
                        help="smoke: smoke.min_probability_spread from release.yaml")
    parser.add_argument("--max-p95-ms", type=float, default=None, dest="max_p95_ms",
                        help="loadtest: load.max_p95_ms from release.yaml")
    parser.add_argument("--max-error-rate", type=float, default=None, dest="max_error_rate",
                        help="loadtest: load.max_error_rate from release.yaml")
    parser.add_argument("--filter", default=None,
                        help="metrics-show: regex of exposition lines to print")
    parser.add_argument("--mix", default=None,
                        help="traffic: kind=weight pairs, e.g. 'valid=9,violation=1'")
    parser.add_argument("--rate", type=float, default=None,
                        help="traffic: requests per second (default 20)")
    parser.add_argument("--seed", type=int, default=42,
                        help="traffic/alert-noise/drift: random seed")
    parser.add_argument("--cohort", default=None,
                        help="traffic/drift-report: reference|drifted|probe (default reference)")
    parser.add_argument("--reference", default=None,
                        help="drift-report: pinned|unfiltered|small|log (default pinned)")
    parser.add_argument("--impact", action="store_true",
                        help="drift-report: also score the model on labels")
    args = parser.parse_args()

    settings = load_settings()
    try:
        COMMANDS[args.command](settings, args)
    except (FileNotFoundError, KeyError, RuntimeError, ValueError) as error:
        # A failed contract or a missing prerequisite: print it and exit 1, so a
        # DVC stage that calls this command fails too.
        print()
        print(f"Cannot run `{args.command}` yet:")
        print(f"  {error}")
        print()
        raise SystemExit(1)
