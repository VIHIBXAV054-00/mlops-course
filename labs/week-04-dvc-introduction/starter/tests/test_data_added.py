"""The check that stops a run from naming the wrong data (Exercise 7, optional).

Each test writes a copy of the full dataset and its pointer to `tmp_path`.
"""

import dataclasses

import pandas as pd
import pytest
import yaml

from week_04_dvc_introduction.datasets import file_md5
from week_04_dvc_introduction.dvc_link import require_data_added


@pytest.fixture
def added(settings, all_batches, tmp_path):
    """Settings whose measurements file matches its pointer, as after `dvc add`."""
    data = tmp_path / "measurements.csv"
    frames = [pd.read_csv(path) for path in sorted(all_batches.glob("batch_*.csv"))]
    pd.concat(frames, ignore_index=True).to_csv(data, index=False, lineterminator="\n")
    out = {"md5": file_md5(data), "size": data.stat().st_size, "hash": "md5",
           "path": "measurements.csv"}
    (tmp_path / "measurements.csv.dvc").write_text(yaml.safe_dump({"outs": [out]}))
    return dataclasses.replace(settings, measurements_path=data)


def test_added_data_is_accepted(added) -> None:
    assert require_data_added(added) == file_md5(added.measurements_path), (
        "When the file matches its pointer, require_data_added should return its md5."
    )


def test_edited_data_is_refused(added) -> None:
    path = added.measurements_path
    text = path.read_text()
    edited = text.replace(",33.6,", ",33.7,", 1)
    assert edited != text
    path.write_text(edited)

    try:
        require_data_added(added)
    except RuntimeError as error:
        assert "dvc add" in str(error), "The error message should tell the user to run `dvc add`."
    else:
        pytest.fail("The file differs from its pointer, but no RuntimeError was raised.")
