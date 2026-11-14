"""Settings: hyperparameters from params.yaml, wiring from .env. You do not need to read it."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

# The values `train.impute_strategy` in params.yaml may take.
IMPUTE_STRATEGIES = ("median", "mean", "most_frequent")


@dataclass(frozen=True)
class Settings:
    """Pipeline configuration.

    Hyperparameters and policy come from `params.yaml` only, so that `dvc.lock`
    records them. Wiring (URIs, ports, bucket names) comes from `.env`.
    """

    # ── Paths ────────────────────────────────────────────────────────────────
    data_path: Path = Path("data/diabetes.csv")
    # The DVC-tracked dataset; `_validate` does not require it to exist.
    measurements_path: Path = Path("data/measurements.csv")
    raw_dir: Path = Path("data/raw")
    processed_dir: Path = Path("data/processed")
    models_dir: Path = Path("models")
    metrics_path: Path = Path("metrics/metrics.json")
    run_id_path: Path = Path("models/mlflow_run_id.json")
    validation_report_path: Path = Path("reports/validation.json")
    quality_dir: Path = Path("data/quality")
    slices_path: Path = Path("metrics/slices.json")
    baseline_path: Path = Path("metrics/baseline.json")
    gate_report_path: Path = Path("reports/gate.json")

    # ── Hyperparameters, from params.yaml ────────────────────────────────────
    random_seed: int = 42
    test_size: float = 0.25
    model_family: str = "logreg"
    model_c: float = 1.0
    max_iter: int = 1000
    impute_strategy: str = "median"
    # Used when `train.family` is `rf`.
    n_estimators: int = 100

    # ── Evaluation and acceptance, from params.yaml ──────────────────────────
    # `evaluation` defines the slices (what we measure); `acceptance` defines the
    # thresholds (what is good enough). They are plain dicts that `gates.py` reads.
    slice_specs: dict = field(default_factory=dict)
    acceptance: dict = field(default_factory=dict)

    # ── MLflow (Weeks 2-3) ───────────────────────────────────────────────────
    mlflow_tracking_uri: str = "http://127.0.0.1:5500"
    mlflow_experiment_name: str = "diabetes-week7"
    registered_model_name: str = "diabetes-classifier"
    model_alias: str = "staging"
    # The alias whose model version is the baseline for the regression check.
    champion_alias: str = "champion"
    model_owner: str = "unknown"

    # ── DVC remote ───────────────────────────────────────────────────────────
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
        mlflow_experiment_name=os.getenv("MLFLOW_EXPERIMENT_NAME", "diabetes-week7"),
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
