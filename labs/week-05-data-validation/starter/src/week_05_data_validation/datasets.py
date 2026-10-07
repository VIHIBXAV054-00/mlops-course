"""Build the dataset that DVC tracks, from the batches in data/raw/.

You do not need to change this module.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

BATCH_PATTERN = "batch_*.csv"


def batch_paths(raw_dir: Path) -> list[Path]:
    """The batch files in `raw_dir`, in name order: batch_01, batch_02, ..."""
    paths = sorted(Path(raw_dir).glob(BATCH_PATTERN))
    if not paths:
        raise FileNotFoundError(
            f"No batch file in {raw_dir}. Run scripts/sync_datasets.sh from the "
            "repository root."
        )
    return paths


def build_measurements(raw_dir: Path, out_path: Path) -> int:
    """Merge every batch in `raw_dir` into one CSV file at `out_path`. Returns the row count."""
    frames = [pd.read_csv(path) for path in batch_paths(raw_dir)]
    merged = pd.concat(frames, ignore_index=True)

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(out, index=False, lineterminator="\n")
    return len(merged)


def file_md5(path: Path) -> str:
    """The md5 of a file, the same value DVC writes into a `.dvc` pointer."""
    return hashlib.md5(Path(path).read_bytes()).hexdigest()
