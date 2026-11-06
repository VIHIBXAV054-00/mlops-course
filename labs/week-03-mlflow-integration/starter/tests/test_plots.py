"""Tests for the diagnostic plots (Exercise 2).

No tracking server required — the figures are built and inspected in memory.
That is exactly why plots.py returns a Figure instead of logging it directly.
"""

import matplotlib.figure
import pytest

from week_03_mlflow_integration.config import load_settings
from week_03_mlflow_integration.data import build_dataset
from week_03_mlflow_integration.model import build_model
from week_03_mlflow_integration.plots import (
    confusion_matrix_figure,
    roc_curve_figure,
)


@pytest.fixture(scope="module")
def fitted_model():
    settings = load_settings()
    x_train, x_test, y_train, y_test = build_dataset(settings)
    model = build_model("logreg", {"C": 1.0}, settings)
    model.fit(x_train, y_train)
    return model, x_test, y_test


def test_roc_curve_figure_returns_figure(fitted_model) -> None:
    """roc_curve_figure returns a matplotlib Figure."""
    model, x_test, y_test = fitted_model
    figure = roc_curve_figure(model, x_test, y_test, label="logreg")
    assert isinstance(figure, matplotlib.figure.Figure)


def test_confusion_matrix_figure_returns_figure(fitted_model) -> None:
    """confusion_matrix_figure returns a matplotlib Figure."""
    model, x_test, y_test = fitted_model
    figure = confusion_matrix_figure(model, x_test, y_test)
    assert isinstance(figure, matplotlib.figure.Figure)


def test_roc_curve_figure_is_populated(fitted_model) -> None:
    """The ROC figure has a titled axes with the curve and the chance line."""
    model, x_test, y_test = fitted_model
    figure = roc_curve_figure(model, x_test, y_test, label="logreg")
    axes = figure.axes[0]
    assert "ROC" in axes.get_title()
    # One line for the model, one dashed line for chance level.
    assert len(axes.get_lines()) >= 2


def test_confusion_matrix_figure_has_four_cells(fitted_model) -> None:
    """The confusion matrix has 4 cells whose counts sum to the test-set size."""
    model, x_test, y_test = fitted_model
    figure = confusion_matrix_figure(model, x_test, y_test)
    axes = figure.axes[0]
    counts = [
        int(text.get_text())
        for text in axes.texts
        if text.get_text().strip().isdigit()
    ]
    assert len(counts) == 4
    assert sum(counts) == len(y_test)
