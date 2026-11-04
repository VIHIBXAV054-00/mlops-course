from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split

from .config import Settings

# build_dataset reads data/diabetes.csv; tests/test_smoke.py checks its pinned F1 0.5785.

FEATURE_COLUMNS = [
    "pregnancies",
    "glucose",
    "blood_pressure",
    "skin_thickness",
    "insulin",
    "bmi",
    "diabetes_pedigree",
    "age",
]
TARGET_COLUMN = "outcome"

# Not a feature: a new patient has no measurement_date at inference time.
METADATA_COLUMNS = ["measurement_date"]


def load_dataframe(settings: Settings) -> pd.DataFrame:
    """Load the dataset at `settings.data_path` (data/diabetes.csv)."""
    return pd.read_csv(settings.data_path)


def build_dataset(settings: Settings) -> tuple:
    """Split the canonical dataset into stratified train and test sets."""
    frame = load_dataframe(settings)
    features = frame[FEATURE_COLUMNS]
    labels = frame[TARGET_COLUMN]

    x_train, x_test, y_train, y_test = train_test_split(
        features,
        labels,
        test_size=settings.test_size,
        random_state=settings.random_seed,
        stratify=labels,
    )
    return x_train, x_test, y_train, y_test


def load_measurements(path) -> pd.DataFrame:
    """Load a measurement dataset, parsing the date column when present.

    The same function reads a batch file (10 columns, `measurement_date` first)
    and a bare diabetes.csv (9 columns, no date), so the pipeline does not care
    which it was handed.
    """
    frame = pd.read_csv(path)
    if "measurement_date" in frame.columns:
        frame["measurement_date"] = pd.to_datetime(frame["measurement_date"])
    return frame


def require_columns(frame: pd.DataFrame) -> None:
    """Fail early and readably if the expected modelling columns are missing.

    A presence check only; the value rules are in schemas.py.
    """
    missing = [c for c in FEATURE_COLUMNS + [TARGET_COLUMN] if c not in frame.columns]
    if missing:
        raise KeyError(
            f"Dataset is missing expected column(s): {missing}. "
            f"Found: {list(frame.columns)}"
        )


def split_measurements(frame: pd.DataFrame, settings: Settings) -> tuple:
    """Stratified split of a measurement frame, keeping all columns.

    Returns whole DataFrames rather than an X/y pair, because the `prepare`
    stage writes them to CSV — and keeping `measurement_date` in the written
    splits means the lineage survives into the processed data.
    """
    require_columns(frame)
    train_frame, test_frame = train_test_split(
        frame,
        test_size=settings.test_size,
        random_state=settings.random_seed,
        stratify=frame[TARGET_COLUMN],
    )
    return train_frame, test_frame
