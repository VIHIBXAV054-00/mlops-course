"""Your pipeline declaration in dvc.yaml (Exercise 5).

The tests read dvc.yaml as YAML. They do not run `dvc`.
"""

import pytest
import yaml

SRC = "src/week_04_dvc_introduction"


@pytest.fixture(scope="module")
def stages(project_root) -> dict:
    return yaml.safe_load((project_root / "dvc.yaml").read_text())["stages"]


def _paths(entries) -> dict:
    """{path: options} for a deps, outs or metrics list."""
    result = {}
    for entry in entries or []:
        if isinstance(entry, str):
            result[entry] = {}
        else:
            result.update({path: options or {} for path, options in entry.items()})
    return result


def _params(entries) -> set:
    """The param names in a params list, e.g. {"random_seed", "train.C"}."""
    names = set()
    for entry in entries or []:
        if isinstance(entry, str):
            names.add(entry)
        else:
            for values in entry.values():
                names.update(values or [])
    return names


@pytest.mark.skip(reason="Exercise 5 — add train and evaluate to dvc.yaml, then delete this skip marker.")
def test_train_and_evaluate_stages_exist(stages) -> None:
    for name in ("train", "evaluate"):
        assert name in stages, f"dvc.yaml has no `{name}` stage."
        assert stages[name].get("cmd") == f"uv run python src/main.py {name}", (
            f"The `{name}` stage should run `uv run python src/main.py {name}`."
        )


@pytest.mark.skip(reason="Exercise 5 — add train and evaluate to dvc.yaml, then delete this skip marker.")
def test_train_declares_what_it_reads_and_writes(stages) -> None:
    train = stages["train"]
    deps = _paths(train.get("deps"))
    for path in ("data/processed/train.csv", f"{SRC}/pipeline.py", f"{SRC}/model.py"):
        assert path in deps, f"train reads {path}, but it is not in its deps."

    params = _params(train.get("params"))
    for name in ("random_seed", "train.family", "train.C", "train.max_iter"):
        assert name in params or name.split(".")[0] in params, (
            f"train uses {name}, but it is not in its params."
        )

    outs = _paths(train.get("outs"))
    assert "models/model.pkl" in outs, "train writes models/model.pkl, but it is not in its outs."
    assert outs.get("models/mlflow_run_id.json", {}).get("cache") is False, (
        "train writes models/mlflow_run_id.json: list it in outs with `cache: false`."
    )


@pytest.mark.skip(reason="Exercise 5 — add train and evaluate to dvc.yaml, then delete this skip marker.")
def test_evaluate_declares_every_file_it_reads(stages) -> None:
    evaluate = stages["evaluate"]
    deps = _paths(evaluate.get("deps"))
    for path in (
        "models/model.pkl",
        "models/mlflow_run_id.json",
        "data/processed/test.csv",
        f"{SRC}/pipeline.py",
        f"{SRC}/model.py",
    ):
        assert path in deps, (
            f"evaluate reads {path}, but it is not in its deps, so DVC does not "
            "re-run evaluate when that file changes."
        )

    metrics = _paths(evaluate.get("metrics"))
    assert metrics.get("metrics/metrics.json", {}).get("cache") is False, (
        "evaluate writes metrics/metrics.json: list it under `metrics:` with `cache: false`."
    )
