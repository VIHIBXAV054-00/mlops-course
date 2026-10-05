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
    """
    fig, ax = plt.subplots(figsize=(5, 5))
    RocCurveDisplay.from_estimator(
        model, x_test, y_test, ax=ax, name=label, plot_chance_level=True
    )
    ax.set_title("ROC curve — diabetes classifier")
    fig.tight_layout()
    return fig


def confusion_matrix_figure(model, x_test, y_test) -> plt.Figure:
    """Plot the confusion matrix for a fitted classifier on the test set.

    This is the plot that makes a mediocre recall concrete: the bottom-left
    cell is the count of diabetic patients the model called healthy.
    """
    fig, ax = plt.subplots(figsize=(5, 5))
    ConfusionMatrixDisplay.from_estimator(
        model,
        x_test,
        y_test,
        ax=ax,
        display_labels=["no diabetes", "diabetes"],
        colorbar=False,
    )
    ax.set_title("Confusion matrix — test set")
    fig.tight_layout()
    return fig
