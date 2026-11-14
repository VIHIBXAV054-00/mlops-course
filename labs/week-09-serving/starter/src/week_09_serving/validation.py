"""Run the Pandera contracts, turn sentinel zeros into nulls, and save the verdict as JSON.

`lazy=True` collects every violation in one pass instead of stopping at the first.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from .schemas import SCHEMA_VERSION, SENTINEL_COLUMNS

# Hide a pandas FutureWarning raised inside Pandera; it says nothing about your data.
warnings.filterwarnings(
    "ignore",
    message="The behavior of DataFrame concatenation with empty or all-NA entries",
    category=FutureWarning,
    module=r"pandera\.backends\.pandas\.error_formatters",
)

# Keep at most this many cases; `n_failure_cases` always has the full count.
MAX_REPORTED_CASES = 50


def read_raw(path: Path) -> pd.DataFrame:
    """Read a measurement CSV as strings; the schema's `coerce=True` converts the types.

    So a bad cell is reported by the contract, with its column and value.
    """
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])


def validate_frame(frame: pd.DataFrame, schema, source: str = "") -> dict:
    """Validate `frame` against `schema` and return a report dict; bad data does not raise."""
    report: dict = {
        "source": source,
        "schema": schema.to_schema().name if hasattr(schema, "to_schema") else str(schema),
        "schema_version": SCHEMA_VERSION,
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "passed": True,
        "n_failure_cases": 0,
        "truncated": False,
        "failure_cases": [],
        "by_check": {},
        "by_column": {},
    }

    try:
        schema.validate(frame, lazy=True)
        return report
    except pa.errors.SchemaErrors as errors:
        cases = errors.failure_cases

    report["passed"] = False
    report["n_failure_cases"] = int(len(cases))

    # The five columns Pandera gives us. `index` is the 0-based row position in
    # the validated frame, or null for a whole-dataframe check.
    kept = cases.head(MAX_REPORTED_CASES)
    report["truncated"] = bool(len(cases) > len(kept))
    report["failure_cases"] = [
        {
            "schema_context": row["schema_context"],
            "column": None if pd.isna(row["column"]) else str(row["column"]),
            "check": str(row["check"]),
            "failure_case": None if pd.isna(row["failure_case"]) else str(row["failure_case"]),
            "row": None if pd.isna(row["index"]) else int(row["index"]),
        }
        for _, row in kept.iterrows()
    ]

    # Two summaries, because they answer different questions: "what rule broke"
    # (fix the data) versus "where did it break" (find the producer).
    report["by_check"] = {
        str(check): int(count) for check, count in cases["check"].value_counts().items()
    }
    report["by_column"] = {
        str(column): int(count)
        for column, count in cases["column"].value_counts(dropna=False).items()
        if not pd.isna(column)
    }
    return report


def to_nullable(frame: pd.DataFrame) -> pd.DataFrame:
    """Replace the sentinel zeros with nulls (nullable `Float64`). Returns a new frame.

    It fills nothing in: the imputer inside the model does that.
    """
    converted = frame.copy()
    for column in SENTINEL_COLUMNS:
        if column not in converted.columns:
            continue
        converted[column] = (
            pd.to_numeric(converted[column], errors="coerce")
            .astype("Float64")
            .replace(0, pd.NA)
        )
    return converted


def sentinel_counts(frame: pd.DataFrame) -> dict:
    """How many sentinel zeros sit in each affected column. For reporting only."""
    counts = {}
    for column in SENTINEL_COLUMNS:
        if column in frame.columns:
            values = pd.to_numeric(frame[column], errors="coerce")
            counts[column] = int((values == 0).sum())
    return counts


def write_report(report: dict, path: Path) -> Path:
    """Write the report as JSON.

    `reports/validation.json` is a `cache: false` DVC output, so it is committed to Git.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    return path


def read_report(path: Path) -> dict:
    """The last recorded verdict, or {} if validation has never run."""
    if not path.exists():
        return {}
    return json.loads(path.read_text() or "{}")


NOT_IMPLEMENTED = "No report: `validate_frame` returned nothing."


def format_report(report: dict, limit: int = 15) -> str:
    """A human-readable rendering of a report, for the CLI."""
    if not report:
        return NOT_IMPLEMENTED

    lines = []
    verdict = "PASS" if report.get("passed") else "FAIL"
    lines.append(
        f"[{verdict}] {report.get('schema')} v{report.get('schema_version')} "
        f"on {report.get('source')} — {report.get('rows')} rows"
    )
    if report.get("passed"):
        return "\n".join(lines)

    lines.append(f"  {report['n_failure_cases']} failure case(s)")
    lines.append("")
    lines.append(f"  {'row':>5}  {'column':<18} {'check':<32} failure_case")
    lines.append(f"  {'-' * 5}  {'-' * 18} {'-' * 32} {'-' * 24}")
    for case in report["failure_cases"][:limit]:
        row = "—" if case["row"] is None else str(case["row"])
        column = case["column"] or "(whole frame)"
        failure = case["failure_case"]
        failure = "—" if failure is None else failure[:24]
        lines.append(f"  {row:>5}  {column:<18} {case['check']:<32} {failure}")
    if len(report["failure_cases"]) > limit:
        lines.append(f"  ... and {len(report['failure_cases']) - limit} more")
    if report.get("truncated"):
        lines.append(
            f"  (report keeps the first {MAX_REPORTED_CASES} cases; "
            f"n_failure_cases is the true total)"
        )
    return "\n".join(lines)
