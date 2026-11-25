"""Drift statistics: Evidently compares the reference and current windows, one number per feature.

drift_policy.py decides what the numbers mean. The serving image does not install evidently.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd

from .drift_policy import DriftPolicy, DriftStatistics, _fmt, contract_admissible, evaluate

# ── The reference window ─────────────────────────────────────────────────────


def load_reference(
    policy: DriftPolicy, project_root: Path | None = None, filtered: bool = True
) -> pd.DataFrame:
    """The reference window, filtered by the same contract rule as the current window.

    `filtered=False` skips the filter. Exercise 2 uses it to show the false drift it causes.

    The dataset md5 in drift.yaml is checked by tests/test_drift_policy.py, not here.
    """
    root = project_root or Path(__file__).resolve().parents[2]
    path = root / policy.reference_path
    if not path.exists():
        raise FileNotFoundError(
            f"reference window {path} does not exist. It is produced by the "
            f"`prepare` stage, so run the pipeline first:\n    make repro"
        )
    frame = pd.read_csv(path)
    missing = [column for column in policy.columns if column not in frame.columns]
    if missing:
        raise KeyError(
            f"the reference window at {path} has no column(s) {missing}, which "
            f"drift.yaml watches. One of the two was changed without the other."
        )
    admissible = contract_admissible(frame) if filtered else frame
    admissible.attrs["reference_rows_raw"] = len(frame)
    admissible.attrs["reference_rows_admissible"] = len(admissible)
    admissible.attrs["reference_path"] = str(path)
    return admissible


# ── The statistics ───────────────────────────────────────────────────────────


def compute_statistics(
    reference: pd.DataFrame,
    current: pd.DataFrame,
    policy: DriftPolicy,
    html_path: Path | None = None,
) -> DriftStatistics:
    """Run Evidently on both windows and pull out one statistic per feature.

    `Report.run()` takes (current, reference), current first. With psi a swapped order gives the
    same number, so only a test catches it.
    """
    # imported here, so the module still imports where evidently is not installed
    try:
        from evidently import DataDefinition, Dataset, Report
        from evidently.metrics import ValueDrift
        from evidently.presets import DataDriftPreset
    except ImportError as exc:  # pragma: no cover - exercised by the image, not the suite
        raise ImportError(
            "evidently is not installed. It lives in the `drift` dependency group "
            "so that the serving image never carries it:\n"
            "    uv sync --group drift        (or --all-groups)\n"
            "If you are seeing this inside the serving container, that is the design "
            "working: the process that scores patients does not audit them."
        ) from exc

    columns = policy.columns
    definition = DataDefinition(numerical_columns=list(columns))
    reference_ds = Dataset.from_pandas(
        reference[columns].reset_index(drop=True), data_definition=definition
    )
    current_ds = Dataset.from_pandas(
        current[columns].reset_index(drop=True), data_definition=definition
    )

    stats = DriftStatistics()

    # one ValueDrift per feature, with the method the policy declares
    metrics = [ValueDrift(column=f.column, method=f.method) for f in policy.features]
    # current first, then reference
    result = Report(metrics).run(current_ds, reference_ds)
    for entry in result.dict().get("metrics", []):
        config = entry.get("config") or {}
        # read `config`, not the display string in `metric_name`
        column = config.get("column")
        if column in stats.values or column not in columns:
            continue
        value = entry.get("value")
        stats.values[column] = None if value is None else float(value)
        stats.methods[column] = str(config.get("method", ""))

    # the preset once more, only for its dataset-level share
    preset = Report([DataDriftPreset()]).run(current_ds, reference_ds)
    # the HTML report is for a human reading the numbers
    if html_path is not None:
        html_path.parent.mkdir(parents=True, exist_ok=True)
        preset.save_html(str(html_path))
    for entry in preset.dict().get("metrics", []):
        config = entry.get("config") or {}
        if str(config.get("type", "")).endswith("DriftedColumnsCount"):
            value = entry.get("value") or {}
            stats.share = _maybe_float(value.get("share"))
            stats.share_count = _maybe_float(value.get("count"))
            break

    missing = [column for column in columns if column not in stats.values]
    if missing:
        raise RuntimeError(
            f"evidently returned no statistic for {missing}. This is an error rather "
            f"than a skipped feature on purpose: a monitor that quietly stops "
            f"watching a gated column reports NO_DRIFT for the rest of its life."
        )
    return stats


def _maybe_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


# ── Does the drift MATTER? ───────────────────────────────────────────────────


def measure_degradation(
    model_path: Path,
    reference: pd.DataFrame,
    current: pd.DataFrame,
    primary_metric: str = "roc_auc",
    min_drop: float = 0.03,
) -> dict[str, Any]:
    """Score the model on both labelled windows and say whether it got worse.

    It needs labels for the current window. The lab has them, production rarely does.

    The default is roc_auc: it does not depend on prevalence, and F1 does.
    """
    import joblib  # local: keeps `drift_policy` importable without sklearn's cost

    from .evaluation import group_metrics
    from .pipeline import prepare_model_input

    if not Path(model_path).exists():
        raise FileNotFoundError(
            f"no model at {model_path}. Degradation is measured with the model that "
            f"is actually serving, not a fresh one — run `make repro` first."
        )
    model = joblib.load(model_path)

    def score(frame: pd.DataFrame, label: str) -> dict[str, Any]:
        if "outcome" not in frame.columns:
            raise KeyError(
                f"the {label} window has no `outcome` column, so performance cannot "
                f"be measured on it. THAT IS THE NORMAL CASE IN PRODUCTION: without "
                f"labels you can detect that the inputs moved and nothing at all "
                f"about whether the model is still right. Use the input-drift "
                f"verdict and the proxy, and see drift.yaml's actions block."
            )
        features, labels, _ = prepare_model_input(frame)
        # One group: the whole window.
        scores = group_metrics(
            labels,
            model.predict(features),
            model.predict_proba(features)[:, 1],
            ["window"] * len(labels),
        )["window"]
        scores["window"] = label
        return scores

    before = score(reference, "reference")
    after = score(current, "current")
    drop = (before.get(primary_metric) or 0.0) - (after.get(primary_metric) or 0.0)
    degraded = drop > min_drop

    return {
        "degraded": bool(degraded),
        "primary_metric": primary_metric,
        "min_drop": min_drop,
        "drop": round(float(drop), 4),
        "reference": before,
        "current": after,
        "summary": (
            f"{primary_metric} {before.get(primary_metric)} -> {after.get(primary_metric)} "
            f"(drop {drop:+.4f}, threshold {min_drop})"
        ),
        # always reported, so a reader can compare it with the primary metric
        "roc_auc_moved": {
            "reference": before.get("roc_auc"),
            "current": after.get("roc_auc"),
        },
        "predicted_positive_rate": {
            "reference": before.get("selection_rate"),
            "current": after.get("selection_rate"),
        },
    }


def build_report(
    policy: DriftPolicy,
    reference: pd.DataFrame,
    current: pd.DataFrame,
    provenance: dict[str, Any] | None = None,
    degradation: dict[str, Any] | None = None,
    window_age_seconds: float | None = None,
    now: float | None = None,
    html_path: Path | None = None,
) -> dict[str, Any]:
    """Statistics, verdict and provenance: the whole `reports/drift.json`.

    `computed_at` is what `DriftReportStale` watches. `now` makes it testable.
    """
    stats = compute_statistics(reference, current, policy, html_path=html_path)
    verdict = evaluate(
        policy,
        stats,
        n_current=len(current),
        n_reference=len(reference),
        degradation=degradation,
        window_age_seconds=window_age_seconds,
    )
    return {
        "schema": "drift-report/1",
        "service": policy.service,
        "computed_at": time.time() if now is None else float(now),
        "reference": {
            "path": str(policy.reference_path),
            "dataset_md5": policy.reference_md5,
            "description": policy.reference_description,
            "rows": len(reference),
        },
        "current": {
            "rows": len(current),
            "window_rows": policy.window_rows,
            "age_seconds": window_age_seconds,
        },
        # from drift.yaml, so the alerting rule needs no hard-coded rate
        "proxy": {
            "reference_positive_rate": policy.proxy_reference_rate,
            "max_absolute_deviation": policy.proxy_max_deviation,
            "window": policy.proxy_window,
        },
        "model": provenance or {},
        **verdict,
    }


def write_report(report: dict[str, Any], path: Path) -> Path:
    """Write `reports/drift.json` with sorted keys and indentation, so it diffs well."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return path


def read_report(path: Path) -> dict[str, Any]:
    """Read a drift report, with an error that says what to run."""
    if not Path(path).exists():
        raise FileNotFoundError(
            f"no drift report at {path}. Produce one with:\n    make drift-report"
        )
    return json.loads(Path(path).read_text())


def format_report(report: dict[str, Any]) -> str:
    """What `make drift-report` prints."""
    lines: list[str] = []
    reference = report.get("reference", {})
    lines.append(
        f"Drift report for `{report.get('service', '?')}` — "
        f"{report.get('n_current', 0)} current rows vs "
        f"{reference.get('rows', 0)} reference rows"
    )
    lines.append(f"  reference : {reference.get('path')}  (dataset md5 {reference.get('dataset_md5', '')[:12]}…)")
    model = report.get("model") or {}
    if model:
        lines.append(
            f"  model     : version {model.get('model_version', '?')} · "
            f"gate {model.get('gate_verdict', '?')}"
        )
    lines.append("")
    lines.append("  feature             method   value     threshold   verdict")
    lines.append("  " + "-" * 62)
    for row in report.get("features", []):
        mark = "DRIFT" if row["drifted"] else "-"
        gate = " (gated)" if row["gated"] else ""
        lines.append(
            f"  {row['column']:<18}  {row['method']:<7}  {_fmt(row['value']):>8}  "
            f"{'>' if not row['smaller_is_drift'] else '<'} {row['threshold']:<9}  {mark}{gate}"
        )
    lines.append("")
    share = report.get("evidently_share")
    if share is not None:
        lines.append(
            f"  Evidently's own dataset-level vote: {report.get('evidently_share_count', 0):.0f}"
            f"/{report.get('features_total', 0)} features, share {share:.3f} against "
            f"{report.get('evidently_share_threshold')}"
        )
        lines.append(
            "  Reported, never used as the verdict. A top-level boolean is a vote,"
        )
        lines.append("  and a vote can be lost by a landslide. See drift.yaml `summary`.")
        lines.append("")
    lines.append(f"  VERDICT   : {report.get('verdict')}   (severity: {report.get('severity')})")
    for reason in report.get("reasons", []):
        lines.append(f"      · {reason}")
    action = report.get("action")
    if action:
        lines.append("")
        lines.append("  ACTION    : " + " ".join(action.split()))
    age = report.get("current", {}).get("age_seconds")
    if age is not None:
        lines.append("")
        lines.append(
            f"  the newest row in this window is {age / 60:.1f} minutes old. A window "
            f"whose numbers are fine\n  and whose rows are three days old is a monitor "
            f"nobody is feeding."
        )
    return "\n".join(lines)
