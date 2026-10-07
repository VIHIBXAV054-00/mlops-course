#!/usr/bin/env python3
"""Generate the broken measurement batch for the Week 5 lab.

It edits values on purpose, so a data contract has something to reject. Never
train on it. No randomness: re-running reproduces the file exactly.

    python make_broken_batch.py            # regenerate broken_batch.csv and manifest.json
    python make_broken_batch.py --check    # verify the committed file (exit 1 on drift)
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / "batches" / "batch_01_baseline.csv"
OUT_CSV = HERE / "broken_batch.csv"
OUT_MANIFEST = HERE / "manifest.json"

# Small enough to open the file and find every fault by eye.
N_BASE_ROWS = 60

# Row positions are 0-based, as Pandera reports them.
FAULTS = [
    {
        "row": 3,
        "column": "glucose",
        "error_class": "schema — wrong type",
        "value": "unknown",
        "why": "A word instead of an empty cell turns the whole column into text.",
    },
    {
        "row": 7,
        "column": "age",
        "error_class": "values — out of range",
        "value": 250,
        "why": "Nobody is 250 years old.",
    },
    {
        "row": 23,
        "column": "bmi",
        "error_class": "values — unit change",
        "value": "x10",
        "why": "BMI multiplied by ten: still numeric and positive; only an upper bound catches it.",
    },
]

# A fault of the whole file, not of one cell.
EXTRA_COLUMN = {
    "column": "notes",
    "error_class": "schema — unexpected column",
    "why": "A column nobody agreed to: the producer changed the file without telling the consumer.",
}


def build() -> pd.DataFrame:
    """Assemble the broken frame from the committed source batch."""
    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Source batch missing: {SOURCE}. Run this from datasets/quality/."
        )

    frame = pd.read_csv(SOURCE, dtype=str).head(N_BASE_ROWS).copy()

    # Read as text, so every untouched cell is written back unchanged.
    for fault in FAULTS:
        row, column, value = fault["row"], fault["column"], fault["value"]
        if value == "x10":
            frame.at[row, column] = f"{float(frame.at[row, column]) * 10:.1f}"
        elif value is None:
            frame.at[row, column] = ""
        else:
            frame.at[row, column] = str(value)

    frame[EXTRA_COLUMN["column"]] = "imported from lab system v2"

    return frame


def write(frame: pd.DataFrame) -> str:
    frame.to_csv(OUT_CSV, index=False, lineterminator="\n")
    digest = hashlib.md5(OUT_CSV.read_bytes()).hexdigest()

    by_class: dict[str, int] = {}
    for fault in FAULTS:
        by_class[fault["error_class"]] = by_class.get(fault["error_class"], 0) + 1
    by_class[EXTRA_COLUMN["error_class"]] = 1

    manifest = {
        "source": str(SOURCE.relative_to(HERE.parent.parent)),
        "note": "Broken on purpose for the Week 5 lab. Never train on this file.",
        "base_rows": N_BASE_ROWS,
        "total_rows": int(len(frame)),
        "md5": digest,
        "bytes": OUT_CSV.stat().st_size,
        "error_classes": by_class,
        "cell_faults": FAULTS,
        "file_faults": [EXTRA_COLUMN],
    }
    OUT_MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    return digest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the committed file matches what this script produces",
    )
    args = parser.parse_args()

    frame = build()

    if args.check:
        if not OUT_CSV.exists():
            raise SystemExit(f"MISSING: {OUT_CSV}")
        expected = frame.to_csv(index=False, lineterminator="\n").encode()
        if OUT_CSV.read_bytes() != expected:
            raise SystemExit(f"DRIFT: {OUT_CSV} differs from what the generator produces")
        print(f"OK: {OUT_CSV.name} matches the generator ({len(frame)} rows).")
        return

    digest = write(frame)
    print(f"Wrote {OUT_CSV.name}: {len(frame)} rows, md5 {digest}")
    print(f"Wrote {OUT_MANIFEST.name}")


if __name__ == "__main__":
    main()
