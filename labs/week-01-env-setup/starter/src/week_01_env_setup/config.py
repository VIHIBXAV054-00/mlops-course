from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """Pipeline configuration with sensible defaults.

    Values can be overridden through environment variables (see `.env.example`).
    """

    random_seed: int = 42
    data_path: Path = Path("data/diabetes.csv")
    test_size: float = 0.25
    max_iter: int = 1000


def load_settings(project_root: Path | None = None) -> Settings:
    """Load settings from defaults, then override from `.env` / environment."""
    base_path = project_root or Path(__file__).resolve().parents[2]
    load_dotenv(base_path / ".env")

    settings = Settings(
        random_seed=int(os.getenv("PIPELINE_RANDOM_SEED", "42")),
        data_path=base_path / os.getenv("PIPELINE_DATA_PATH", "data/diabetes.csv"),
        test_size=float(os.getenv("PIPELINE_TEST_SIZE", "0.25")),
        max_iter=int(os.getenv("PIPELINE_MAX_ITER", "1000")),
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
