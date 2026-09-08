# Pima diabetes — simulated measurement batches

The Pima dataset is a single static snapshot with no time axis. To teach **data versioning** (Week 4) and **drift monitoring** (Weeks 11–12) on realistic terms, we split it into two **measurement batches** as if the data arrived over time: an initial cohort, then "a new batch of measurements arrived." This is a **teaching simulation** and is labelled as such wherever it is used.

> Important: every row in these batches is a **real, unmodified record** from the canonical `diabetes.csv`. We do **not** edit any feature values. We only bias *which rows* land in the later batch (toward higher glucose), which produces a genuine distribution shift to detect. The canonical `labs/.../data/diabetes.csv` is **never modified** and remains the file the Week 1–2 labs use.

## Files

| File | Rows | Window (synthetic) | What it represents |
| :--- | :--- | :--- | :--- |
| `batch_01_baseline.csv` | 461 | 2024-01-01 → 2024-03-30 | The initial cohort; distribution close to the original. |
| `batch_02_new_arrival.csv` | 307 | 2024-03-31 → 2024-06-28 | "New measurements arrived" — deliberately shifted toward higher glucose. |
| `manifest.json` | — | — | Provenance + per-batch statistics (regenerated with the data). |
| `make_batches.py` | — | — | The reproducible generator (also works on your own dataset). |

Each batch adds one column, `measurement_date` (first column), so the data has a usable time axis. 461 + 307 = 768 rows — the full dataset, partitioned, no duplication.

## The shift (what Weeks 11–12 will detect)

| Statistic | Baseline | New arrival |
| :--- | :--- | :--- |
| Positive rate (`outcome = 1`) | 28.9% | **44.0%** |
| `glucose` mean | 111.9 | **134.4** |
| `glucose` PSI vs. baseline | — | **0.585** |

A PSI above ~0.25 indicates a major distribution shift, so the `glucose` drift here is unmistakable, and the positive rate climbs too (a label-shift flavour) — exactly the kind of signal a monitoring stack should raise. The dataset's existing quirks (the impossible zeros) are preserved untouched, so the data-quality story (Week 5) still holds in both batches.

## How the course uses these

- **Week 4 (DVC):** version `batch_01_baseline.csv` first; later commit `batch_02_new_arrival.csv` as a new data version to demonstrate dataset lineage and `dvc` diffs.
- **Weeks 11–12 (monitoring / drift):** treat `batch_01` as the training/reference window and `batch_02` as live production traffic; the glucose PSI and the rising positive rate are the drift the dashboards and Evidently report should flag.

(Weeks 1–2 do **not** use these batches — they use the full snapshot.)

## Reproduce / adapt

Deterministic (seed 42); re-running reproduces these files exactly:

```bash
cd datasets/batches
python make_batches.py \
  --input ../diabetes.csv \
  --target outcome --drift-col glucose --out .
```

To build batches for **your own project dataset**, point `--input`/`--target` at it and pick a numeric `--drift-col` to bias the later batch (omit `--drift-col` for an unbiased split). Useful knobs: `--new-fraction` (size of the final batch), `--drift-strength` (how strong the shift is), `--batches` (more than two), `--seed`. Requires `pandas` and `numpy`.

_Last updated: 2026-06. Generated from the canonical diabetes.csv; regenerate if that file changes._
