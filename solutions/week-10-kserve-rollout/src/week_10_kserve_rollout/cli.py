"""Command-line entry point — one subcommand per pipeline stage and exercise.

    uv run python src/main.py validate                 # Ex 1/4: DVC stage 0 - the gate
    uv run python src/main.py check-file --path P      # Ex 2: validate any CSV
    uv run python src/main.py model-input              # Ex 3: the training contract
    uv run python src/main.py prepare                  # DVC stage 1
    uv run python src/main.py train                    # DVC stage 2
    uv run python src/main.py evaluate                 # Ex 1: DVC stage 3 + slices
    uv run python src/main.py slices                   # Ex 1/2: read the slice table
    uv run python src/main.py gate                     # Ex 3/4: DVC stage 4 - go/no-go
    uv run python src/main.py fairness                 # Ex 5: the three gaps
    uv run python src/main.py baseline                 # Ex 6: the recorded champion
    uv run python src/main.py baseline-sync            # Ex 6: raise the bar
    uv run python src/main.py predict [--payload ...]  # Week 5 mechanics
    uv run python src/main.py build-data --version N   # Week 4 mechanics
    uv run python src/main.py verify-data              # Week 4 mechanics
    uv run python src/main.py runs-for-data            # Week 4 mechanics
    uv run python src/main.py register                 # gate-aware since Week 6
    uv run python src/main.py promote [--champion]     # gate-aware since Week 6
    uv run python src/main.py trace                    # the full chain, 8 steps

The `validate`/`prepare`/`train`/`evaluate`/`gate` subcommands are what
`dvc.yaml` invokes, so the pipeline and a human run exactly the same code.

Two of these deliberately exit NON-ZERO on a bad outcome — `validate` and
`gate` — because DVC runs them as stages and a stage that swallowed its own
failure would let `dvc repro` report success on a pipeline that refused. The
informational ones (`slices`, `fairness`, `baseline`, `check-file`) exit 0 even
when the news is bad: inspecting a problem is not itself a problem.
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
    """DVC stage 0 — run the ingestion contract and write the verdict.

    Raises (and therefore exits 1) when the data fails, which is what makes this
    a gate. The report is written either way.
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
    """Validate any CSV against the ingestion contract, without writing a report.

    Exercise 2 points this at the deliberately corrupted batch. It exits 0 even
    when the file fails, because inspecting a broken file is not itself an error
    — the point is to READ the report.
    """
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
    """Show the training contract failing, then passing, on the same data.

    This is Exercise 3's proof: the only difference between the two runs is
    `to_nullable`, and it changes 652 violations into none.
    """
    source = settings.measurements_path
    if not source.exists():
        raise FileNotFoundError(
            f"{source.name} is missing. Run `make dvc-pull` or `make data-v2`."
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
    """Exercise 1/2 — the slice table. Informational, always exits 0.

    Reads what `evaluate` already wrote rather than recomputing it, so the table
    a student reads is byte-for-byte the one the gate acted on. Recomputing here
    would be one line shorter and would let the two drift apart, which is the
    class of bug this whole course is about.
    """
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
    """Exercise 5 — the three gaps, per axis. Informational, always exits 0."""
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
    """Exercise 3/4 — DVC stage 4. The go/no-go decision.

    Exits NON-ZERO on a NO-GO, which is what stops `dvc repro` and what a CI job
    would notice. The report is written either way.
    """
    report = pipeline.gate(settings)
    print(format_gate(report))
    print()
    print(f"  report: {_rel(settings, settings.gate_report_path)}")
    print()


def cmd_baseline(settings: Settings, args) -> None:
    """Exercise 6 — what "worse than what we have" is measured against."""
    print(format_baseline(read_baseline(settings.baseline_path)))
    print()
    print(f"  file: {_rel(settings, settings.baseline_path)}")
    print("  The pipeline reads this FILE, never the registry. A stage whose")
    print("  result depends on a database in another container is not")
    print("  reproducible, and `dvc.lock` would be recording a lie.")
    print()


def cmd_baseline_sync(settings: Settings, args) -> None:
    """Exercise 6 — raise the bar, deliberately, from the current champion.

    The only place in this lab that reads the registry to decide something. It
    is a human command precisely because promoting a champion is a human
    decision: the new baseline lands in a file, in a commit, next to the data
    pointer and the metrics that justify it.
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
    # The gate is checked FIRST, before looking for a version. Otherwise a
    # NO-GO on a project with an empty registry reports "no versions
    # registered", which is true, unhelpful, and hides the actual refusal.
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
    """The full chain — now reaching the bytes."""
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
    """The gate verdict as markdown — for `$GITHUB_STEP_SUMMARY`.

    Reads the recorded verdict rather than re-running the gate, so the summary
    describes the run that actually happened.
    """
    report = pipeline.read_gate(settings)
    print(format_gate_markdown(report))


def cmd_flow(settings: Settings, args) -> None:
    """Exercise 1 — run the training flow."""
    from .flows import training_flow
    from .tracking import prefect_available

    if not prefect_available(settings):
        raise RuntimeError(
            f"No Prefect server at {settings.prefect_api_url} — start the stack with "
            "`make up`.\n"
            "  (Unsetting PREFECT_API_URL also works: Prefect then starts a temporary\n"
            "   server, runs, and throws the history away. Fine for a smoke test, and\n"
            "   useless for this week, whose whole point is the run record.)"
        )

    verdict = training_flow(
        settings=settings,
        push=args.push,
        register_model_version=args.register,
    )
    print()
    print(f"flow finished — verdict {verdict.get('verdict', '?')}")


def cmd_flow_params(settings: Settings, args) -> None:
    """Exercise 4 — run with a runtime override, then restore params.yaml."""
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
    """Exercise 6 — a scheduled deployment.

    `.serve()` starts a process that listens for scheduled runs. No work pool,
    no worker, no infrastructure block. Work pools are the production answer
    and they are a lecture slide, not this lab.
    """
    from .flows import scheduled_flow

    print(f"Serving `diabetes-training-with-pull` on cron `{args.cron}`.")
    print(f"Open the UI at {settings.prefect_api_url.replace('/api', '')} to watch it.")
    print("Ctrl-C to stop.")
    scheduled_flow.serve(name="weekly-retrain", cron=args.cron)


def cmd_bake_info(settings: Settings, args) -> None:
    """What `make image` bakes in. One line of `KEY=value`, for the shell.

    Lives here rather than as inline shell in the Makefile because it has
    branches, and a `run:` block is the one place in a project that nothing
    tests. Same argument as Week 7's `gate-summary`.
    """
    from . import registry

    verdict, run_id, version = "unknown", "unknown", "unknown"

    report = pipeline.read_gate(settings)
    if report:
        verdict = report.get("verdict", "unknown")

    run_id = pipeline.read_run_id(settings) or "unknown"

    # The registry is optional. If the stack is down we bake the local model
    # and SAY SO, rather than claiming a provenance we cannot support.
    source = "local models/model.pkl"
    try:
        champion = registry.champion_version(settings)
        if champion is not None:
            version = str(champion.version)
            source = "registry champion"
    except Exception:  # noqa: BLE001 -- the stack being down is an ordinary state
        pass

    # QUOTED. `MODEL_SOURCE=local models/model.pkl` unquoted makes `eval` assign
    # the first word and then try to EXECUTE the second, which fails with
    # "models/model.pkl: Permission denied" — an error that says nothing about
    # quoting. Anything a shell will `eval` has to be quoted at the source.
    for key, value in (
        ("MODEL_VERSION", version),
        ("RUN_ID", run_id),
        ("GATE_VERDICT", verdict),
        ("MODEL_SOURCE", source),
    ):
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
    uvicorn.run("week_10_kserve_rollout.api:app", host="127.0.0.1", port=port, log_level="info")


# ── Week 10 — rollout ────────────────────────────────────────────────────────


def cmd_model_publish(settings: Settings, args) -> None:
    """Exercise 1 — put a model version in the store the cluster fetches from."""
    from .rollout import format_versions, list_versions, publish_version

    version = args.store_version or "v1"
    result = publish_version(version, settings=settings, force=args.force)
    print()
    print(f"published {result.version} -> {result.path}")
    if result.forced:
        print()
        print("  FORCED. The recorded gate verdict is "
              f"{result.provenance.get('gate_verdict')!r}, and it has been written into")
        print("  provenance.json, so the pod serving this model will admit it when asked.")
        print("  A model store is the fourth door into production; this is what walking")
        print("  through it looks like.")
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
    """A live endpoint if one was given, otherwise this app, in-process.

    The same suite either way. Without a URL it needs no cluster, no Docker and
    no server, which is why the smoke test is testable in the autograder — and
    why `tests/test_smoke_suite.py` can prove it FAILS on a bad model.
    """
    if args.url:
        import httpx

        headers = {"Host": args.host} if args.host else None
        return httpx.Client(base_url=args.url, headers=headers, timeout=15.0), args.url
    from fastapi.testclient import TestClient

    from .api import create_app

    return TestClient(create_app()), "in-process (TestClient)"


def cmd_smoke(settings: Settings, args) -> None:
    """Exercises 2 and 4: the smoke test, with the spread from the rollout plan."""
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
    """Exercise 2: is release.yaml complete?"""
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
    """Exercise 3: count which revision answered, one request at a time."""
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
    """Exercise 6: the same endpoint at rising concurrency."""
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


def cmd_ci_explain(settings: Settings, args) -> None:
    """Exercise 1 — read the workflows, including the one grading you."""
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
        print("  none yet — Exercises 4 and 5.")
    print()
    print("Workflows GitHub will actually run (repository root):")
    for path in installed:
        print(f"  {path.relative_to(repo)}")
    if not installed:
        print("  none — run `make install-ci`.")
    print()
    print("  GitHub only executes workflows in .github/workflows AT THE ROOT.")
    print("  A workflow in a subdirectory is never run, and never warns you.")
    print()

    rows = audit(lab + installed + grader)
    print(format_audit(rows))


COMMANDS = {
    "validate": cmd_validate,
    "check-file": cmd_check_file,
    "model-input": cmd_model_input,
    "predict": cmd_predict,
    # New in Week 6.
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
    # New in Week 7.
    "ci-explain": cmd_ci_explain,
    # New in Week 9.
    "bench": cmd_bench,
    "bake-info": cmd_bake_info,
    "serve-api": cmd_serve_api,
    # New in Week 10.
    "model-publish": cmd_model_publish,
    "store-list": cmd_store_list,
    "smoke": cmd_smoke,
    "release-check": cmd_release_check,
    "release-value": cmd_release_value,
    "split-measure": cmd_split_measure,
    "loadtest": cmd_loadtest,
    # New in Week 8.
    "flow": cmd_flow,
    "flow-params": cmd_flow_params,
    "serve": cmd_serve,
    "gate-summary": cmd_gate_summary,
}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="week-10-kserve-rollout",
        description="Week 10 lab — KServe: declarative rollout, canary, rollback, smoke tests.",
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
        help="promote: move the `champion` alias too, raising the bar (Exercise 6)",
    )
    parser.add_argument("--push", action="store_true", help="flow: dvc push after the run")
    parser.add_argument("--register", action="store_true", help="flow: register on a GO")
    parser.add_argument("--C", type=float, default=None, help="flow-params: override train.C")
    parser.add_argument("--impute-strategy", default=None, dest="impute_strategy",
                        help="flow-params: override train.impute_strategy")
    parser.add_argument("--family", default=None, help="flow-params: override train.family")
    parser.add_argument("--port", type=int, default=None, help="serve-api: port (default 5541)")
    parser.add_argument("--cron", default="0 3 * * 1", help="serve: schedule (default Mon 03:00)")
    # New in Week 10. `--store-version` is spelled out rather than reusing
    # `--version`, which is already an int (the dataset version) — two meanings
    # for one flag is how a lab command silently does the wrong thing.
    parser.add_argument("--store-version", default=None, dest="store_version",
                        help="model-publish/smoke: the model store version, e.g. v2")
    parser.add_argument("--force", action="store_true",
                        help="model-publish: publish a model the gate refused (Exercise 1)")
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
    args = parser.parse_args()

    settings = load_settings()
    try:
        COMMANDS[args.command](settings, args)
    except (FileNotFoundError, KeyError, RuntimeError, ValueError) as error:
        # RuntimeError covers pipeline.ValidationFailed, which is the ordinary
        # way this lab's gate reports itself. A failed contract is not a crash.
        # A missing prerequisite is an ordinary state in this lab, not a crash.
        # Print it readably and exit NON-ZERO, because dvc.yaml invokes these
        # same subcommands as pipeline stages — a stage that swallowed its own
        # failure would let `dvc repro` report success on a broken pipeline.
        print()
        print(f"Cannot run `{args.command}` yet:")
        print(f"  {error}")
        print()
        raise SystemExit(1)
