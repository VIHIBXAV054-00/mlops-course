from __future__ import annotations

from sklearn.ensemble import RandomForestClassifier
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

from .config import Settings

# The ML stays trivial — Week 3's complexity budget goes to MLflow, not modelling.
# What is new here is `build_model`, which lets one sweep compare several
# hyperparameter settings (and two model families) through one identical
# Pipeline shape. Comparable runs require a comparable pipeline.

MODEL_FAMILIES = ("logreg", "rf")


def train_logistic_regression(x_train, y_train, settings: Settings) -> Pipeline:
    """Train a scaled logistic regression model.

    Unchanged from Weeks 1-2, and the course's reference model:
    seed 42 gives F1 0.5785, accuracy 0.7344.

    Follows the standard Scikit-learn pattern: a Pipeline that chains
    preprocessing (StandardScaler) with an estimator, so the exact same
    transformation is applied at training and prediction time.
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


def build_model(family: str, hyperparams: dict, settings: Settings) -> Pipeline:
    """Build one UNFITTED pipeline for a single sweep cell.

    Scaling is harmless for a random forest and required for logistic
    regression, so both families share the same Pipeline shape. That is what
    makes the sweep runs genuinely comparable rather than merely adjacent.

    With sklearn's defaults (`C=1.0` for logreg, `n_estimators=100` for the
    forest) this reproduces the Week 1/2 baselines exactly.
    """
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

    return Pipeline(steps=[("scaler", StandardScaler()), ("classifier", estimator)])


def evaluate_model(model, x_test, y_test) -> dict:
    """Compute standard binary classification metrics on the test set.

    New in Week 3: `roc_auc`. It is threshold-independent, so it ranks models
    differently from F1 — which is the point of Exercise 4. It requires a
    classifier exposing `predict_proba`; both families above do.

    Values are rounded to 4 decimals, which is what keeps the course's pinned
    reference metrics stable across machines.
    """
    predictions = model.predict(x_test)
    probabilities = model.predict_proba(x_test)[:, 1]
    return {
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "precision": round(float(precision_score(y_test, predictions)), 4),
        "recall": round(float(recall_score(y_test, predictions)), 4),
        "f1": round(float(f1_score(y_test, predictions)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, probabilities)), 4),
    }
