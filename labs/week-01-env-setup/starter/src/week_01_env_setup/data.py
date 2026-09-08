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


def load_dataframe(settings: Settings) -> pd.DataFrame:
    """Load the diabetes dataset from the configured CSV path."""
    return pd.read_csv(settings.data_path)


def build_dataset(settings: Settings) -> tuple:
    """Split the dataset into stratified train and test sets."""
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
