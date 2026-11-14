"""Build the versioned dataset from the committed measurement batches. You do not need to read it.

The output must be byte-identical on every machine, because DVC hashes the bytes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

# Version N uses the first N of these files.
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

    Version 1 has 461 rows, version 2 has 768 rows (both batches).
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
    """The md5 of a file's content, the same hash a `.dvc` pointer records."""
    return hashlib.md5(Path(path).read_bytes()).hexdigest()
