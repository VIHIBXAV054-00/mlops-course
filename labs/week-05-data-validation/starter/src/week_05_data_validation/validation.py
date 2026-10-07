"""Run a contract, turn its failures into a report, and convert sentinel zeros.

The report is a dict of plain values, so it can go into Git, into MLflow and
into a test.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from .schemas import SCHEMA_VERSION, SENTINEL_COLUMNS

# A pandas warning from inside Pandera's report code; it says nothing about our data.
warnings.filterwarnings(
    "ignore",
    message="The behavior of DataFrame concatenation with empty or all-NA entries",
    category=FutureWarning,
    module=r"pandera\.backends\.pandas\.error_formatters",
)

# The report keeps the first 50 failure cases; `n_failure_cases` is the true total.
MAX_REPORTED_CASES = 50


def read_raw(path: Path) -> pd.DataFrame:
    """Read a measurement CSV with every value as text. The contract converts the types."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])


def validate_frame(frame: pd.DataFrame, schema, source: str = "") -> dict:
    """Check `frame` against `schema` and return a report. A failure is not an exception."""
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
    # TODO(student) Exercise 1: write a try/except block.
    #   - try: check `frame` against `schema` in lazy mode, so that every failure
    #     is collected, not only the first.
    #   - except: catch `SchemaErrors` and pass the exception's
    #     `failure_cases` table to `_add_failures`.
    # After the block, return `report`.
    # Reference: https://pandera.readthedocs.io/en/stable/lazy_validation.html
    raise NotImplementedError("validate_frame is not written yet (Exercise 1).")


def _add_failures(report: dict, cases: pd.DataFrame) -> None:
    """Fill the failure fields of `report` from Pandera's `failure_cases` table."""
    report["passed"] = False
    report["n_failure_cases"] = int(len(cases))

    kept = cases.head(MAX_REPORTED_CASES)
    report["truncated"] = bool(len(cases) > len(kept))
    # `index` is the 0-based row position, or null for a check on the whole frame.
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
    report["by_check"] = {
        str(check): int(count) for check, count in cases["check"].value_counts().items()
    }
    report["by_column"] = {
        str(column): int(count)
        for column, count in cases["column"].value_counts(dropna=False).items()
        if not pd.isna(column)
    }


def to_nullable(frame: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of `frame` with the sentinel zeros replaced by missing values.

    It fills nothing in: the model's imputer does that (see model.py).
    """
    converted = frame.copy()
    # TODO(student) Exercise 3: in each of the SENTINEL_COLUMNS that `converted`
    # has, change the column to the nullable type "Float64" and replace 0 with
    # pd.NA. Leave every other column as it is.
    return converted


def sentinel_counts(frame: pd.DataFrame) -> dict:
    """How many zeros each sentinel column holds."""
    counts = {}
    for column in SENTINEL_COLUMNS:
        if column in frame.columns:
            values = pd.to_numeric(frame[column], errors="coerce")
            counts[column] = int((values == 0).sum())
    return counts


def write_report(report: dict, path: Path) -> Path:
    """Write the report as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    return path


def read_report(path: Path) -> dict:
    """The last written report, or {} if there is none."""
    if not path.exists():
        return {}
    return json.loads(path.read_text() or "{}")


def format_report(report: dict, limit: int = 15) -> str:
    """The report as a table, for the command line."""
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
            f"  (the report keeps the first {MAX_REPORTED_CASES} cases; "
            "n_failure_cases is the true total)"
        )
    return "\n".join(lines)
