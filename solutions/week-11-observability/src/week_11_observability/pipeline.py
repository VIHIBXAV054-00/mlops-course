"""The five pipeline stages that `dvc.yaml` declares.

    validate ──▶ prepare ──▶ train ──▶ evaluate ──▶ gate

Week 4 had the middle three. `validate` is Week 5's, and it is first on purpose:
it is a DATA quality gate, and a gate that runs after the work is a report.

`gate` is new in Week 6 and it is last, which changes how it has to work. Week
5's gate had teeth because `prepare` declared its verdict file as a dependency:
fail, and nothing downstream ran. There is nothing downstream of `evaluate`, and
a failing MODEL gate must not delete the model — you need the artifact to work
out why it failed. So this one writes a verdict, exits non-zero, and `register`
and `promote` refuse without a GO. A gate is only as strong as the thing that
consults it.

    Week 5 = was the data allowed IN?
    Week 6 = is the model allowed OUT?

Each function is one DVC stage, and each is runnable by hand through
`src/main.py` — a stage you cannot run manually is a stage you cannot debug.

The stages communicate through FILES, not through Python calls. That is what
lets DVC hash the boundary between them and skip work that cannot have changed.
It is also how the gate gets its teeth: `validate` writes
`reports/validation.json`, `prepare` declares that file as a dependency, and so
`dvc repro` will not run `prepare` until `validate` has succeeded. The gate is a
node in the graph, not an `assert` buried in a function.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib

from .baseline import read_baseline
from .config import Settings
from .data import FEATURE_COLUMNS, TARGET_COLUMN, load_measurements, split_measurements
from .evaluation import slice_report
from .gates import evaluate_gate
from .model import build_model, evaluate_model
from .schemas import MODEL_INPUT_COLUMNS, ModelInput, RawMeasurements
from .validation import (
    read_raw,
    read_report,
    sentinel_counts,
    to_nullable,
    validate_frame,
    write_report,
)


def _require_measurements(settings: Settings) -> Path:
    path = settings.measurements_path
    if not path.exists():
        raise FileNotFoundError(
            f"{path.name} is missing. It is DVC-tracked, so a fresh clone does "
            "not have it. Run `make dvc-pull` to fetch it, or `make data-v2` "
            "to rebuild it from data/raw/."
        )
    return path


class ValidationFailed(RuntimeError):
    """The data did not satisfy its contract. Not a bug — a gate doing its job."""


class GateFailed(RuntimeError):
    """The model did not satisfy its acceptance criteria. New in Week 6.

    Also not a bug. A NO-GO is the system working: somebody wrote down what
    "good enough" meant, and this model is not it.
    """


def _hyperparams(settings: Settings) -> dict:
    """The estimator keyword arguments for the configured family.

    Kept in one place because `train` and the tests both need it, and because a
    silently-ignored hyperparameter is the kind of thing that makes a sweep
    meaningless. `n_estimators` applies to the forest only; passing it to
    LogisticRegression would raise, which is better than being ignored.
    """
    if settings.model_family == "rf":
        return {"n_estimators": settings.n_estimators}
    return {"C": settings.model_c}


def validate(settings: Settings) -> dict:
    """Stage 0 — the gate. New in Week 5.

    Runs the INGESTION contract against the DVC-tracked dataset, writes the
    verdict to `reports/validation.json`, and raises `ValidationFailed` if the
    data did not pass. The CLI turns that into a non-zero exit, which is what
    makes `dvc repro` stop here instead of training on data it was told not to.

    Note the ordering inside the function: the report is written BEFORE the
    failure is raised. A gate that blocks the pipeline and leaves no evidence
    behind is untriageable — you want the file that says exactly which 15 things
    were wrong, and you want it even on the run that failed.
    """
    source = _require_measurements(settings)
    frame = read_raw(source)

    report = validate_frame(
        frame, RawMeasurements, source=str(source.name)
    )
    report["sentinel_zeros"] = sentinel_counts(frame)
    write_report(report, settings.validation_report_path)

    if not report["passed"]:
        raise ValidationFailed(
            f"{source.name} failed the {report['schema']} contract with "
            f"{report['n_failure_cases']} failure case(s). "
            f"See {settings.validation_report_path.name} for the full report, "
            "or run `make validate` to print it."
        )

    return report


def _require_validated(settings: Settings) -> dict:
    """The recorded verdict, or a refusal to continue without one."""
    report = read_report(settings.validation_report_path)
    if not report:
        raise FileNotFoundError(
            f"{settings.validation_report_path.name} is missing. The validate "
            "stage has never run — run `make validate` (or `make repro`, which "
            "runs it first)."
        )
    if not report.get("passed"):
        raise ValidationFailed(
            f"The last validation run FAILED "
            f"({report.get('n_failure_cases')} failure case(s)). Fix the data "
            "or the contract; do not train on data that failed its contract."
        )
    return report


def prepare(settings: Settings) -> dict:
    """Stage 1 — split the versioned dataset into train and test CSVs.

    `measurement_date` is KEPT in the written files (lineage survives into the
    processed data, and Weeks 11-12 get a time axis for free) but is not a
    feature — `train` selects FEATURE_COLUMNS explicitly.

    New in Week 5: it refuses to run at all unless a PASSING validation report
    exists. `dvc.yaml` already enforces that through the dependency graph; this
    check is what makes a manual `python src/main.py prepare` behave the same
    way. A gate that only holds when you use the front door is not a gate.
    """
    _require_validated(settings)
    source = _require_measurements(settings)
    frame = load_measurements(source)
    train_frame, test_frame = split_measurements(frame, settings)

    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    train_path = settings.processed_dir / "train.csv"
    test_path = settings.processed_dir / "test.csv"
    train_frame.to_csv(train_path, index=False, lineterminator="\n")
    test_frame.to_csv(test_path, index=False, lineterminator="\n")

    return {
        "rows_in": len(frame),
        "rows_train": len(train_frame),
        "rows_test": len(test_frame),
        "train_path": str(train_path),
        "test_path": str(test_path),
    }


def prepare_model_input(frame) -> tuple:
    """Turn a processed split into something `ModelInput` accepts. New in Week 5.

    Three steps, in this order, and the order is the lesson:

    1. **Project** to exactly the model's columns, in the contract's order. The
       processed CSVs still carry `measurement_date`; the model must never see
       it (it would leak batch identity, and a new patient does not have one).
    2. **Convert** the sentinel zeros to nulls. This is a statement of fact — we
       do not know these values — and nothing more.
    3. **Validate** against `ModelInput`, which permits nulls and forbids zeros.

    Returns `(features, labels, report)`. The report is returned rather than
    printed so the caller can log it to MLflow.
    """
    projected = frame[MODEL_INPUT_COLUMNS]
    nullable = to_nullable(projected)
    report = validate_frame(nullable, ModelInput, source="model input")
    if not report["passed"]:
        raise ValidationFailed(
            f"The model input failed the ModelInput contract with "
            f"{report['n_failure_cases']} failure case(s). The most likely cause "
            "is a sentinel zero that survived to_nullable — check that every "
            "column in SENTINEL_COLUMNS is being converted."
        )
    # float64, not Float64: sklearn's SimpleImputer wants a plain numeric array,
    # and NaN is how it recognises a value to fill.
    features = nullable[list(FEATURE_COLUMNS)].astype("float64")
    labels = nullable[TARGET_COLUMN].astype("int64")
    return features, labels, report


def train(settings: Settings) -> dict:
    """Stage 2 — fit the model, and record the data version on the MLflow run.

    The MLflow half is guarded: if the tracking server is not reachable, the
    stage still produces its model and writes `{"run_id": null}`, so the DVC
    pipeline is not hostage to a running container. That guard is why this stage
    works in CI.

    New in Week 5: the TRAINING contract runs here, right before `fit`, and the
    imputer that makes the nulls trainable lives inside the Pipeline rather than
    in this function — see `model.build_model`.
    """
    train_path = settings.processed_dir / "train.csv"
    if not train_path.exists():
        raise FileNotFoundError(
            f"{train_path.name} is missing. Run the prepare stage first "
            "(`make repro`)."
        )

    frame = load_measurements(train_path)
    features, labels, input_report = prepare_model_input(frame)
    model = build_model(
        settings.model_family,
        _hyperparams(settings),
        settings,
        impute=settings.impute_strategy,
    )
    model.fit(features, labels)

    settings.models_dir.mkdir(parents=True, exist_ok=True)
    model_path = settings.models_dir / "model.pkl"
    joblib.dump(model, model_path)

    run_id = None
    digest = None
    from .tracking import mlflow_available

    if mlflow_available(settings):
        import mlflow

        from .dvc_link import (
            dvc_data_url,
            log_data_version,
            log_dataset_input,
            log_validation,
        )
        from .tracking import connect, git_commit

        connect(settings)
        with mlflow.start_run(run_name=f"dvc-{settings.model_family}") as run:
            run_id = run.info.run_id
            mlflow.log_params(
                {
                    "model_family": settings.model_family,
                    **_hyperparams(settings),
                    "max_iter": settings.max_iter,
                    "random_seed": settings.random_seed,
                    "test_size": settings.test_size,
                    "n_rows_train": len(frame),
                    # New in Week 5 — the imputation strategy is part of what
                    # produced this model, so it is part of the run.
                    "impute_strategy": settings.impute_strategy,
                }
            )
            mlflow.set_tags({"git_commit": git_commit()})
            # The Week 4 addition: which BYTES did this run consume?
            log_data_version(settings)
            # The Week 5 addition: did those bytes pass their contract, and
            # which version of the contract was that? Without the version,
            # "it passed validation" is a claim with no referent.
            log_validation(settings, input_report)
            digest = log_dataset_input(frame, settings, dvc_data_url(settings))
            mlflow.sklearn.log_model(model, name="model")

    # Written even when MLflow is down, so `evaluate` and Git always have a
    # (possibly null) join key back to the tracking server.
    settings.run_id_path.parent.mkdir(parents=True, exist_ok=True)
    settings.run_id_path.write_text(
        json.dumps({"run_id": run_id, "mlflow_digest": digest}, indent=2) + "\n"
    )

    return {"model_path": str(model_path), "run_id": run_id, "mlflow_digest": digest}


def evaluate(settings: Settings) -> dict:
    """Stage 3 — score the model, aggregate and per slice.

    `metrics/metrics.json` is unchanged from Week 5. New in Week 6 is its
    companion, `metrics/slices.json`: the same model scored again on each group
    declared in `evaluation.slices`.

    Both are `cache: false` DVC outputs, so they live in Git. That is what makes
    `dvc metrics diff` work with no remote and puts the numbers in the same
    commit as the pointer, the lock file and the validation verdict.

    Note what this function still does NOT do: compare anything to a threshold.
    Measurement and policy are separate stages for the same reason they are
    separate blocks in `params.yaml` — see the header there.
    """
    model_path = settings.models_dir / "model.pkl"
    test_path = settings.processed_dir / "test.csv"
    for path in (model_path, test_path):
        if not path.exists():
            raise FileNotFoundError(
                f"{path.name} is missing. Run the earlier stages first (`make repro`)."
            )

    model = joblib.load(model_path)
    frame = load_measurements(test_path)
    # The test set goes through the SAME three steps as the training set —
    # project, convert, validate. Scoring the model on raw zeros while it was
    # fitted on imputed nulls would be training-serving skew inside our own
    # pipeline, which is precisely the mistake Week 5 exists to prevent.
    features, labels, _ = prepare_model_input(frame)
    metrics = evaluate_model(model, features, labels)

    # The slice frame is `frame` — the RAW test split, sentinel zeros intact —
    # and NOT `features`, which the conversion has already emptied out. Slice on
    # imputed values and a patient whose BMI was never measured joins whichever
    # band the training median fell in: their group stops existing and the band
    # they joined reports a number partly about people it does not describe.
    slices = slice_report(
        frame,
        labels,
        model.predict(features),
        model.predict_proba(features)[:, 1],
        settings.slice_specs,
    )

    settings.metrics_path.parent.mkdir(parents=True, exist_ok=True)
    settings.metrics_path.write_text(json.dumps(metrics, indent=2) + "\n")
    # No timestamp, no hostname, no run id generated at write time. This file is
    # a `cache: false` output committed to Git, so anything that changed between
    # two identical runs would leave `gate` permanently stale, the working tree
    # permanently dirty, and every commit carrying a diff that says nothing.
    settings.slices_path.write_text(json.dumps(slices, indent=2) + "\n")

    # Attach the scores to the run that produced the model, if there was one.
    run_id = read_run_id(settings)
    if run_id:
        from .tracking import mlflow_available

        if mlflow_available(settings):
            from mlflow.tracking import MlflowClient

            client = MlflowClient(settings.mlflow_tracking_uri)
            for key, value in metrics.items():
                client.log_metric(run_id, key, value)
            for key, value in flatten_slice_metrics(slices).items():
                client.log_metric(run_id, key, value)

    return {"metrics": metrics, "slices": slices, "run_id": run_id}


# MLflow metric names allow alphanumerics, underscores, dashes, periods, spaces
# and slashes — but not `+`, which `50+` contains. Sanitised rather than
# renamed, so the slice label in params.yaml stays readable for humans.
_METRIC_NAME_SAFE = str.maketrans({"+": "plus", " ": "_", "/": "_"})


def flatten_slice_metrics(slices: dict, keys=("f1", "recall", "roc_auc")) -> dict:
    """Per-slice scores as flat MLflow metric names.

    `slice.age_band.50plus.f1` and friends. Only a few keys, on purpose: the
    full table is logged as an artifact, and a run with two hundred metrics is a
    run nobody reads. Nulls are dropped — MLflow cannot store "undefined", and
    writing 0.0 instead is exactly the lie this week is about.
    """
    flat = {}
    for axis, groups in (slices.get("slices") or {}).items():
        for group, m in groups.items():
            safe = str(group).translate(_METRIC_NAME_SAFE)
            for key in keys:
                if m.get(key) is not None:
                    flat[f"slice.{axis}.{safe}.{key}"] = float(m[key])
    return flat


def gate(settings: Settings) -> dict:
    """Stage 4 — the model quality gate. New in Week 6, and the point of it.

    Reads the measurements (`metrics.json`, `slices.json`), the recorded
    champion (`baseline.json`) and the policy (`acceptance` in params.yaml);
    writes the verdict to `reports/gate.json`; raises `GateFailed` on NO-GO so
    the CLI exits non-zero and `dvc repro` stops.

    Two orderings matter here and both are deliberate:

    1. **The report is written BEFORE the failure is raised.** A gate that blocks
       a release and leaves no evidence behind is untriageable. You want the file
       that says exactly which check failed and by how much, and you want it on
       the run that failed most of all.
    2. **Nothing is deleted.** `models/model.pkl` survives a NO-GO. This is the
       opposite of Week 5, where a failing data gate meant no processed data was
       written at all — and the difference is that a bad model is evidence,
       whereas bad data is just bad data.
    """
    metrics = read_metrics(settings)
    if not metrics:
        raise FileNotFoundError(
            f"{settings.metrics_path.name} is missing. The evaluate stage has "
            "never run — run `make repro`."
        )
    slices = read_slices(settings)
    baseline = read_baseline(settings.baseline_path)

    report = evaluate_gate(metrics, slices, baseline, settings.acceptance)

    settings.gate_report_path.parent.mkdir(parents=True, exist_ok=True)
    settings.gate_report_path.write_text(json.dumps(report, indent=2) + "\n")

    log_gate_to_run(settings, report)

    if report["verdict"] != "GO":
        failed = [c["id"] for c in report["checks"] if c["status"] == "fail"]
        raise GateFailed(
            f"NO-GO. {report['summary']['failed']} acceptance criteria failed: "
            f"{', '.join(failed)}. See "
            f"reports/{settings.gate_report_path.name} for the numbers, or run "
            "`make gate` to print them. The model is still on disk — a failing "
            "gate stops a release, not an investigation."
        )

    return report


def log_gate_to_run(settings: Settings, report: dict) -> dict:
    """Stamp the verdict onto the MLflow run that produced the model.

    This is the last link in a chain that has been growing since Week 3, and it
    is what turns the registry alias into an audit trail:

        alias -> version -> run -> git commit -> data md5 -> validation verdict
              -> params -> GATE VERDICT

    Tagged even on a NO-GO, deliberately. A run that failed its gate and still
    exists is exactly the run you want to be able to find later — either to
    understand why, or to notice that somebody released it anyway.

    Guarded by reachability, like every other MLflow call in this pipeline, so
    the stage still works with the stack down and in CI.
    """
    run_id = read_run_id(settings)
    if not run_id:
        return {}
    from .tracking import mlflow_available

    if not mlflow_available(settings):
        return {}

    from mlflow.tracking import MlflowClient

    client = MlflowClient(settings.mlflow_tracking_uri)
    tags = {
        "gate": report.get("verdict", ""),
        "gate_criteria_version": str(report.get("criteria_version", "")),
        "gate_checks_failed": str(report.get("summary", {}).get("failed", "")),
        # Skipped is a tag of its own, because "0 failed" and "0 failed, 8 not
        # checked" are different sentences and only one of them is reassuring.
        "gate_checks_skipped": str(report.get("summary", {}).get("skipped", "")),
    }
    for key, value in tags.items():
        client.set_tag(run_id, key, value)

    for path in (settings.gate_report_path, settings.slices_path):
        if path.exists():
            client.log_artifact(run_id, str(path), artifact_path="evaluation")
    return tags


def read_slices(settings: Settings) -> dict:
    """The per-slice scores recorded by the evaluate stage, if any."""
    if not settings.slices_path.exists():
        return {}
    return json.loads(settings.slices_path.read_text() or "{}")


def read_gate(settings: Settings) -> dict:
    """The last recorded verdict, or {} if the gate has never run."""
    if not settings.gate_report_path.exists():
        return {}
    return json.loads(settings.gate_report_path.read_text() or "{}")


def require_go(settings: Settings) -> dict:
    """The recorded GO verdict, or a refusal. New in Week 6.

    This is the function that gives the gate its teeth, and it lives here rather
    than inside `registry.py` so that there is exactly ONE definition of "may
    this model be released?" in the project. `register` and `promote` both call
    it. A second, slightly different copy of this rule is how a gate quietly
    stops applying to the path somebody actually uses.
    """
    report = read_gate(settings)
    if not report:
        raise GateFailed(
            f"reports/{settings.gate_report_path.name} is missing — the gate has never "
            "run for this model. Run `make gate` (or `make repro`, which runs "
            "it last). Releasing an ungated model is not a shortcut; it is the "
            "thing the gate exists to prevent."
        )
    if report.get("verdict") != "GO":
        failed = [c["id"] for c in report.get("checks", []) if c["status"] == "fail"]
        raise GateFailed(
            f"The recorded verdict is {report.get('verdict')} "
            f"(criteria v{report.get('criteria_version')}): "
            f"{', '.join(failed) or 'no checks recorded'}. Refusing to release."
        )
    return report


def read_run_id(settings: Settings) -> str | None:
    """The MLflow run id recorded by the train stage, if any."""
    if not settings.run_id_path.exists():
        return None
    payload = json.loads(settings.run_id_path.read_text() or "{}")
    return payload.get("run_id")


def read_metrics(settings: Settings) -> dict:
    """The metrics recorded by the evaluate stage, if any."""
    if not settings.metrics_path.exists():
        return {}
    return json.loads(settings.metrics_path.read_text() or "{}")
