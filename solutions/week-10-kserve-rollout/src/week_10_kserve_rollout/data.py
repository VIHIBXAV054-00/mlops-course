from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split

from .config import Settings

# FEATURE_COLUMNS, TARGET_COLUMN, load_dataframe and build_dataset are UNCHANGED
# from Weeks 1-3. They still operate on data/diabetes.csv, which is what keeps
# the course's pinned baseline metrics (LR F1 0.5785 / accuracy 0.7344)
# reproducible in tests/test_smoke.py while Week 4 changes what the *pipeline*
# trains on.

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

# Columns the measurement batches carry that are NOT features. `measurement_date`
# is metadata: it identifies when a row arrived, it would leak batch identity
# into the model, and it does not exist for a new patient at inference time.
METADATA_COLUMNS = ["measurement_date"]


def load_dataframe(settings: Settings) -> pd.DataFrame:
    """Load the canonical Week 1-3 dataset from the configured CSV path."""
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

    This is a presence check, not a schema. It has no types, no ranges, and no
    opinion about the physically-impossible zeros sitting in `glucose`,
    `insulin` and `bmi` — real data contracts, and those zeros, are Week 5.
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
