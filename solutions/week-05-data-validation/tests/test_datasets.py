"""The batches and the dataset builder.

Each test builds its own copy of the data in `tmp_path`.
"""

import pandas as pd
import pytest
import yaml

from week_05_data_validation.datasets import batch_paths, build_measurements, file_md5


def test_raw_batches_present_and_shaped(raw_batches) -> None:
    """Two batches in data/raw/, with the date column first."""
    frames = [pd.read_csv(path) for path in batch_paths(raw_batches)]
    assert [len(frame) for frame in frames] == [461, 307]
    assert frames[0].columns[0] == "measurement_date"
    assert list(frames[0].columns) == list(frames[1].columns)


def test_batch_paths_needs_at_least_one_batch(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="sync_datasets"):
        batch_paths(tmp_path)


def test_build_merges_every_batch(raw_batches, tmp_path) -> None:
    out = tmp_path / "measurements.csv"
    assert build_measurements(raw_batches, out) == 768


def test_build_is_byte_deterministic(raw_batches, tmp_path) -> None:
    first = tmp_path / "a.csv"
    second = tmp_path / "b.csv"
    build_measurements(raw_batches, first)
    build_measurements(raw_batches, second)
    assert file_md5(first) == file_md5(second)
    assert b"\r\n" not in first.read_bytes()


def test_committed_pointer_names_a_fresh_build(
    raw_batches, measurements_pointer, tmp_path
) -> None:
    """The .dvc pointer that ships with the lab describes a build from data/raw/."""
    rebuilt = tmp_path / "measurements.csv"
    build_measurements(raw_batches, rebuilt)
    out = yaml.safe_load(measurements_pointer.read_text())["outs"][0]
    assert file_md5(rebuilt) == out["md5"] == "a8fd7b4f0d6d1bc4e378a8f76c5fff0c"
    assert out["size"] == rebuilt.stat().st_size
