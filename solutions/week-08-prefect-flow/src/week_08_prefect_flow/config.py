from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Strategies `sklearn.impute.SimpleImputer` accepts that make sense for this
# data. It lives here rather than in model.py because it is the set of legal
# values for a params.yaml entry, and model.py imports config (so the reverse
# import would be circular).
#
# `median` is the default because these distributions are skewed and a median is
# not dragged around by outliers — but the choice is a modelling argument you
# should be able to defend, not a setting to copy.
IMPUTE_STRATEGIES = ("median", "mean", "most_frequent")


@dataclass(frozen=True)
class Settings:
    """Pipeline configuration.

    Two sources, and the split is the point of this week:

    - `params.yaml` holds the pipeline HYPERPARAMETERS. DVC can only hash a
      file, so these must live in one for `dvc.lock` to be able to record what
      a run actually used. Environment overrides are deliberately ignored.
    - `.env` holds ENVIRONMENT wiring — URIs, ports, bucket names, credentials.
      None of it changes the model, so none of it belongs in the lock file.
    """

    # ── Paths ────────────────────────────────────────────────────────────────
    # The Week 1-3 canonical snapshot: git-committed, always present.
    data_path: Path = Path("data/diabetes.csv")
    # The DVC-tracked dataset. See the note in _validate().
    measurements_path: Path = Path("data/measurements.csv")
    raw_dir: Path = Path("data/raw")
    processed_dir: Path = Path("data/processed")
    models_dir: Path = Path("models")
    metrics_path: Path = Path("metrics/metrics.json")
    run_id_path: Path = Path("models/mlflow_run_id.json")
    # New in Week 5. The validation verdict, and the corrupted batch the report
    # exercise reads. `quality_dir` holds git-committed teaching material, so
    # unlike measurements_path it is always present.
    validation_report_path: Path = Path("reports/validation.json")
    quality_dir: Path = Path("data/quality")
    # New in Week 6. Three more `cache: false` artifacts that live in Git:
    # the per-slice scores, the recorded champion, and the go/no-go verdict.
    slices_path: Path = Path("metrics/slices.json")
    baseline_path: Path = Path("metrics/baseline.json")
    gate_report_path: Path = Path("reports/gate.json")

    # ── Hyperparameters, from params.yaml ────────────────────────────────────
    random_seed: int = 42
    test_size: float = 0.25
    model_family: str = "logreg"
    model_c: float = 1.0
    max_iter: int = 1000
    # New in Week 5: how the model fills the nulls that to_nullable created.
    # A hyperparameter, so it lives in params.yaml where DVC can hash it.
    impute_strategy: str = "median"
    # New in Week 6, and the number of fields here is the point.
    #
    # `n_estimators` applies only when `train.family` is `rf`; Exercise 6 uses
    # it to produce a model that is genuinely BETTER, so the ratchet has
    # something to ratchet.
    n_estimators: int = 100

    # ── Evaluation and acceptance, from params.yaml (new in Week 6) ──────────
    #
    # TWO blocks, not one, and the separation is deliberate:
    #
    #   `evaluation`  WHAT we measure — the slice definitions. Changing this
    #                 changes the evidence, so `evaluate` (and therefore `gate`)
    #                 must re-run.
    #   `acceptance`  WHETHER it is good enough — the thresholds. Changing this
    #                 changes only the DECISION, so `dvc repro` re-runs `gate`
    #                 alone and nothing is retrained.
    #
    # Put them in one block and every threshold edit invalidates the model —
    # slow, and it quietly teaches that changing your mind about what "good"
    # means requires new evidence. It does not. Try it: tighten
    # `acceptance.minimum.f1` and run `make repro`.
    #
    # Both are carried as plain dicts rather than typed fields, because they are
    # policy documents that will grow, and because `gates.evaluate_gate` is a
    # pure function over exactly these dicts.
    slice_specs: dict = field(default_factory=dict)
    acceptance: dict = field(default_factory=dict)

    # ── MLflow (Weeks 2-3) ───────────────────────────────────────────────────
    mlflow_tracking_uri: str = "http://127.0.0.1:5500"
    # New in Week 8. NOTE THE /api SUFFIX — without it every client call
    # 404s against the UI, which is the most common self-hosting mistake.
    prefect_api_url: str = "http://127.0.0.1:5520/api"
    mlflow_experiment_name: str = "diabetes-week8"
    registered_model_name: str = "diabetes-classifier"
    model_alias: str = "staging"
    # New in Week 6 as a named setting rather than a literal. `champion` is the
    # role the baseline is read from, and Week 6 is the first week where a
    # second alias does real work instead of demonstrating that two can coexist.
    champion_alias: str = "champion"
    model_owner: str = "unknown"

    # ── DVC remote (new in Week 4) ───────────────────────────────────────────
    dvc_remote_name: str = "storage"
    dvc_bucket: str = "dvc-storage"
    dvc_remote_path: str = "dvcstore"

    project_root: Path = field(default_factory=lambda: Path("."))


def load_params(project_root: Path) -> dict:
    """Read params.yaml. Returns {} if it is absent."""
    params_file = project_root / "params.yaml"
    if not params_file.exists():
        return {}
    return yaml.safe_load(params_file.read_text()) or {}


def load_settings(project_root: Path | None = None) -> Settings:
    """Load hyperparameters from params.yaml and wiring from `.env`."""
    base_path = project_root or Path(__file__).resolve().parents[2]
    load_dotenv(base_path / ".env")
    params = load_params(base_path)
    prepare = params.get("prepare") or {}
    train = params.get("train") or {}
    evaluation = params.get("evaluation") or {}
    acceptance = params.get("acceptance") or {}

    settings = Settings(
        project_root=base_path,
        data_path=base_path / os.getenv("PIPELINE_DATA_PATH", "data/diabetes.csv"),
        measurements_path=base_path
        / os.getenv("PIPELINE_MEASUREMENTS_PATH", "data/measurements.csv"),
        raw_dir=base_path / "data/raw",
        processed_dir=base_path / "data/processed",
        models_dir=base_path / "models",
        metrics_path=base_path / "metrics/metrics.json",
        run_id_path=base_path / "models/mlflow_run_id.json",
        validation_report_path=base_path / "reports/validation.json",
        quality_dir=base_path / "data/quality",
        slices_path=base_path / "metrics/slices.json",
        baseline_path=base_path / "metrics/baseline.json",
        gate_report_path=base_path / "reports/gate.json",
        # From params.yaml ONLY — see the class docstring.
        random_seed=int(params.get("random_seed", 42)),
        test_size=float(prepare.get("test_size", 0.25)),
        model_family=str(train.get("family", "logreg")),
        model_c=float(train.get("C", 1.0)),
        max_iter=int(train.get("max_iter", 1000)),
        impute_strategy=str(train.get("impute_strategy", "median")),
        n_estimators=int(train.get("n_estimators", 100)),
        slice_specs=dict(evaluation.get("slices") or {}),
        acceptance=dict(acceptance),
        mlflow_tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5500"),
        prefect_api_url=os.getenv("PREFECT_API_URL", "http://127.0.0.1:5520/api"),
        mlflow_experiment_name=os.getenv("MLFLOW_EXPERIMENT_NAME", "diabetes-week8"),
        registered_model_name=os.getenv(
            "MLFLOW_REGISTERED_MODEL_NAME", "diabetes-classifier"
        ),
        model_alias=os.getenv("MLFLOW_MODEL_ALIAS", "staging"),
        champion_alias=os.getenv("MLFLOW_CHAMPION_ALIAS", "champion"),
        model_owner=os.getenv("MLFLOW_MODEL_OWNER", "unknown"),
        dvc_remote_name=os.getenv("DVC_REMOTE_NAME", "storage"),
        dvc_bucket=os.getenv("DVC_BUCKET", "dvc-storage"),
        dvc_remote_path=os.getenv("DVC_REMOTE_PATH", "dvcstore"),
    )

    _validate(settings)
    return settings


def _validate(settings: Settings) -> None:
    if not 0.0 < settings.test_size < 1.0:
        raise ValueError("prepare.test_size in params.yaml must be between 0 and 1.")
    if settings.max_iter <= 0:
        raise ValueError("train.max_iter in params.yaml must be greater than 0.")
    if settings.model_c <= 0:
        raise ValueError("train.C in params.yaml must be greater than 0.")
    if settings.impute_strategy not in IMPUTE_STRATEGIES:
        raise ValueError(
            f"train.impute_strategy in params.yaml must be one of "
            f"{IMPUTE_STRATEGIES}; got {settings.impute_strategy!r}."
        )
    if settings.n_estimators <= 0:
        raise ValueError("train.n_estimators in params.yaml must be greater than 0.")
    _validate_slices(settings.slice_specs)
    _validate_acceptance(settings.acceptance)
    if not settings.data_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {settings.data_path}. "
            "Check PIPELINE_DATA_PATH and run commands from the lab directory."
        )
    if not settings.mlflow_tracking_uri.startswith("http"):
        raise ValueError("MLFLOW_TRACKING_URI must start with http:// or https://")
    if not settings.mlflow_experiment_name:
        raise ValueError("MLFLOW_EXPERIMENT_NAME must not be empty.")
    if not settings.registered_model_name:
        raise ValueError("MLFLOW_REGISTERED_MODEL_NAME must not be empty.")
    if "/" in settings.registered_model_name:
        raise ValueError("MLFLOW_REGISTERED_MODEL_NAME must not contain '/'.")
    if not settings.model_alias or " " in settings.model_alias:
        raise ValueError("MLFLOW_MODEL_ALIAS must be a non-empty name without spaces.")
    if not settings.champion_alias or " " in settings.champion_alias:
        raise ValueError(
            "MLFLOW_CHAMPION_ALIAS must be a non-empty name without spaces."
        )
    if not settings.dvc_bucket or "/" in settings.dvc_bucket:
        raise ValueError("DVC_BUCKET must be a bucket name without '/'.")

    # measurements_path is DELIBERATELY NOT VALIDATED.
    #
    # It is DVC-tracked, so it is legitimately absent in a fresh clone (before
    # `dvc pull`) and in the course autograder, which never runs `dvc pull`.
    # Validating it here would fail every test in CI. Code and tests that need
    # the file check for it themselves and skip or fail with a clear message —
    # see tests/conftest.py::measurements_file and cli.py.


# The two Week 6 policy blocks get their own validators, because a typo in a
# slice definition or a threshold should fail at load time with a sentence you
# can act on — not three stages later, as a KeyError inside the gate.
#
# This matters more here than for the other settings. A malformed threshold that
# silently defaults to something permissive is a gate that reports GO for a
# reason nobody intended, and the whole point of the week is that a gate you
# cannot trust is worse than no gate at all.

SLICE_KINDS = ("bins", "missing_flag")


def _validate_slices(specs: dict) -> None:
    for name, spec in (specs or {}).items():
        if not isinstance(spec, dict):
            raise ValueError(f"evaluation.slices.{name} must be a mapping.")
        if "column" not in spec:
            raise ValueError(f"evaluation.slices.{name} must name a `column`.")
        kind = spec.get("kind", "bins")
        if kind not in SLICE_KINDS:
            raise ValueError(
                f"evaluation.slices.{name}.kind must be one of {SLICE_KINDS}; "
                f"got {kind!r}."
            )
        if kind == "bins":
            edges = spec.get("bins")
            labels = spec.get("labels")
            if not edges or len(edges) < 2:
                raise ValueError(
                    f"evaluation.slices.{name}.bins needs at least two edges."
                )
            if list(edges) != sorted(edges):
                raise ValueError(
                    f"evaluation.slices.{name}.bins must be in ascending order."
                )
            if not labels or len(labels) != len(edges) - 1:
                raise ValueError(
                    f"evaluation.slices.{name} declares {len(edges) - 1} bin(s) "
                    f"but {len(labels or [])} label(s); they must match."
                )


def _validate_acceptance(acceptance: dict) -> None:
    if not acceptance:
        return
    for metric, floor in (acceptance.get("minimum") or {}).items():
        if not 0.0 <= float(floor) <= 1.0:
            raise ValueError(
                f"acceptance.minimum.{metric} must be between 0 and 1; got {floor}."
            )
    regression = acceptance.get("regression") or {}
    if regression:
        if "primary_metric" not in regression:
            raise ValueError("acceptance.regression must name a `primary_metric`.")
        drop = regression.get("max_drop")
        if drop is None or float(drop) < 0:
            raise ValueError(
                "acceptance.regression.max_drop must be present and non-negative. "
                "It is a noise band, not a budget for getting worse."
            )
    rules = acceptance.get("slice_rules") or {}
    for key in ("min_support", "min_positives"):
        if key in rules and int(rules[key]) < 0:
            raise ValueError(f"acceptance.slice_rules.{key} must be non-negative.")
