"""Load the diabetes data and split it. You do not need to read this module."""

from __future__ import annotations

import pandas as pd
from sklearn.model_selection import train_test_split

from .config import Settings

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

# Metadata of a batch row, not a feature: it does not exist for a new patient.
METADATA_COLUMNS = ["measurement_date"]


def load_dataframe(settings: Settings) -> pd.DataFrame:
    """Load `data/diabetes.csv`, the canonical dataset."""
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
    """Load a measurement CSV, parsing `measurement_date` when the file has it."""
    frame = pd.read_csv(path)
    if "measurement_date" in frame.columns:
        frame["measurement_date"] = pd.to_datetime(frame["measurement_date"])
    return frame


def require_columns(frame: pd.DataFrame) -> None:
    """Raise a KeyError that names the missing modelling columns."""
    missing = [c for c in FEATURE_COLUMNS + [TARGET_COLUMN] if c not in frame.columns]
    if missing:
        raise KeyError(
            f"Dataset is missing expected column(s): {missing}. "
            f"Found: {list(frame.columns)}"
        )


def split_measurements(frame: pd.DataFrame, settings: Settings) -> tuple:
    """Stratified split of a measurement frame into two frames with all columns."""
    require_columns(frame)
    train_frame, test_frame = train_test_split(
        frame,
        test_size=settings.test_size,
        random_state=settings.random_seed,
        stratify=frame[TARGET_COLUMN],
    )
    return train_frame, test_frame
