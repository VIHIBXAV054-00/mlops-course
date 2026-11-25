"""The drift policy: load and validate drift.yaml, and turn statistics into a verdict.

Pure Python and yaml with no evidently import, so the serving container can use it.
"""


from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from .data import FEATURE_COLUMNS
from .schemas import SENTINEL_COLUMNS


def contract_admissible(frame: pd.DataFrame) -> pd.DataFrame:
    """The rows this API could actually have scored. Used on both windows.

    A row with a zero in a sentinel column gets a 422 and never reaches the log, so the
    reference window must drop it too. A zero in `pregnancies` is real.
    """
    present = [column for column in SENTINEL_COLUMNS if column in frame.columns]
    if not present:
        return frame
    return frame[~(frame[present] == 0).any(axis=1)]

# INSUFFICIENT means the window was too small to measure. It is not NO_DRIFT.
INSUFFICIENT = "INSUFFICIENT"
NO_DRIFT = "NO_DRIFT"
DRIFT = "DRIFT"
DRIFT_WITH_DEGRADATION = "DRIFT_WITH_DEGRADATION"

VERDICTS = (INSUFFICIENT, NO_DRIFT, DRIFT, DRIFT_WITH_DEGRADATION)

# The direction of each method: a p-value drifts below its threshold, a distance above it.
METHODS: dict[str, dict[str, Any]] = {
    "psi": {
        "smaller_is_drift": False,
        "what": "Population Stability Index — an effect size. Does not grow with n.",
    },
    "wasserstein": {
        "smaller_is_drift": False,
        "what": "normed Wasserstein distance — an effect size, in units of std.",
    },
    "jensenshannon": {
        "smaller_is_drift": False,
        "what": "Jensen-Shannon distance between the two histograms.",
    },
    "ks": {
        "smaller_is_drift": True,
        "what": "Kolmogorov-Smirnov p-value — a SIGNIFICANCE test. Grows with n.",
    },
}


@dataclass(frozen=True)
class FeaturePolicy:
    """One row of `drift.yaml`'s `features:` list."""

    column: str
    method: str
    threshold: float
    gated: bool = False
    note: str = ""

    @property
    def smaller_is_drift(self) -> bool:
        return bool(METHODS[self.method]["smaller_is_drift"])

    def drifted(self, value: float | None) -> bool:
        """Did this feature drift? A `None` value (no statistic) is not drift."""
        if value is None:
            return False
        return value < self.threshold if self.smaller_is_drift else value > self.threshold


@dataclass(frozen=True)
class DriftPolicy:
    """Everything `drift.yaml` declares, parsed and validated."""

    service: str
    reference_path: Path
    reference_md5: str
    reference_description: str
    min_samples: int
    window_rows: int
    features: tuple[FeaturePolicy, ...]
    proxy_reference_rate: float
    proxy_max_deviation: float
    proxy_window: str
    degradation_metric: str
    degradation_min_drop: float
    degradation_also_report: tuple[str, ...]
    drift_share_threshold: float
    actions: dict[str, dict[str, str]]
    staleness_max_age: str
    staleness_expected_every: str
    staleness_severity: str

    @property
    def gated(self) -> tuple[FeaturePolicy, ...]:
        return tuple(f for f in self.features if f.gated)

    @property
    def columns(self) -> list[str]:
        return [f.column for f in self.features]

    def severity_for(self, verdict: str) -> str:
        """What `drift.yaml` says should happen. `none`, `ticket` or `page`."""
        return str(self.actions.get(verdict.lower(), {}).get("severity", "none"))


DEFAULT_POLICY_PATH = Path("drift.yaml")


def load_policy(path: Path | None = None) -> DriftPolicy:
    """Read and validate drift.yaml. Raises with a readable message on a bad value."""
    policy_path = Path(path) if path is not None else _find_policy_file()
    raw = yaml.safe_load(policy_path.read_text()) or {}

    service = str(raw.get("service") or "").strip()
    if not service:
        raise ValueError("drift.yaml: `service` must name the service this policy is about.")

    reference = raw.get("reference") or {}
    reference_path = str(reference.get("path") or "").strip()
    if not reference_path:
        raise ValueError(
            "drift.yaml: reference.path must name the window every current window "
            "is compared against. Drift is a statement about TWO datasets."
        )
    reference_md5 = str(reference.get("dataset_md5") or "").strip()
    if not reference_md5:
        raise ValueError(
            "drift.yaml: reference.dataset_md5 must pin the dataset version the "
            "reference window came from. A reference that is 'whatever is on disk' "
            "drifts along with the thing it is supposed to measure against, and a "
            "monitor built on one agrees with production forever."
        )

    current = raw.get("current") or {}
    min_samples = int(current.get("min_samples", 0))
    if min_samples <= 0:
        raise ValueError(
            "drift.yaml: current.min_samples must be positive. It is what separates "
            "NO_DRIFT ('we looked') from INSUFFICIENT ('we could not look'), and "
            "without it a monitor reports health because nobody called the service."
        )
    window_rows = int(current.get("window_rows", 0))
    if window_rows < min_samples:
        raise ValueError(
            f"drift.yaml: current.window_rows ({window_rows}) is smaller than "
            f"current.min_samples ({min_samples}), so the verdict can never be "
            f"anything but INSUFFICIENT."
        )

    features: list[FeaturePolicy] = []
    seen: set[str] = set()
    for spec in raw.get("features") or []:
        column = str(spec.get("column") or "").strip()
        if not column:
            raise ValueError("drift.yaml: every entry in `features` must name a `column`.")
        if column in seen:
            raise ValueError(
                f"drift.yaml: feature {column!r} is declared twice. Two rows for one "
                f"column means two thresholds, and nothing says which one won."
            )
        seen.add(column)
        if column not in FEATURE_COLUMNS:
            raise ValueError(
                f"drift.yaml: {column!r} is not a model feature. Watching a column "
                f"the model does not read produces a signal with no consequence. "
                f"Features: {list(FEATURE_COLUMNS)}"
            )
        method = str(spec.get("method") or "").strip()
        if method not in METHODS:
            raise ValueError(
                f"drift.yaml: features.{column}.method must be one of "
                f"{sorted(METHODS)}; got {method!r}. It is written out explicitly "
                f"and never inherited, because Evidently's own default switches "
                f"from a K-S p-value to a normed Wasserstein distance once the "
                f"reference window passes 1000 rows — silently, and with a "
                f"different threshold."
            )
        threshold = spec.get("threshold")
        if threshold is None:
            raise ValueError(
                f"drift.yaml: features.{column} declares a method and no threshold. "
                f"A statistic with no threshold is a number, not a monitor."
            )
        threshold = float(threshold)
        if not 0.0 < threshold < 1.0 and METHODS[method]["smaller_is_drift"]:
            raise ValueError(
                f"drift.yaml: features.{column}.threshold is a p-value threshold "
                f"and must be strictly between 0 and 1; got {threshold}."
            )
        if threshold <= 0:
            raise ValueError(
                f"drift.yaml: features.{column}.threshold must be positive; got {threshold}."
            )
        features.append(
            FeaturePolicy(
                column=column,
                method=method,
                threshold=threshold,
                gated=bool(spec.get("gated", False)),
                note=str(spec.get("note", "")).strip(),
            )
        )
    if not features:
        raise ValueError("drift.yaml declares no features — an empty policy watches nothing.")
    if not any(f.gated for f in features):
        raise ValueError(
            "drift.yaml declares no GATED feature, so no window can ever produce a "
            "DRIFT verdict. A policy in which nothing is a verdict is a dashboard."
        )

    proxy = raw.get("proxy") or {}
    proxy_rate = float(proxy.get("reference_positive_rate", -1))
    if not 0.0 <= proxy_rate <= 1.0:
        raise ValueError(
            "drift.yaml: proxy.reference_positive_rate must be between 0 and 1 — it "
            "is the share of positive predictions on the reference window, and the "
            "proxy alert is a deviation from it."
        )
    proxy_deviation = float(proxy.get("max_absolute_deviation", -1))
    if not 0.0 < proxy_deviation < 1.0:
        raise ValueError(
            "drift.yaml: proxy.max_absolute_deviation must be strictly between 0 and 1."
        )

    degradation = raw.get("degradation") or {}
    degradation_metric = str(degradation.get("primary_metric", "roc_auc")).strip()
    if degradation_metric == "f1":
        # f1 is allowed, but it has to be written explicitly
        pass
    if not degradation_metric:
        raise ValueError(
            "drift.yaml: degradation.primary_metric must name the metric that "
            "decides whether performance fell. Measured on this model, f1 and "
            "roc_auc give OPPOSITE answers on the same two windows — so leaving "
            "it implicit is leaving the verdict implicit."
        )
    degradation_min_drop = float(degradation.get("min_drop", 0.03))
    if degradation_min_drop <= 0:
        raise ValueError(
            "drift.yaml: degradation.min_drop must be positive. It is a noise band, "
            "not a budget for getting worse — the same distinction Week 6 draws for "
            "acceptance.regression.max_drop."
        )

    summary = raw.get("summary") or {}
    share_threshold = float(summary.get("drift_share_threshold", 0.5))
    if not 0.0 < share_threshold <= 1.0:
        raise ValueError("drift.yaml: summary.drift_share_threshold must be in (0, 1].")

    actions = {str(k).lower(): dict(v or {}) for k, v in (raw.get("actions") or {}).items()}
    for verdict in VERDICTS:
        key = verdict.lower()
        if key not in actions:
            raise ValueError(
                f"drift.yaml: actions.{key} is missing. Every verdict needs a written "
                f"action, or the verdict is a number somebody will have to interpret "
                f"under pressure at an unknown hour."
            )
        severity = str(actions[key].get("severity", "")).strip()
        if severity not in {"none", "ticket", "page"}:
            raise ValueError(
                f"drift.yaml: actions.{key}.severity must be 'none', 'ticket' or "
                f"'page'; got {severity!r}."
            )
    # Drift alone never pages: at 03:00 there is no action a woken engineer can take.
    if str(actions[DRIFT.lower()].get("severity")) == "page":
        raise ValueError(
            "drift.yaml: actions.drift.severity is 'page'. Input drift on its own "
            "does not page anybody: at 03:00 there is no action available, the model "
            "is still serving and the SLO is still being met. Use 'ticket' — and see "
            "actions.drift_with_degradation for the one verdict that does justify an "
            "interrupt, and what it costs (labels)."
        )

    staleness = raw.get("staleness") or {}
    max_age = str(staleness.get("max_age") or "").strip()
    if not max_age:
        raise ValueError(
            "drift.yaml: staleness.max_age is required. A drift monitor that stopped "
            "running reports no drift, forever, and looks exactly like good news — "
            "the only defence is to measure the clock."
        )

    return DriftPolicy(
        service=service,
        reference_path=Path(reference_path),
        reference_md5=reference_md5,
        reference_description=str(reference.get("description", "")).strip(),
        min_samples=min_samples,
        window_rows=window_rows,
        features=tuple(features),
        proxy_reference_rate=proxy_rate,
        proxy_max_deviation=proxy_deviation,
        proxy_window=str(proxy.get("window", "6h")),
        degradation_metric=degradation_metric,
        degradation_min_drop=degradation_min_drop,
        degradation_also_report=tuple(
            str(name) for name in (degradation.get("also_report") or [])
        ),
        drift_share_threshold=share_threshold,
        actions=actions,
        staleness_max_age=max_age,
        staleness_expected_every=str(staleness.get("expected_every", "24h")),
        staleness_severity=str(staleness.get("severity", "ticket")),
    )


def _find_policy_file() -> Path:
    """Next to the project root, then the working directory. Same two-step as slo.py."""
    for candidate in (
        Path(__file__).resolve().parents[2] / "drift.yaml",
        DEFAULT_POLICY_PATH,
    ):
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "drift.yaml not found. It is the declaration the drift verdict and every "
        "rule in prometheus/rules/drift.yml are derived from; run make targets from "
        "the lab directory."
    )



@dataclass
class DriftStatistics:
    """Per-feature values, plus Evidently's dataset-level share."""

    values: dict[str, float | None] = field(default_factory=dict)
    methods: dict[str, str] = field(default_factory=dict)
    share: float | None = None
    share_count: float | None = None


# ── The verdict ──────────────────────────────────────────────────────────────


def evaluate(
    policy: DriftPolicy,
    stats: DriftStatistics,
    n_current: int,
    n_reference: int,
    degradation: dict[str, Any] | None = None,
    window_age_seconds: float | None = None,
) -> dict[str, Any]:
    """Turn statistics into one of the four verdicts, with the reasons."""
    per_feature = []
    for feature in policy.features:
        value = stats.values.get(feature.column)
        per_feature.append(
            {
                "column": feature.column,
                "method": feature.method,
                # the method Evidently used, next to the one the policy asked for
                "method_used": stats.methods.get(feature.column, feature.method),
                "threshold": feature.threshold,
                "value": value,
                "drifted": feature.drifted(value),
                "gated": feature.gated,
                "smaller_is_drift": feature.smaller_is_drift,
            }
        )

    drifted = [row for row in per_feature if row["drifted"]]
    drifted_gated = [row for row in drifted if row["gated"]]

    if n_current < policy.min_samples:
        verdict = INSUFFICIENT
        reasons = [
            f"only {n_current} rows in the current window; drift.yaml requires at "
            f"least {policy.min_samples}. This is NOT a clean bill of health — we "
            f"did not measure."
        ]
    elif drifted_gated:
        reasons = [
            f"{row['column']}: {row['method']}={_fmt(row['value'])} "
            f"{'<' if row['smaller_is_drift'] else '>'} {row['threshold']} (gated)"
            for row in drifted_gated
        ]
        if degradation and degradation.get("degraded"):
            verdict = DRIFT_WITH_DEGRADATION
            reasons.append(
                "and measured performance fell on labelled data: "
                + str(degradation.get("summary", "see the degradation block"))
            )
        else:
            verdict = DRIFT
    else:
        verdict = NO_DRIFT
        reasons = [
            f"no gated feature crossed its threshold "
            f"({', '.join(f.column for f in policy.gated)})"
        ]
        if drifted:
            # report-only features that moved are listed, the verdict stays NO_DRIFT
            reasons.append(
                "report-only features that did move: "
                + ", ".join(f"{row['column']}={_fmt(row['value'])}" for row in drifted)
            )

    return {
        "verdict": verdict,
        "severity": policy.severity_for(verdict),
        "action": str(policy.actions.get(verdict.lower(), {}).get("action", "")).strip(),
        "reasons": reasons,
        "features": per_feature,
        "drifted_count": len(drifted),
        "drifted_gated_count": len(drifted_gated),
        "features_total": len(per_feature),
        # Evidently's dataset-level vote, reported but never used as the verdict
        "evidently_share": stats.share,
        "evidently_share_count": stats.share_count,
        "evidently_share_threshold": policy.drift_share_threshold,
        "n_current": n_current,
        "n_reference": n_reference,
        "min_samples": policy.min_samples,
        "window_age_seconds": window_age_seconds,
        "degradation": degradation,
    }


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.4f}"
