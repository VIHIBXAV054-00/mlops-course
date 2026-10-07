"""Diagnostic plots, built as figures so MLflow can log them as artifacts.

New in Week 3. Two design rules worth copying into your own projects:

1. The backend is forced to "Agg" BEFORE pyplot is imported. Otherwise
   matplotlib may pick a GUI backend (likely on macOS) and try to open a
   window from a background process.
2. These functions RETURN a Figure and never call plt.show() or plt.savefig().
   Returning the figure is what makes them unit-testable with no MLflow server
   and no files on disk — the caller decides what to do with it.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")  # headless: never try to open a window

import matplotlib.pyplot as plt  # noqa: E402  (must follow matplotlib.use)
from sklearn.metrics import ConfusionMatrixDisplay, RocCurveDisplay  # noqa: E402


def roc_curve_figure(model, x_test, y_test, *, label: str = "model") -> plt.Figure:
    """Plot the ROC curve for a fitted classifier on the test set.

    The ROC curve is threshold-independent: it shows how the model would behave
    at *every* decision threshold, not just the 0.5 default that `predict` uses.
    The dashed chance line is what a coin flip would score.

    TODO(student) — Exercise 2: draw the ROC curve of `model` on the test set
    onto `ax` with RocCurveDisplay, named `label`, with the dashed chance line.
    Give the axes a title that contains "ROC", call fig.tight_layout() so the
    labels are not cut off, and return the figure. Do not show or save it: the
    caller logs it with mlflow.log_figure.
    Reference: https://scikit-learn.org/stable/modules/generated/sklearn.metrics.RocCurveDisplay.html
    """
    fig, ax = plt.subplots(figsize=(5, 5))
    # Placeholder — a valid but empty Figure, so the starter's tests still run.
    return fig


def confusion_matrix_figure(model, x_test, y_test) -> plt.Figure:
    """Plot the confusion matrix for a fitted classifier on the test set.

    This is the plot that makes a mediocre recall concrete: the bottom-left
    cell is the count of diabetic patients the model called healthy.

    TODO(student) — Exercise 2: draw the confusion matrix of `model` on the test
    set onto `ax` with ConfusionMatrixDisplay, with the class names
    "no diabetes" and "diabetes" and no colour bar. Title the axes, call
    fig.tight_layout(), and return the figure.
    Reference: https://scikit-learn.org/stable/modules/generated/sklearn.metrics.ConfusionMatrixDisplay.html
    """
    fig, ax = plt.subplots(figsize=(5, 5))
    # Placeholder — a valid but empty Figure, so the starter's tests still run.
    return fig
