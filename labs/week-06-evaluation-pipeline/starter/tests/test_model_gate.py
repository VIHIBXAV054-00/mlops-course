"""The model gate as a pipeline stage, and as the check that `register` and `promote` call.

A failing model gate writes its report and keeps `models/model.pkl`. Every test
builds a project directory in `tmp_path`, so no Docker, Silo or DVC is needed.
"""

from __future__ import annotations

import dataclasses
import json

import pandas as pd
import pytest

from week_06_evaluation_pipeline import pipeline
from week_06_evaluation_pipeline.baseline import (
    read_baseline,
    score_on_test_set,
    write_baseline,
)
from week_06_evaluation_pipeline.data import split_measurements
from week_06_evaluation_pipeline.model import build_model
from week_06_evaluation_pipeline.pipeline import GateFailed

GOOD_METRICS = {
    "accuracy": 0.7656, "precision": 0.6964, "recall": 0.5821,
    "f1": 0.6341, "roc_auc": 0.8345,
}
SLICES = {
    "n_rows": 192,
    "n_positives": 67,
    "slices": {"age_band": {
        "21-29": {"n": 94, "n_positives": 21, "f1": 0.6316, "accuracy": 0.8511,
                  "precision": 0.7059, "recall": 0.5714, "roc_auc": 0.8656,
                  "selection_rate": 0.1809, "fpr": 0.0685},
        "50+": {"n": 19, "n_positives": 7, "f1": 0.5000, "accuracy": 0.5789,
                "precision": 0.4444, "recall": 0.5714, "roc_auc": 0.6071,
                "selection_rate": 0.4737, "fpr": 0.4167},
    }},
    "fairness": {"age_band": {
        "groups": {}, "selection_rate_gap": 0.0070, "tpr_gap": 0.1562,
        "fpr_gap": 0.0139, "equalized_odds_difference": 0.1562,
        "min_group_for_gap": 5,
    }},
}


@pytest.fixture
def sandbox(settings, tmp_path):
    """A settings object with every path inside `tmp_path` and MLflow unreachable."""
    return dataclasses.replace(
        settings,
        project_root=tmp_path,
        metrics_path=tmp_path / "metrics" / "metrics.json",
        slices_path=tmp_path / "metrics" / "slices.json",
        baseline_path=tmp_path / "metrics" / "baseline.json",
        gate_report_path=tmp_path / "reports" / "gate.json",
        models_dir=tmp_path / "models",
        run_id_path=tmp_path / "models" / "mlflow_run_id.json",
        mlflow_tracking_uri="http://127.0.0.1:1",  # unreachable
        acceptance={
            "criteria_version": "test-1",
            "minimum": {"accuracy": 0.70, "f1": 0.55, "roc_auc": 0.75},
            "regression": {"primary_metric": "f1", "max_drop": 0.01},
            "slice_rules": {"min_support": 20, "min_positives": 10,
                            "min_f1": 0.50, "max_f1_gap": 0.15},
            "fairness": {"age_band": {"max_selection_rate_gap": 0.10,
                                      "max_tpr_gap": 0.20}},
        },
    )


def seed(sandbox, metrics=None, slices=None, baseline=True, model=True) -> None:
    sandbox.metrics_path.parent.mkdir(parents=True, exist_ok=True)
    sandbox.metrics_path.write_text(json.dumps(metrics or GOOD_METRICS, indent=2))
    sandbox.slices_path.write_text(json.dumps(slices or SLICES, indent=2))
    if baseline:
        write_baseline({"source": "test", "metrics": dict(GOOD_METRICS)},
                       sandbox.baseline_path)
    if model:
        sandbox.models_dir.mkdir(parents=True, exist_ok=True)
        (sandbox.models_dir / "model.pkl").write_bytes(b"not really a model")


def test_a_passing_gate_writes_its_verdict_and_returns_it(sandbox):
    seed(sandbox)
    report = pipeline.gate(sandbox)
    assert report["verdict"] == "GO"
    assert json.loads(sandbox.gate_report_path.read_text())["verdict"] == "GO"


def test_a_failing_gate_raises_but_writes_the_report_first(sandbox):
    """The report is written before `GateFailed` is raised."""
    seed(sandbox, metrics=dict(GOOD_METRICS, f1=0.20))
    with pytest.raises(GateFailed, match="NO-GO"):
        pipeline.gate(sandbox)
    written = json.loads(sandbox.gate_report_path.read_text())
    assert written["verdict"] == "NO-GO"
    assert any(c["status"] == "fail" for c in written["checks"])


def test_a_failing_gate_does_not_delete_the_model(sandbox):
    """A NO-GO keeps `models/model.pkl`, so the failure can be investigated."""
    seed(sandbox, metrics=dict(GOOD_METRICS, f1=0.20))
    model = sandbox.models_dir / "model.pkl"
    before = model.read_bytes()
    with pytest.raises(GateFailed):
        pipeline.gate(sandbox)
    assert model.is_file()
    assert model.read_bytes() == before


def test_the_gate_report_is_byte_identical_across_runs(sandbox):
    """The gate report has no timestamp: two runs write the same bytes."""
    seed(sandbox)
    pipeline.gate(sandbox)
    first = sandbox.gate_report_path.read_bytes()
    pipeline.gate(sandbox)
    assert sandbox.gate_report_path.read_bytes() == first


def test_the_slice_report_the_gate_reads_is_the_one_evaluate_wrote(sandbox):
    """`read_slices` returns the file that `evaluate` wrote."""
    seed(sandbox)
    assert pipeline.read_slices(sandbox) == SLICES


def test_missing_metrics_is_a_clear_message_not_a_key_error(sandbox):
    seed(sandbox)
    sandbox.metrics_path.unlink()
    with pytest.raises(FileNotFoundError, match="evaluate stage"):
        pipeline.gate(sandbox)


def test_an_absent_baseline_skips_the_regression_check_and_still_gates(sandbox):
    seed(sandbox, baseline=False)
    report = pipeline.gate(sandbox)
    regression = [c for c in report["checks"] if c["kind"] == "regression"][0]
    assert regression["status"] == "skipped"
    assert report["verdict"] == "GO"
    assert report["summary"]["skipped"] >= 1
    assert read_baseline(sandbox.baseline_path) == {}


# ── require_go: the teeth ─────────────────────────────────────────────────────


def test_require_go_refuses_when_the_gate_has_never_run(sandbox):
    seed(sandbox)
    with pytest.raises(GateFailed, match="never"):
        pipeline.require_go(sandbox)


def test_require_go_refuses_a_recorded_no_go(sandbox):
    seed(sandbox, metrics=dict(GOOD_METRICS, f1=0.20))
    with pytest.raises(GateFailed):
        pipeline.gate(sandbox)
    with pytest.raises(GateFailed, match="Refusing to release"):
        pipeline.require_go(sandbox)


def test_require_go_accepts_a_recorded_go(sandbox):
    seed(sandbox)
    pipeline.gate(sandbox)
    assert pipeline.require_go(sandbox)["verdict"] == "GO"


def test_a_stale_go_is_still_a_go_and_that_is_the_dangerous_part(sandbox):
    """`require_go` reads a file: a GO stays a GO after the model on disk changes."""
    seed(sandbox)
    pipeline.gate(sandbox)
    (sandbox.models_dir / "model.pkl").write_bytes(b"a completely different model")
    assert pipeline.require_go(sandbox)["verdict"] == "GO"


# ── the baseline file ─────────────────────────────────────────────────────────


def test_the_baseline_file_has_no_timestamp(sandbox):
    write_baseline({"source": "test", "metrics": dict(GOOD_METRICS)},
                   sandbox.baseline_path)
    text = sandbox.baseline_path.read_text()
    assert "time" not in text.lower() and "date" not in text.lower()


def test_the_baseline_is_written_with_stable_key_order(sandbox):
    """`write_baseline` writes the same bytes whatever the key order of its input."""
    write_baseline({"metrics": {"roc_auc": 0.8, "f1": 0.6}, "source": "a"},
                   sandbox.baseline_path)
    first = sandbox.baseline_path.read_bytes()
    write_baseline({"source": "a", "metrics": {"f1": 0.6, "roc_auc": 0.8}},
                   sandbox.baseline_path)
    assert sandbox.baseline_path.read_bytes() == first


def test_a_baseline_without_metrics_reads_as_no_baseline(sandbox):
    """A baseline file without metrics counts as no baseline."""
    sandbox.baseline_path.parent.mkdir(parents=True, exist_ok=True)
    sandbox.baseline_path.write_text('{"source": "nothing yet"}')
    assert read_baseline(sandbox.baseline_path) == {}


def test_the_champion_is_scored_on_the_test_split_it_is_given(settings, tmp_path):
    """A stored score is true only for its test set, so `baseline-sync` scores the champion again."""
    train_frame, test_frame = split_measurements(pd.read_csv(settings.data_path), settings)
    features, labels, _ = pipeline.prepare_model_input(train_frame)
    model = build_model("logreg", {"C": 1.0}, settings, impute="median").fit(features, labels)

    test_frame.to_csv(tmp_path / "today.csv", index=False)
    test_frame.iloc[: len(test_frame) // 2].to_csv(tmp_path / "smaller.csv", index=False)

    today = score_on_test_set(model, tmp_path / "today.csv")
    smaller = score_on_test_set(model, tmp_path / "smaller.csv")
    assert set(today) == {"accuracy", "precision", "recall", "f1", "roc_auc"}
    assert today != smaller, "a different test split must give a different baseline"


def test_baseline_sync_scores_the_champion_it_loads_by_alias(settings, tmp_path, monkeypatch):
    """The baseline is the champion, found by its alias and scored on today's test split."""
    import mlflow.sklearn
    import mlflow.tracking

    from week_06_evaluation_pipeline.baseline import baseline_from_registry

    train_frame, test_frame = split_measurements(pd.read_csv(settings.data_path), settings)
    features, labels, _ = pipeline.prepare_model_input(train_frame)
    model = build_model("logreg", {"C": 1.0}, settings, impute="median").fit(features, labels)
    (tmp_path / "processed").mkdir()
    test_path = tmp_path / "processed" / "test.csv"
    test_frame.to_csv(test_path, index=False)

    class FakeVersion:
        version, run_id = "3", "run-of-the-champion"

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_model_version_by_alias(self, name, alias):
            return FakeVersion()

    loaded = []
    monkeypatch.setattr(mlflow.tracking, "MlflowClient", FakeClient)
    monkeypatch.setattr(mlflow.sklearn, "load_model", lambda uri: loaded.append(uri) or model)

    record = baseline_from_registry(dataclasses.replace(settings, processed_dir=tmp_path / "processed"))

    name, alias = settings.registered_model_name, settings.champion_alias
    assert loaded == [f"models:/{name}@{alias}"], "load the champion by its alias"
    assert record["model_version"] == "3"
    assert record["metrics"] == score_on_test_set(model, test_path)


# ── who consults the verdict (Exercise 4) ─────────────────────────────────────


class MlflowReached(AssertionError):
    pass


def _refuse_mlflow(*args, **kwargs):
    raise MlflowReached("MLflow was called before the gate verdict was checked.")


def test_register_refuses_a_no_go_before_it_reaches_mlflow(sandbox, monkeypatch):
    from week_06_evaluation_pipeline import registry

    monkeypatch.setattr(registry.mlflow, "register_model", _refuse_mlflow)
    seed(sandbox, metrics=dict(GOOD_METRICS, f1=0.20))
    with pytest.raises(GateFailed):
        pipeline.gate(sandbox)
    with pytest.raises(GateFailed, match="Refusing to release"):
        registry.register_best_model(sandbox, "any-run-id")


def test_promote_refuses_a_no_go_before_it_reaches_mlflow(sandbox, monkeypatch):
    from week_06_evaluation_pipeline import registry

    monkeypatch.setattr(registry, "MlflowClient", _refuse_mlflow)
    seed(sandbox, metrics=dict(GOOD_METRICS, f1=0.20))
    with pytest.raises(GateFailed):
        pipeline.gate(sandbox)
    with pytest.raises(GateFailed, match="Refusing to release"):
        registry.promote_to_staging(sandbox, "1")


def test_the_gate_is_a_stage_that_no_other_stage_depends_on(project_root):
    """`dvc repro` runs the gate last; `register` and `promote` read its verdict instead."""
    import yaml

    stages = yaml.safe_load((project_root / "dvc.yaml").read_text())["stages"]
    assert "gate" in stages, "dvc.yaml has no `gate` stage."
    assert "main.py gate" in stages["gate"]["cmd"]
    assert {"reports/gate.json": {"cache": False}} in stages["gate"].get("outs", [])
    for name, stage in stages.items():
        deps = [str(dep) for dep in stage.get("deps", [])]
        assert "reports/gate.json" not in deps, f"Stage `{name}` depends on the gate's verdict."
