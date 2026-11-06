"""The validate stage in dvc.yaml (Exercise 4).

The tests read dvc.yaml as YAML. They do not run `dvc`.
"""

import pytest
import yaml

SRC = "src/week_05_data_validation"


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


def test_validate_stage_runs_the_validate_command(stages) -> None:
    assert "validate" in stages, "dvc.yaml has no `validate` stage."
    assert stages["validate"].get("cmd") == "uv run python src/main.py validate"


def test_validate_declares_what_it_reads_and_writes(stages) -> None:
    deps = _paths(stages["validate"].get("deps"))
    for path in (
        "data/measurements.csv",
        f"{SRC}/pipeline.py",
        f"{SRC}/schemas.py",
        f"{SRC}/validation.py",
    ):
        assert path in deps, f"validate reads {path}, but it is not in its deps."

    outs = _paths(stages["validate"].get("outs"))
    assert outs.get("reports/validation.json", {}).get("cache") is False, (
        "validate writes reports/validation.json: list it in outs with `cache: false`."
    )


def test_prepare_waits_for_the_report(stages) -> None:
    deps = _paths(stages["prepare"].get("deps"))
    assert "reports/validation.json" in deps, (
        "prepare does not depend on reports/validation.json, so DVC can run it "
        "before validate, or after validate has failed."
    )
