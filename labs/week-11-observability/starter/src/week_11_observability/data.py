"""Load the dataset and split it into train and test sets."""

from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split

from .config import Settings

# `load_dataframe` and `build_dataset` read data/diabetes.csv, the committed snapshot.
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

# not a feature: a new patient has no measurement date at prediction time
METADATA_COLUMNS = ["measurement_date"]


def load_dataframe(settings: Settings) -> pd.DataFrame:
    """Load the committed snapshot from the configured CSV path."""
    return pd.read_csv(settings.data_path)


def build_dataset(settings: Settings) -> tuple:
    """Split the committed snapshot into stratified train and test sets."""
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
    """Load a batch file or diabetes.csv, parsing `measurement_date` when it is present."""
    frame = pd.read_csv(path)
    if "measurement_date" in frame.columns:
        frame["measurement_date"] = pd.to_datetime(frame["measurement_date"])
    return frame


def require_columns(frame: pd.DataFrame) -> None:
    """Raise a readable KeyError if a feature or the target column is missing."""
    missing = [c for c in FEATURE_COLUMNS + [TARGET_COLUMN] if c not in frame.columns]
    if missing:
        raise KeyError(
            f"Dataset is missing expected column(s): {missing}. "
            f"Found: {list(frame.columns)}"
        )


def split_measurements(frame: pd.DataFrame, settings: Settings) -> tuple:
    """Stratified split that keeps every column, `measurement_date` included."""
    require_columns(frame)
    train_frame, test_frame = train_test_split(
        frame,
        test_size=settings.test_size,
        random_state=settings.random_seed,
        stratify=frame[TARGET_COLUMN],
    )
    return train_frame, test_frame
