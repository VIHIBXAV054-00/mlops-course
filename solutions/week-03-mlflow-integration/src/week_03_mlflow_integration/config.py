from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Pipeline configuration with sensible defaults.

    Values can be overridden through environment variables (see `.env.example`).

    New in Week 3 (compared to Week 2):
      - registered_model_name: the NAME under which model versions are registered
      - model_alias: the movable pointer we assign when promoting a version
      - model_owner: recorded as a governance tag when a version is promoted
    """

    # ── ML pipeline settings (carried over from Week 1) ──────────────────────
    random_seed: int = 42
    data_path: Path = Path("data/diabetes.csv")
    test_size: float = 0.25
    max_iter: int = 1000

    # ── MLflow tracking settings (Week 2) ────────────────────────────────────
    mlflow_tracking_uri: str = "http://127.0.0.1:5500"
    mlflow_experiment_name: str = "diabetes-week3"

    # ── Model registry settings (new in Week 3) ──────────────────────────────
    registered_model_name: str = "diabetes-classifier"
    model_alias: str = "staging"
    model_owner: str = "unknown"


def load_settings(project_root: Path | None = None) -> Settings:
    """Load settings from defaults, then override from `.env` / environment."""
    base_path = project_root or Path(__file__).resolve().parents[2]
    load_dotenv(base_path / ".env")

    settings = Settings(
        random_seed=int(os.getenv("PIPELINE_RANDOM_SEED", "42")),
        data_path=base_path / os.getenv("PIPELINE_DATA_PATH", "data/diabetes.csv"),
        test_size=float(os.getenv("PIPELINE_TEST_SIZE", "0.25")),
        max_iter=int(os.getenv("PIPELINE_MAX_ITER", "1000")),
        mlflow_tracking_uri=os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5500"),
        mlflow_experiment_name=os.getenv("MLFLOW_EXPERIMENT_NAME", "diabetes-week3"),
        registered_model_name=os.getenv(
            "MLFLOW_REGISTERED_MODEL_NAME", "diabetes-classifier"
        ),
        model_alias=os.getenv("MLFLOW_MODEL_ALIAS", "staging"),
        model_owner=os.getenv("MLFLOW_MODEL_OWNER", "unknown"),
    )

    _validate(settings)
    return settings


def _validate(settings: Settings) -> None:
    if not 0.0 < settings.test_size < 1.0:
        raise ValueError("PIPELINE_TEST_SIZE must be between 0 and 1 (exclusive).")
    if settings.max_iter <= 0:
        raise ValueError("PIPELINE_MAX_ITER must be greater than 0.")
    if not settings.data_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {settings.data_path}. "
            "Check PIPELINE_DATA_PATH and run commands from the lab directory."
        )
    if not settings.mlflow_tracking_uri.startswith("http"):
        raise ValueError("MLFLOW_TRACKING_URI must start with http:// or https://")
    if not settings.mlflow_experiment_name:
        raise ValueError("MLFLOW_EXPERIMENT_NAME must not be empty.")

    # ── Registry validations (new in Week 3) ─────────────────────────────────
    # Registered-model names and aliases have real server-side constraints.
    # Fail fast on the host rather than hitting an opaque REST error mid-run.
    if not settings.registered_model_name:
        raise ValueError("MLFLOW_REGISTERED_MODEL_NAME must not be empty.")
    if "/" in settings.registered_model_name:
        raise ValueError(
            "MLFLOW_REGISTERED_MODEL_NAME must not contain '/' — it would collide "
            "with the models:/<name>/<version> URI form."
        )
    if not settings.model_alias or " " in settings.model_alias:
        raise ValueError("MLFLOW_MODEL_ALIAS must be a non-empty name without spaces.")
