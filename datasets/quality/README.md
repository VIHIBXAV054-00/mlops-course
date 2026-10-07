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
| Rows | 60, taken from `batch_01_baseline.csv` |
| Columns | 11: the batch's usual 10, plus an unexpected `notes` column |
| md5 | `04cd5962da21814fa6c16de98c9a5ef7` |
| Generator | `make_broken_batch.py`; no randomness, so re-running reproduces the file exactly |

Sixty rows are few enough to open the file and find every fault by eye.

## The faults

Row numbers are 0-based, as Pandera reports them.

| Row | Column | Error type | What was written | Report lines |
| :--- | :--- | :--- | :--- | :--- |
| — | `notes` | schema: unexpected column | `"imported from lab system v2"` | 1 |
| 3 | `glucose` | schema: wrong type | `unknown` | 4: the conversion, the type check, and two range checks on text |
| 7 | `age` | values: out of range | `250` | 1 |
| 23 | `bmi` | values: unit change | ×10 (`280.0`) | 1: only an upper bound catches it |

The data's own zeros stay in place (for example `skin_thickness = 0` in row 2). The
Week 5 ingestion contract accepts them; the faults above are the ones it must catch.

## Regenerate / verify

```bash
cd datasets/quality
uv run --with pandas python make_broken_batch.py           # regenerate
uv run --with pandas python make_broken_batch.py --check   # verify (exit 1 on drift)
```

`manifest.json` records the fault-to-row mapping and the md5, and is rewritten
with the data.

## How the course uses this

- **Week 5 (data validation):** Exercise 2 runs the ingestion contract on this file
  and traces each of the 7 report lines to one of the 4 faults.
- **Weeks 6–13** carry the file and the same tests on it. No pipeline stage reads it.
