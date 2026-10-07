"""Build, train and score the model."""

from __future__ import annotations

from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import IMPUTE_STRATEGIES, Settings

MODEL_FAMILIES = ("logreg", "rf")


def train_logistic_regression(x_train, y_train, settings: Settings) -> Pipeline:
    """Train a scaled logistic regression model.

    https://scikit-learn.org/stable/getting_started.html
    """
    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    max_iter=settings.max_iter,
                    random_state=settings.random_seed,
                ),
            ),
        ]
    )
    model.fit(x_train, y_train)
    return model


def build_model(
    family: str, hyperparams: dict, settings: Settings, impute: str | None = None
) -> Pipeline:
    """Build one unfitted pipeline: an imputer if `impute` is set, a scaler, the estimator."""
    if family == "logreg":
        estimator = LogisticRegression(
            max_iter=settings.max_iter,
            random_state=settings.random_seed,
            **hyperparams,
        )
    elif family == "rf":
        estimator = RandomForestClassifier(
            random_state=settings.random_seed,
            **hyperparams,
        )
    else:
        raise ValueError(
            f"Unknown model family {family!r}; expected one of {MODEL_FAMILIES}."
        )

    steps = []
    # TODO(student) Exercise 5: when `impute` is not None, add a step named
    # "imputer" before the scaler, which fills missing values with the `impute`
    # strategy. Raise a ValueError for a strategy that is not in IMPUTE_STRATEGIES.
    # Reference: https://scikit-learn.org/stable/modules/generated/sklearn.impute.SimpleImputer.html
    steps.append(("scaler", StandardScaler()))
    steps.append(("classifier", estimator))
    return Pipeline(steps=steps)


def evaluate_model(model, x_test, y_test) -> dict:
    """Compute binary classification metrics on the test set, rounded to 4 places."""
    predictions = model.predict(x_test)
    probabilities = model.predict_proba(x_test)[:, 1]
    return {
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "precision": round(float(precision_score(y_test, predictions)), 4),
        "recall": round(float(recall_score(y_test, predictions)), 4),
        "f1": round(float(f1_score(y_test, predictions)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4),
    }
