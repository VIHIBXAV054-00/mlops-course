"""Running the contracts, and turning a failure into an artifact.

New in Week 5. Three jobs:

1. `validate_frame` — run a schema in LAZY mode and return a JSON-able report
   instead of a traceback. Lazy matters: by default Pandera raises on the FIRST
   violation, which turns a broken file into a scavenger hunt. `lazy=True`
   collects every violation in one pass, so one run tells you everything wrong
   with the file.
2. `to_nullable` — the sentinel conversion. `0` in the five affected columns
   becomes a real null, which is the only honest representation of "not
   measured".
3. `write_report` / `read_report` — the verdict as a file, because a gate that
   leaves no evidence is an opinion.

The report is deliberately a plain dict of primitives. It goes into Git (as a
`cache: false` DVC output), into an MLflow artifact, and into a test assertion,
and none of those want a pandas object.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

import pandas as pd
import pandera.pandas as pa

from .schemas import SCHEMA_VERSION, SENTINEL_COLUMNS

# Pandera 0.32.1 assembles its failure-case report with pd.concat, which emits a
# pandas FutureWarning about all-NA entries whenever a `not_nullable` check
# fires. It is entirely inside the library, it says nothing about your data, and
# it prints on exactly the runs where a student most needs to read the output.
# Silenced narrowly — by message and module — so a genuine pandas deprecation in
# OUR code still surfaces.
warnings.filterwarnings(
    "ignore",
    message="The behavior of DataFrame concatenation with empty or all-NA entries",
    category=FutureWarning,
    module=r"pandera\.backends\.pandas\.error_formatters",
)

# How many failure cases to keep in the report. A truly broken file can produce
# thousands; the report has to stay readable and diffable in Git. The full count
# is always recorded, so nothing is hidden — see `truncated` in the report.
MAX_REPORTED_CASES = 50


def read_raw(path: Path) -> pd.DataFrame:
    """Read a measurement CSV with NO type inference at all.

    Everything comes back as `str`, and the schema's `coerce = True` does the
    type work. That ordering is deliberate: pandas' own inference silently turns
    a column with one bad cell into `object` and moves on, so the failure
    surfaces later, somewhere else, as a confusing error about an unrelated
    operation. Letting the contract do the coercion means a bad cell is reported
    HERE, with the column named and the offending value quoted.
    """
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])


def validate_frame(frame: pd.DataFrame, schema, source: str = "") -> dict:
    """Validate `frame` against `schema` and return a report dict.

    Never raises for a data problem — a validation failure is data, not an
    exception, and the caller decides what to do about it. (The `validate`
    pipeline stage decides to exit non-zero; a test decides to assert.)
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
    """Replace the sentinel zeros with real nulls. Returns a new frame.

    This is where the dataset's oldest lie gets corrected. Since Week 1 a
    glucose of 0 has been sitting in the data meaning "not measured" while
    claiming to mean "zero", and every model so far has averaged those zeros
    into its notion of a normal patient.

    Note what this function does NOT do: it does not fill anything in. Turning a
    sentinel into a null is a statement of fact — we do not know this value.
    Deciding what to do about not knowing is a MODELLING decision, and it lives
    in the sklearn Pipeline (see model.py) so that it travels with the model to
    serving. That separation is the difference between a data fix and a data
    guess.

    The nullable `Float64` dtype (capital F) is required, not cosmetic: plain
    `float64` cannot hold `pd.NA` and silently converts it to `NaN`, which
    muddles "missing" with "not a number".
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
    """Persist the verdict next to the pointer, the lock file and the metrics.

    `reports/validation.json` is a `cache: false` DVC output, so it lands in Git
    rather than the DVC cache. That is the same convention Week 4 used for
    `metrics.json`, and for the same reason: the evidence for a claim belongs in
    the same commit as the claim.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n")
    return path


def read_report(path: Path) -> dict:
    """The last recorded verdict, or {} if validation has never run."""
    if not path.exists():
        return {}
    return json.loads(path.read_text() or "{}")


NOT_IMPLEMENTED = (
    "No report — `validation.validate_frame` returns nothing yet.\n"
    "  See the TODO in src/week_08_prefect_flow/validation.py (Exercise 1)."
)


def format_report(report: dict, limit: int = 15) -> str:
    """A human-readable rendering of a report, for the CLI."""
    if not report:
        # An empty report is the starter's honest "not done yet". Saying so beats
        # rendering a blank table that looks like a clean bill of health.
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
