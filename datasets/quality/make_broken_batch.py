#!/usr/bin/env python3
"""Generate a DELIBERATELY CORRUPTED measurement batch for the Week 5 lab.

Unlike `datasets/batches/`, which guarantees every row is a real unmodified
record, this file EDITS VALUES on purpose. It exists so students have a file
that a data contract must reject, with one fault per error class so that every
row of Pandera's `failure_cases` report maps back to exactly one injected fault.

The output is a teaching exhibit. It must never be used for training.

Determinism: no randomness at all. Faults are written to fixed row positions of
a fixed slice of `batch_01_baseline.csv`, so re-running reproduces the file
byte-for-byte on any machine (LF line endings are forced for the same reason
Week 4 forces them — DVC 3 and md5 both hash raw bytes).

    python make_broken_batch.py            # regenerate broken_batch.csv + manifest.json
    python make_broken_batch.py --check    # verify the committed file matches (exit 1 on drift)
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

# How many clean rows to start from. Small on purpose: a student has to be able
# to open the file and find every fault by eye.
N_BASE_ROWS = 60

# Row positions (0-based, in the emitted file) that carry an injected fault.
# Chosen to be spread out and to never collide with each other.
FAULTS = [
    {
        "row": 3,
        "column": "glucose",
        "error_class": "schema — wrong dtype",
        "value": "unknown",
        "why": "A non-numeric string in a numeric column. Whoever exported this "
        "file used a sentinel word instead of an empty cell, which turns the "
        "whole column into text.",
    },
    {
        "row": 7,
        "column": "age",
        "error_class": "semantic — out of range",
        "value": 250,
        "why": "Nobody is 250 years old. A plausible-looking integer in a "
        "column with no upper bound declared.",
    },
    {
        "row": 11,
        "column": "insulin",
        "error_class": "semantic — impossible sign",
        "value": -1,
        "why": "A negative concentration. Often a sentinel for 'not measured' "
        "picked by whoever wrote the export, with nobody downstream told.",
    },
    {
        "row": 15,
        "column": "outcome",
        "error_class": "semantic — invalid label",
        "value": 2,
        "why": "A third class in a binary target. Silently trains a model on a "
        "label that does not exist.",
    },
    {
        "row": 19,
        "column": "blood_pressure",
        "error_class": "completeness — missing value",
        "value": None,
        "why": "An empty cell where the contract says a value is required.",
    },
    {
        "row": 23,
        "column": "bmi",
        "error_class": "semantic — unit change",
        "value": "x10",
        "why": "BMI multiplied by ten, as if the exporter switched units or "
        "dropped a decimal separator. THE SUBTLE ONE: still numeric, still "
        "positive, invisible to a row count.",
    },
    {
        "row": 27,
        "column": "bmi",
        "error_class": "semantic — unit change",
        "value": "x10",
        "why": "Second occurrence of the same unit change, so the report shows "
        "a pattern rather than a one-off typo.",
    },
    {
        "row": 31,
        "column": "bmi",
        "error_class": "semantic — unit change",
        "value": "x10",
        "why": "Third occurrence.",
    },
    {
        "row": 39,
        "column": "measurement_date",
        "error_class": "schema — unparseable date",
        "value": "2024-13-45",
        "why": "A date that cannot exist. Month 13, day 45 — the kind of thing "
        "a hand-edited spreadsheet produces.",
    },
]

# Faults that are properties of the FILE rather than of one cell.
EXTRA_COLUMN = {
    "column": "notes",
    "error_class": "schema — unexpected column",
    "why": "A column nobody agreed to. Harmless here, but it means the "
    "producer changed the file without telling the consumer — and the next "
    "change might not be harmless.",
}
DUPLICATE_SOURCE_ROW = 5
DUPLICATE = {
    "row": N_BASE_ROWS,  # appended at the end
    "error_class": "uniqueness — duplicated row",
    "why": f"An exact copy of row {DUPLICATE_SOURCE_ROW}. Double-counts one "
    "patient in training and in the metrics.",
}


def build() -> pd.DataFrame:
    """Assemble the corrupted frame. Pure function of the committed source file."""
    if not SOURCE.exists():
        raise FileNotFoundError(
            f"Source batch missing: {SOURCE}. It is committed to the repository — "
            "check you are running this from datasets/quality/."
        )

    frame = pd.read_csv(SOURCE, dtype=str).head(N_BASE_ROWS).copy()

    # Everything is read as str so that injecting "unknown" into a numeric
    # column does not depend on pandas' dtype promotion rules, and so the
    # emitted file is byte-identical to the source for every untouched cell.
    for fault in FAULTS:
        row, column, value = fault["row"], fault["column"], fault["value"]
        if value == "x10":
            frame.at[row, column] = f"{float(frame.at[row, column]) * 10:.1f}"
        elif value is None:
            frame.at[row, column] = ""
        else:
            frame.at[row, column] = str(value)

    frame[EXTRA_COLUMN["column"]] = "imported from lab system v2"

    duplicated = frame.iloc[[DUPLICATE_SOURCE_ROW]].copy()
    frame = pd.concat([frame, duplicated], ignore_index=True)

    return frame


def write(frame: pd.DataFrame) -> str:
    frame.to_csv(OUT_CSV, index=False, lineterminator="\n")
    digest = hashlib.md5(OUT_CSV.read_bytes()).hexdigest()

    by_class: dict[str, int] = {}
    for fault in FAULTS:
        by_class[fault["error_class"]] = by_class.get(fault["error_class"], 0) + 1
    by_class[EXTRA_COLUMN["error_class"]] = 1
    by_class[DUPLICATE["error_class"]] = 1

    manifest = {
        "source": str(SOURCE.relative_to(HERE.parent.parent)),
        "note": (
            "DELIBERATELY CORRUPTED teaching material for the Week 5 data-validation "
            "lab. Values have been edited. Never train on this file."
        ),
        "base_rows": N_BASE_ROWS,
        "total_rows": int(len(frame)),
        "md5": digest,
        "bytes": OUT_CSV.stat().st_size,
        "error_classes": by_class,
        "cell_faults": FAULTS,
        "file_faults": [EXTRA_COLUMN, DUPLICATE],
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
