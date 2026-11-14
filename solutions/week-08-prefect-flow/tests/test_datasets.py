"""The versioned dataset builder (Exercises 2 and 4).

Everything here builds its own data into `tmp_path` from the git-committed raw
batches, so nothing depends on whether the workspace happens to have a
DVC-materialised `data/measurements.csv`. That is what makes this file green in
the autograder.
"""

import hashlib

import pytest
import yaml

from week_08_prefect_flow.datasets import build_measurements, file_md5

pytestmark = pytest.mark.data


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
    """Two builds of the same version produce identical bytes.

    Without this, two students would get two different md5s for the same
    logical dataset and every `.dvc` pointer would disagree.
    """
    first = tmp_path / "a.csv"
    second = tmp_path / "b.csv"
    build_measurements(2, raw_batches, first)
    build_measurements(2, raw_batches, second)
    assert file_md5(first) == file_md5(second)


def test_build_uses_lf_line_endings(raw_batches, tmp_path) -> None:
    """The CRLF hazard, as an assertion.

    DVC 3 hashes raw bytes and no longer normalises line endings, so a CRLF
    checkout would produce a different md5 for identical data.
    """
    out = tmp_path / "measurements.csv"
    build_measurements(2, raw_batches, out)
    assert b"\r\n" not in out.read_bytes()


def test_build_rejects_unknown_version(raw_batches, tmp_path) -> None:
    with pytest.raises(ValueError):
        build_measurements(3, raw_batches, tmp_path / "x.csv")


def test_v2_md5_matches_committed_pointer(
    raw_batches, measurements_pointer, tmp_path
) -> None:
    """The committed .dvc pointer really does describe version 2.

    This is the lineage-honesty test. The bytes the pointer names live in a DVC
    cache or an object store, neither of which travels in Git — so without this,
    the solution's claim that its pointer corresponds to the committed raw
    batches would be unverifiable and would rot silently.

    It needs no Silo, no remote, no `dvc` subprocess, and not even a workspace
    copy of measurements.csv.
    """
    rebuilt = tmp_path / "measurements.csv"
    build_measurements(2, raw_batches, rebuilt)
    rebuilt_md5 = hashlib.md5(rebuilt.read_bytes()).hexdigest()

    out = yaml.safe_load(measurements_pointer.read_text())["outs"][0]
    assert rebuilt_md5 == out["md5"], (
        "The committed pointer does not match a fresh build of version 2. "
        "Either the raw batches, the generator, or the line endings changed."
    )
    assert out["size"] == rebuilt.stat().st_size
