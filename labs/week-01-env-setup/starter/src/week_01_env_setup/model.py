from __future__ import annotations

from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .config import Settings


def train_logistic_regression(x_train, y_train, settings: Settings) -> Pipeline:
    """Train a scaled logistic regression model.

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


def evaluate_model(model, x_test, y_test) -> dict:
    """Compute standard binary classification metrics on the test set."""
    predictions = model.predict(x_test)
    return {
        "accuracy": round(float(accuracy_score(y_test, predictions)), 4),
        "precision": round(float(precision_score(y_test, predictions)), 4),
        "recall": round(float(recall_score(y_test, predictions)), 4),
        "f1": round(float(f1_score(y_test, predictions)), 4),
    }
