"""Arriving batches and the dataset builder (Exercises 2 and 4).

Each test builds its own copy of the data in `tmp_path`.
"""

import pandas as pd
import pytest
import yaml

from week_04_dvc_introduction.datasets import (
    batch_paths,
    build_measurements,
    file_md5,
    next_batch,
)


def test_incoming_batches_present_and_shaped(incoming) -> None:
    """Three batches wait in data/incoming/, with the date column first."""
    frames = [pd.read_csv(path) for path in sorted(incoming.glob("batch_*.csv"))]
    assert [len(frame) for frame in frames] == [461, 107, 200]
    assert frames[0].columns[0] == "measurement_date"
    assert all(list(frame.columns) == list(frames[0].columns) for frame in frames)


def test_next_batch_copies_the_batches_in_order(incoming, tmp_path) -> None:
    raw = tmp_path / "raw"
    arrived = [next_batch(incoming, raw).name for _ in range(3)]
    assert arrived == ["batch_01.csv", "batch_02.csv", "batch_03.csv"]
    assert next_batch(incoming, raw) is None


def test_batch_paths_needs_at_least_one_batch(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="next-batch"):
        batch_paths(tmp_path)


def test_build_from_the_first_batch(make_raw, tmp_path) -> None:
    out = tmp_path / "measurements.csv"
    rows = build_measurements(make_raw(1), out)
    assert rows == 461, f"The first batch has 461 rows; got {rows}."
    assert out.exists(), "build_measurements did not write the output file."


def test_build_is_byte_deterministic(make_raw, tmp_path) -> None:
    """Two builds from the same batches produce identical bytes."""
    raw = make_raw(3)
    first = tmp_path / "a.csv"
    second = tmp_path / "b.csv"
    build_measurements(raw, first)
    build_measurements(raw, second)
    assert first.exists(), "build_measurements did not write the output file."
    assert file_md5(first) == file_md5(second), "Two builds wrote different bytes."


def test_build_uses_lf_line_endings(make_raw, tmp_path) -> None:
    """The file uses LF line endings on every platform."""
    out = tmp_path / "measurements.csv"
    build_measurements(make_raw(3), out)
    assert out.exists(), "build_measurements did not write the output file."
    assert b"\r\n" not in out.read_bytes(), (
        "The file has Windows (CRLF) line endings, so its md5 depends on the laptop."
    )


def test_build_from_all_batches(make_raw, incoming, tmp_path) -> None:
    """All three batches give 768 rows, with the batch files' columns."""
    out = tmp_path / "measurements.csv"
    rows = build_measurements(make_raw(3), out)
    assert rows == 768, f"The three batches have 768 rows together; got {rows}."
    first = pd.read_csv(incoming / "batch_01.csv")
    assert list(pd.read_csv(out).columns) == list(first.columns), (
        "The written file has different columns from the batch files. "
        "Is a pandas index column in the file?"
    )


def test_committed_pointer_names_all_three_batches(
    make_raw, measurements_pointer, tmp_path
) -> None:
    """The committed .dvc pointer describes a fresh build from all three batches."""
    rebuilt = tmp_path / "measurements.csv"
    build_measurements(make_raw(3), rebuilt)

    out = yaml.safe_load(measurements_pointer.read_text())["outs"][0]
    assert file_md5(rebuilt) == out["md5"], (
        "The committed pointer does not match a fresh build from all three batches. "
        "Did you add and commit version 3?"
    )
    assert out["size"] == rebuilt.stat().st_size, "The pointer's size does not match."
