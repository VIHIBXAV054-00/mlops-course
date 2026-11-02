"""Build the versioned dataset from the git-committed measurement batches.

New in Week 4. This is the thing DVC tracks.

The point of building it rather than committing it: the dataset has *versions*.
Version 1 is the baseline cohort; version 2 adds the batch that arrived later.
Both are reconstructible from inputs that are in Git, which is what lets the
solution's `.dvc` pointer stay honest even though the bytes it names live only
in a cache or an object store.

Byte-determinism is a requirement, not a nicety. Two students on two machines
must produce the same md5, so this function pins:
  - batch order (01 then 02),
  - column order (whatever batch 01's header says),
  - `index=False` (no pandas row index leaking into the file),
  - `lineterminator="\\n"` — LF on every platform. DVC 3 hashes raw bytes and
    no longer normalises CRLF, so a Windows checkout would otherwise produce a
    different md5 for the same logical data.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

# Ordered. Version N uses the first N of these.
BATCH_FILES = ("batch_01_baseline.csv", "batch_02_new_arrival.csv")

MAX_VERSION = len(BATCH_FILES)


def batch_paths(raw_dir: Path, version: int) -> list[Path]:
    """The batch files that make up a given dataset version."""
    if not 1 <= version <= MAX_VERSION:
        raise ValueError(
            f"version must be between 1 and {MAX_VERSION}; got {version!r}."
        )
    return [Path(raw_dir) / name for name in BATCH_FILES[:version]]


def build_measurements(version: int, raw_dir: Path, out_path: Path) -> int:
    """Write dataset version `version` to `out_path`. Returns the row count.

    Version 1 = 461 rows (baseline batch).
    Version 2 = 768 rows (both batches) — the same 768 rows as the canonical
    diabetes.csv, but in batch-arrival order rather than the original file
    order. That difference is real and it changes the train/test split, so the
    metrics will NOT match the Week 1-3 pins. See Exercise 4.
    """
    paths = batch_paths(raw_dir, version)
    missing = [p for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"Missing raw batch file(s): {[str(p) for p in missing]}. "
            "Run scripts/sync_datasets.sh from the repository root."
        )

    frames = [pd.read_csv(p) for p in paths]
    combined = pd.concat(frames, ignore_index=True)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(out, index=False, lineterminator="\n")
    return len(combined)


def file_md5(path: Path) -> str:
    """The plain md5 of a file's bytes.

    This is exactly what DVC records in a `.dvc` pointer — verified against
    dvc 3.67.1. Having it here lets the pipeline and the tests compare their own
    view of the data against DVC's without shelling out to `dvc`.
    """
    return hashlib.md5(Path(path).read_bytes()).hexdigest()
