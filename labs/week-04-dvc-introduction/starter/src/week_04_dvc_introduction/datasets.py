"""Build the dataset that DVC tracks, from the batches that have arrived in data/raw/.

Batches wait in data/incoming/. `next_batch` copies the next one to data/raw/.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pandas as pd

BATCH_PATTERN = "batch_*.csv"


def batch_paths(raw_dir: Path) -> list[Path]:
    """The batch files in `raw_dir`, in name order: batch_01, batch_02, ..."""
    paths = sorted(Path(raw_dir).glob(BATCH_PATTERN))
    if not paths:
        raise FileNotFoundError(
            f"No batch file in {raw_dir}. Run `make next-batch` to receive the first one."
        )
    return paths


def next_batch(incoming_dir: Path, raw_dir: Path) -> Path | None:
    """Copy the first batch that has not arrived yet from `incoming_dir` to `raw_dir`.

    Returns the new file, or None when every batch has arrived.
    """
    arrived = {path.name for path in Path(raw_dir).glob(BATCH_PATTERN)}
    for source in sorted(Path(incoming_dir).glob(BATCH_PATTERN)):
        if source.name not in arrived:
            Path(raw_dir).mkdir(parents=True, exist_ok=True)
            return Path(shutil.copyfile(source, Path(raw_dir) / source.name))
    return None


def build_measurements(raw_dir: Path, out_path: Path) -> int:
    """Merge every batch in `raw_dir` into one CSV file at `out_path`.

    TODO(student) — Exercise 2: load the batch files (`batch_paths` lists them in
    order) and merge them into one frame. Write the frame to `out_path` with
    `DataFrame.to_csv`, and look at its options. Return the frame's row count.
    """
    paths = batch_paths(raw_dir)
    _ = (pd, paths)  # keep the names meaningful until you implement the body
    return 0  # placeholder — the CLI reports this as "not implemented yet"


def file_md5(path: Path) -> str:
    """The md5 of a file's bytes, the same value DVC writes into a `.dvc` pointer."""
    return hashlib.md5(Path(path).read_bytes()).hexdigest()
