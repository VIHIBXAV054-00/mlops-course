#!/usr/bin/env python3
"""Split a static CSV into ordered "measurement batches" to simulate evolving data.

Why: several course datasets (Pima, Telco, Adult) have no real time axis. To teach
data *versioning* (Week 4) and *drift monitoring* (Weeks 11-12) on realistic terms,
we pretend the data arrived in batches over time: an initial cohort, then "a new
batch of measurements arrived." Optionally, the later batch is drawn with a bias on
one feature so its distribution genuinely shifts — giving the monitoring weeks a real
signal to detect. Every output row is a *real* record from the source file; we only
change *which* rows land in which batch (biased sampling), never the values.

This is a TEACHING SIMULATION and is labelled as such. It never modifies the input.

Example (Pima, the course default):
    python make_batches.py \
        --input ../diabetes.csv \
        --target outcome --drift-col glucose --out .

Apply to your own project dataset by changing --input/--target/--drift-col.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd


def psi(expected: pd.Series, actual: pd.Series, bins: int = 10) -> float:
    """Population Stability Index of `actual` vs `expected` using expected-quantile bins."""
    e = pd.to_numeric(expected, errors="coerce").dropna()
    a = pd.to_numeric(actual, errors="coerce").dropna()
    if e.empty or a.empty:
        return float("nan")
    edges = np.unique(np.quantile(e, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return float("nan")
    edges[0], edges[-1] = -np.inf, np.inf
    e_pct = np.histogram(e, bins=edges)[0] / len(e)
    a_pct = np.histogram(a, bins=edges)[0] / len(a)
    eps = 1e-6
    e_pct, a_pct = np.clip(e_pct, eps, None), np.clip(a_pct, eps, None)
    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))


def batch_stats(df: pd.DataFrame, target: str | None, drift_col: str | None,
                baseline: pd.DataFrame | None) -> dict:
    s: dict = {"rows": int(len(df))}
    if target and target in df.columns and df[target].nunique() <= 10:
        vc = df[target].value_counts(normalize=True).round(4).to_dict()
        s["target_distribution"] = {str(k): v for k, v in vc.items()}
    if drift_col and drift_col in df.columns:
        col = pd.to_numeric(df[drift_col], errors="coerce")
        s[f"{drift_col}_mean"] = round(float(col.mean()), 2)
        s[f"{drift_col}_std"] = round(float(col.std()), 2)
        if baseline is not None:
            s[f"{drift_col}_PSI_vs_baseline"] = round(
                psi(pd.to_numeric(baseline[drift_col], errors="coerce"), col), 4
            )
    return s


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, type=Path, help="source CSV (never modified)")
    p.add_argument("--target", default=None, help="target column (for reporting balance)")
    p.add_argument("--out", default=".", type=Path, help="output directory")
    p.add_argument("--batches", type=int, default=2, help="number of batches")
    p.add_argument("--new-fraction", type=float, default=0.4,
                   help="fraction of rows in the final 'new arrival' batch")
    p.add_argument("--drift-col", default=None,
                   help="numeric column to bias the later batch toward (None = no drift)")
    p.add_argument("--drift-strength", type=float, default=1.2,
                   help="how strongly the later batch over-represents high values of drift-col")
    p.add_argument("--date-col", default="measurement_date")
    p.add_argument("--start", default="2024-01-01", help="first batch start date (YYYY-MM-DD)")
    p.add_argument("--batch-span-days", type=int, default=90)
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    rng = np.random.default_rng(args.seed)
    df = pd.read_csv(args.input)
    n = len(df)
    names = (["baseline", "new_arrival"] if args.batches == 2
             else [f"batch_{i+1:02d}" for i in range(args.batches)])

    # --- choose the rows of the final ("new arrival") batch, optionally drift-biased ---
    if args.drift_col and args.drift_col in df.columns:
        x = pd.to_numeric(df[args.drift_col], errors="coerce").fillna(0).to_numpy(dtype=float)
        z = (x - x.mean()) / (x.std() + 1e-9)
        w = 1.0 / (1.0 + np.exp(-args.drift_strength * z))  # higher drift-col -> higher weight
    else:
        w = np.ones(n)
    w = w / w.sum()

    n_new = round(n * args.new_fraction)
    new_idx = rng.choice(n, size=n_new, replace=False, p=w)
    is_new = np.zeros(n, dtype=bool)
    is_new[new_idx] = True

    # remaining rows split (uniformly at random) across the earlier batches
    earlier_idx = np.where(~is_new)[0]
    rng.shuffle(earlier_idx)
    earlier_chunks = np.array_split(earlier_idx, max(args.batches - 1, 1))
    batches_idx = list(earlier_chunks) + [new_idx]

    start = date.fromisoformat(args.start)
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {"source": str(args.input), "seed": args.seed,
                "drift_col": args.drift_col, "drift_strength": args.drift_strength,
                "note": "Teaching simulation. Rows are real; only batch assignment is biased.",
                "batches": {}}
    baseline_df = None
    written = []
    for i, idx in enumerate(batches_idx):
        b = df.iloc[np.sort(idx)].copy()
        # assign synthetic dates inside this batch's window
        win_start = start + timedelta(days=i * args.batch_span_days)
        days = rng.integers(0, args.batch_span_days, size=len(b))
        dates = [win_start + timedelta(days=int(d)) for d in days]
        b.insert(0, args.date_col, pd.to_datetime(sorted(dates)).date)
        b = b.sort_values(args.date_col).reset_index(drop=True)

        fname = f"batch_{i+1:02d}_{names[i]}.csv"
        b.drop(columns=[]).to_csv(out_dir / fname, index=False)
        written.append(fname)
        manifest["batches"][fname] = {
            "window": [str(win_start), str(win_start + timedelta(days=args.batch_span_days - 1))],
            **batch_stats(b, args.target, args.drift_col, baseline_df),
        }
        if i == 0:
            baseline_df = b

    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))
    print("\nWrote:", ", ".join(written), "and manifest.json")


if __name__ == "__main__":
    main()
