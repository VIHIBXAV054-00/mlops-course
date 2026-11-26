"""A custom Prometheus collector that reads reports/drift.json on every scrape.

It never raises, and with no report it still publishes a timestamp of 0 so DriftReportStale fires.
https://prometheus.github.io/client_python/collector/custom/
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from prometheus_client.core import GaugeMetricFamily

from .drift_policy import VERDICTS

# what `make drift-report` writes, and what compose.yaml mounts into the container
DEFAULT_REPORT_PATH = Path("reports/drift.json")

# published when there is no readable report, so the staleness alert can fire
NO_REPORT_TIMESTAMP = 0.0


class DriftCollector:
    """Reads `reports/drift.json` on every scrape and yields the drift series. No caching."""

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_REPORT_PATH

    # prometheus_client calls collect() on every scrape. It must not raise.
    def collect(self) -> Iterable[GaugeMetricFamily]:  # noqa: C901 - a flat series of guards
        report = self._read()

        timestamp = GaugeMetricFamily(
            "model_drift_report_timestamp_seconds",
            "Unix timestamp of the drift report this service is publishing. "
            "0 means no report has ever been produced.",
        )
        if report is None:
            # no readable report: publish only the zero timestamp
            timestamp.add_metric([], NO_REPORT_TIMESTAMP)
            yield timestamp
            return

        timestamp.add_metric([], _number(report.get("computed_at"), NO_REPORT_TIMESTAMP))
        yield timestamp

        # per-feature statistic. `method` is a label because psi and ks have different scales.
        scores = GaugeMetricFamily(
            "model_drift_score",
            "Per-feature drift statistic from the latest drift report.",
            labels=["feature", "method"],
        )
        thresholds = GaugeMetricFamily(
            "model_drift_threshold",
            "The threshold each feature's statistic is compared against.",
            labels=["feature", "method"],
        )
        gated = GaugeMetricFamily(
            "model_drift_feature_gated",
            "1 if drift in this feature can produce a DRIFT verdict, 0 if report-only.",
            labels=["feature"],
        )
        for row in report.get("features") or []:
            if not isinstance(row, dict):
                continue
            column = str(row.get("column", "")) or "unknown"
            method = str(row.get("method", "")) or "unknown"
            value = _number(row.get("value"), None)
            # a null statistic is no series, not 0: 0 is a real psi value
            if value is not None:
                scores.add_metric([column, method], value)
            threshold = _number(row.get("threshold"), None)
            if threshold is not None:
                thresholds.add_metric([column, method], threshold)
            gated.add_metric([column], 1.0 if row.get("gated") else 0.0)
        yield scores
        yield thresholds
        yield gated

        # the counts the verdict rests on, with the total for context
        drifted = GaugeMetricFamily(
            "model_drift_features_drifted",
            "Features whose statistic crossed its threshold in the latest report.",
        )
        drifted.add_metric([], _number(report.get("drifted_count"), 0.0))
        yield drifted

        drifted_gated = GaugeMetricFamily(
            "model_drift_features_drifted_gated",
            "GATED features whose statistic crossed its threshold. Non-zero means DRIFT.",
        )
        drifted_gated.add_metric([], _number(report.get("drifted_gated_count"), 0.0))
        yield drifted_gated

        total = GaugeMetricFamily(
            "model_drift_features_total",
            "Features watched by drift.yaml.",
        )
        total.add_metric([], _number(report.get("features_total"), 0.0))
        yield total

        rows = GaugeMetricFamily(
            "model_drift_window_rows",
            "Rows in the current window the latest report was computed over.",
        )
        rows.add_metric([], _number(report.get("n_current"), 0.0))
        yield rows

        # The verdict as an info metric: one series per possible verdict, exactly one is 1.
        # A single series labelled with the verdict would start a new series at every change.
        verdict_now = str(report.get("verdict", "")).upper()
        verdict = GaugeMetricFamily(
            "model_drift_verdict",
            "1 for the verdict of the latest drift report, 0 for the others.",
            labels=["verdict"],
        )
        for candidate in VERDICTS:
            verdict.add_metric([candidate], 1.0 if candidate == verdict_now else 0.0)
        yield verdict

        # Age of the newest row in the window. A fresh report can still be computed on old rows.
        age = _number((report.get("current") or {}).get("age_seconds"), None)
        if age is not None:
            window_age = GaugeMetricFamily(
                "model_drift_window_age_seconds",
                "Age of the newest row in the window the latest report was computed over.",
            )
            window_age.add_metric([], age)
            yield window_age

        # the reference positive rate, so PromQL needs no hard-coded number
        proxy = _number((report.get("proxy") or {}).get("reference_positive_rate"), None)
        if proxy is not None:
            reference_rate = GaugeMetricFamily(
                "model_reference_positive_rate",
                "Share of positive predictions on the reference window, from drift.yaml.",
            )
            reference_rate.add_metric([], proxy)
            yield reference_rate

    def _read(self) -> dict[str, Any] | None:
        """The report, or `None` if it is missing or unreadable. Never raises."""
        try:
            if not self.path.exists():
                return None
            report = json.loads(self.path.read_text())
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            return None
        if not isinstance(report, dict):
            return None
        return report


def _number(value: Any, default: float | None) -> float | None:
    """Coerce to float, or return `default`, so a bad value in the report cannot raise."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
