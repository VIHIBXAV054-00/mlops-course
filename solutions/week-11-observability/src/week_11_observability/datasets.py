"""Build the DVC-tracked dataset from the committed measurement batches.

Version 1 is the baseline batch, version 2 adds the later batch. The output is byte-identical
on every machine (fixed batch order, no index, LF line endings), so the md5 matches.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

# version N uses the first N of these
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
    """Write dataset version `version` to `out_path` and return the row count.

    Version 1 has 461 rows, version 2 has all 768 rows in batch-arrival order.
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
    """The md5 of a file's bytes, the same value DVC writes in a `.dvc` pointer."""
    return hashlib.md5(Path(path).read_bytes()).hexdigest()
