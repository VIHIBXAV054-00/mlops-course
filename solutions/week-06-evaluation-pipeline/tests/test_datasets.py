"""The versioned dataset builder. It builds into `tmp_path` from the committed raw batches."""

import hashlib

import pytest
import yaml

from week_06_evaluation_pipeline.datasets import build_measurements, file_md5


def test_raw_batches_present_and_shaped(raw_batches) -> None:
    """The committed inputs are the two batches, with the date column first."""
    import pandas as pd

    first = pd.read_csv(raw_batches / "batch_01_baseline.csv")
    second = pd.read_csv(raw_batches / "batch_02_new_arrival.csv")
    assert len(first) == 461
    assert len(second) == 307
    assert first.columns[0] == "measurement_date"
    assert list(first.columns) == list(second.columns)


def test_build_v1_row_count(settings, raw_batches, tmp_path) -> None:
    out = tmp_path / "measurements.csv"
    assert build_measurements(1, raw_batches, out) == 461


def test_build_v2_row_count_and_column_order(settings, raw_batches, tmp_path) -> None:
    """v2 is both batches: the same 768 rows as diabetes.csv, in arrival order."""
    import pandas as pd

    out = tmp_path / "measurements.csv"
    assert build_measurements(2, raw_batches, out) == 768
    built = pd.read_csv(out)
    first = pd.read_csv(raw_batches / "batch_01_baseline.csv")
    assert list(built.columns) == list(first.columns)


def test_build_is_byte_deterministic(raw_batches, tmp_path) -> None:
    """Two builds of the same version produce identical bytes, so every machine gets the same md5."""
    first = tmp_path / "a.csv"
    second = tmp_path / "b.csv"
    build_measurements(2, raw_batches, first)
    build_measurements(2, raw_batches, second)
    assert file_md5(first) == file_md5(second)


def test_build_uses_lf_line_endings(raw_batches, tmp_path) -> None:
    """The file uses LF line endings: DVC hashes raw bytes, so CRLF would change the md5."""
    out = tmp_path / "measurements.csv"
    build_measurements(2, raw_batches, out)
    assert b"\r\n" not in out.read_bytes()


def test_build_rejects_unknown_version(raw_batches, tmp_path) -> None:
    with pytest.raises(ValueError):
        build_measurements(3, raw_batches, tmp_path / "x.csv")


def test_v2_md5_matches_committed_pointer(
    raw_batches, measurements_pointer, tmp_path
) -> None:
    """The committed `.dvc` pointer has the md5 of dataset version 2, built from the raw batches."""
    rebuilt = tmp_path / "measurements.csv"
    build_measurements(2, raw_batches, rebuilt)
    rebuilt_md5 = hashlib.md5(rebuilt.read_bytes()).hexdigest()

    out = yaml.safe_load(measurements_pointer.read_text())["outs"][0]
    assert rebuilt_md5 == out["md5"], (
        "The committed pointer does not match a fresh build of version 2. "
        "Either the raw batches, the generator, or the line endings changed."
    )
    assert out["size"] == rebuilt.stat().st_size
