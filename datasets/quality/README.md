# Corrupted measurement batch — Week 5 teaching exhibit

> **This file is deliberately broken. Never train on it.** Unlike
> [`datasets/batches/`](../batches/README.md), where every row is a real
> unmodified record, `broken_batch.csv` has had **values edited on purpose**. It
> exists so that a data contract has something to reject.

## Why a separate directory

`datasets/batches/README.md` promises that no feature value is ever edited, and
`scripts/sync_datasets.sh` copies `datasets/batches/batch_0*.csv` into **every**
lab that has a `data/raw/` directory. A corrupted `batch_03_*.csv` would break
the first promise and silently appear in the Week 4 lab. So the corrupted file
lives here instead, and the sync script copies it only into labs that opt in by
having a `data/quality/` directory — today, Week 5 alone.

## The file

| Property | Value |
| :--- | :--- |
| Rows | 61 (60 taken from `batch_01_baseline.csv`, plus 1 duplicate) |
| Columns | 11 — the batch's usual 10, plus an unexpected `notes` column |
| md5 | `873300d072058ff129c9f4aa72eee58b` |
| Bytes | 4,113 |
| Generator | `make_broken_batch.py` — no randomness; re-running reproduces the file byte-for-byte |

Sixty rows is deliberate: a student must be able to open the file and find every
fault by eye, then check their reading against Pandera's report.

## The injected faults

One fault per error class, each at a fixed row (0-based, as pandas reports it),
so every row of a `failure_cases` report maps back to exactly one edit.

| Row | Column | Error class | What was written | Why this one |
| :--- | :--- | :--- | :--- | :--- |
| — | `notes` | schema — unexpected column | `"imported from lab system v2"` | A column nobody agreed to. Harmless in itself; it means the producer changed the file without telling the consumer. |
| 3 | `glucose` | schema — wrong dtype | `unknown` | A sentinel *word* instead of an empty cell. Turns the whole column into text. |
| 39 | `measurement_date` | schema — unparseable date | `2024-13-45` | Month 13, day 45. What hand-edited spreadsheets produce. |
| 7 | `age` | semantic — out of range | `250` | A plausible-looking integer in a column with no upper bound. |
| 11 | `insulin` | semantic — impossible sign | `-1` | A negative concentration, used as a private "not measured" sentinel. |
| 15 | `outcome` | semantic — invalid label | `2` | A third class in a binary target. |
| 23, 27, 31 | `bmi` | semantic — unit change | ×10 (`280.0`, `297.0`, `227.0`) | **The subtle one.** Still numeric, still positive, invisible to a row count. Only an upper bound catches it. |
| 19 | `blood_pressure` | completeness — missing value | empty cell | A required value that is absent. |
| 60 | — | uniqueness — duplicated row | exact copy of row 5 | Double-counts one patient in training *and* in the metrics. |

The dataset's original quirks are **left in place**: rows 2 and 6, for instance,
still carry the real `skin_thickness = 0` and `blood_pressure = 0` sentinels from
the Pima data. That matters — the Week 5 ingestion contract is written to
*tolerate* those, because a gate that rejects every real file is a gate that gets
switched off. The faults above are the ones a contract must catch.

## Regenerate / verify

```bash
cd datasets/quality
uv run --with pandas python make_broken_batch.py           # regenerate
uv run --with pandas python make_broken_batch.py --check   # verify (exit 1 on drift)
```

`manifest.json` records the fault-to-row mapping and the md5, and is rewritten
with the data.

## How the course uses this

- **Week 5 (data validation):** Exercise 2 runs the ingestion contract against
  this file with `lazy=True` and reads the resulting `failure_cases` report,
  mapping every row of it back to the table above.

No other week uses it, and no pipeline stage ever reads it.
