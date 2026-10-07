"""Load and split the data."""

from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split

from .config import Settings

# load_dataframe and build_dataset read data/diabetes.csv. The DVC pipeline uses
# the measurement functions below.

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

# Columns in the measurement batches that are not features. A new patient has
# no `measurement_date`, so the model must not use it.
METADATA_COLUMNS = ["measurement_date"]


def load_dataframe(settings: Settings) -> pd.DataFrame:
    """Load data/diabetes.csv."""
    return pd.read_csv(settings.data_path)


def build_dataset(settings: Settings) -> tuple:
    """Split data/diabetes.csv into stratified train and test sets."""
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
    """Load a measurement dataset, parsing the date column when present."""
    frame = pd.read_csv(path)
    if "measurement_date" in frame.columns:
        frame["measurement_date"] = pd.to_datetime(frame["measurement_date"])
    return frame


def require_columns(frame: pd.DataFrame) -> None:
    """Fail early if a modelling column is missing.

    This checks only that the columns exist. The contracts in schemas.py check
    the values.
    """
    missing = [c for c in FEATURE_COLUMNS + [TARGET_COLUMN] if c not in frame.columns]
    if missing:
        raise KeyError(
            f"Dataset is missing expected column(s): {missing}. "
            f"Found: {list(frame.columns)}"
        )


def split_measurements(frame: pd.DataFrame, settings: Settings) -> tuple:
    """Stratified split of a measurement frame, keeping all columns.

    Returns whole DataFrames, because the `prepare` stage writes them to CSV.
    """
    require_columns(frame)
    train_frame, test_frame = train_test_split(
        frame,
        test_size=settings.test_size,
        random_state=settings.random_seed,
        stratify=frame[TARGET_COLUMN],
    )
    return train_frame, test_frame
