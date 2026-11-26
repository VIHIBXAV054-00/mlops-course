"""Run the data contracts and turn a failure into a JSON report.

`validate_frame` runs a schema with `lazy=True`, so one run lists every violation.
`to_nullable` turns the sentinel zeros into real nulls.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from .schemas import SCHEMA_VERSION, SENTINEL_COLUMNS

# A pandas FutureWarning from inside Pandera's error report. Silenced by message and module only.
warnings.filterwarnings(
    "ignore",
    message="The behavior of DataFrame concatenation with empty or all-NA entries",
    category=FutureWarning,
    module=r"pandera\.backends\.pandas\.error_formatters",
)

# failure cases kept in the report (`n_failure_cases` always has the full count)
MAX_REPORTED_CASES = 50


def read_raw(path: Path) -> pd.DataFrame:
    """Read a measurement CSV as strings, so the schema's `coerce` names any bad cell."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])


def validate_frame(frame: pd.DataFrame, schema, source: str = "") -> dict:
    """Validate `frame` against `schema` and return a report dict.

    Never raises for a data problem. The caller decides what a failure means.
    """
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

    # `index` is the row position, or null for a whole-frame check
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

    # what rule broke, and where it broke
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
    """Replace the sentinel zeros with real nulls and return a new frame.

    It does not fill anything in: the imputer in the model pipeline does that.
    The nullable `Float64` dtype holds `pd.NA`, which plain `float64` cannot.
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
    """Write the verdict to `reports/validation.json`, which is committed to Git."""
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
        # an unfinished `validate_frame` returns an empty report
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
