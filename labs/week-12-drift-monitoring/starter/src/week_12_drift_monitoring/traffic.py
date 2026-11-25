"""A traffic generator: a steady, seeded mix of requests so the dashboards and alerts have data.

Valid requests carry patients from a cohort CSV, so the prediction log has a distribution:

    reference   data/raw/batch_01_baseline.csv
    drifted     data/raw/batch_02_new_arrival.csv   (higher glucose)
    probe       one fixed patient, repeated
"""

from __future__ import annotations

import random
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import pandas as pd

from .data import FEATURE_COLUMNS
from .drift_policy import contract_admissible
from .loadtest import PROBE_PATIENT

# fails one contract check: glucose 0 is a missing value, so the API returns 422
ILLEGAL_PATIENT = {**PROBE_PATIENT, "glucose": 0.0}

# Real, unmodified rows. Only which rows went into which batch was chosen.
COHORTS: dict[str, str] = {
    "reference": "data/raw/batch_01_baseline.csv",
    "drifted": "data/raw/batch_02_new_arrival.csv",
}
DEFAULT_COHORT = "reference"

# Rows with impossible zeros come back as 422, so cohorts are filtered with
# contract_admissible, the same function that filters the reference window.


@dataclass
class TrafficResult:
    """What was sent, and what came back."""

    requests: int = 0
    wall_seconds: float = 0.0
    statuses: Counter = field(default_factory=Counter)
    kinds: Counter = field(default_factory=Counter)
    errors: list[str] = field(default_factory=list)
    # which cohort was sent, so the summary can name it
    cohort: "Cohort | None" = None

    @property
    def rate(self) -> float:
        return self.requests / self.wall_seconds if self.wall_seconds else 0.0

    def summary(self) -> str:
        lines = [
            f"  sent      : {self.requests} requests in {self.wall_seconds:.1f}s "
            f"({self.rate:.1f}/s)",
            "  by kind   : "
            + ", ".join(f"{kind}={count}" for kind, count in sorted(self.kinds.items())),
            "  by status : "
            + ", ".join(f"{status}={count}" for status, count in sorted(self.statuses.items())),
        ]
        if self.cohort is not None:
            note = f"  cohort    : {self.cohort.name} ({self.cohort.kept} legal patients"
            if self.cohort.dropped:
                note += (
                    f"; {self.cohort.dropped} of {self.cohort.total} dropped for "
                    f"sentinel zeros -- Week 5's contract, not a bug)"
                )
            else:
                note += ")"
            lines.append(note)
        if self.errors:
            lines.append(f"  transport : {len(self.errors)} failed to send, e.g. {self.errors[0]}")
        return "\n".join(lines)


def plan(count: int, mix: dict[str, float], seed: int = 42) -> list[str]:
    """Decide the kind of every request before sending any. Weights need not sum to 1."""
    if count <= 0:
        return []
    kinds = sorted(mix)
    weights = [max(0.0, float(mix[kind])) for kind in kinds]
    total = sum(weights)
    if total <= 0:
        raise ValueError("traffic mix must give at least one kind a positive weight.")
    rng = random.Random(seed)
    return rng.choices(kinds, weights=weights, k=count)


@dataclass(frozen=True)
class Cohort:
    """The patients a named cohort will send, and how many rows were dropped."""

    name: str
    patients: list[dict[str, Any]]
    kept: int
    total: int

    @property
    def dropped(self) -> int:
        return self.total - self.kept

    def patient(self, rng: random.Random) -> dict[str, Any]:
        """One patient, sampled with replacement, so a small cohort can serve many requests."""
        return dict(rng.choice(self.patients))


def load_cohort(name: str, project_root: Path | None = None) -> Cohort:
    """Load a named cohort: real rows, contract-legal only. `probe` repeats one patient."""
    if name == "probe":
        return Cohort(name=name, patients=[dict(PROBE_PATIENT)], kept=1, total=1)
    if name not in COHORTS:
        raise ValueError(
            f"unknown cohort {name!r}; expected one of "
            f"{sorted(['probe', *COHORTS])}."
        )
    root = project_root or Path(__file__).resolve().parents[2]
    path = root / COHORTS[name]
    if not path.exists():
        raise FileNotFoundError(
            f"cohort file {path} is missing. The measurement batches are committed "
            f"to Git (they are the raw material data/measurements.csv is built "
            f"from), so a fresh clone has them — check you are running from the lab "
            f"directory."
        )
    frame = pd.read_csv(path)
    missing = [column for column in FEATURE_COLUMNS if column not in frame.columns]
    if missing:
        raise KeyError(f"cohort {name!r} at {path} has no column(s) {missing}.")
    frame = frame[list(FEATURE_COLUMNS)]
    legal = contract_admissible(frame)
    if legal.empty:
        raise ValueError(
            f"every row of cohort {name!r} carries at least one sentinel zero, so "
            f"every request would be a 422 and the prediction log would stay empty. "
            f"That is Week 5's contract doing its job, not a bug here."
        )
    return Cohort(
        name=name,
        patients=legal.astype(float).to_dict(orient="records"),
        kept=len(legal),
        total=len(frame),
    )


def _request_for(
    kind: str,
    index: int,
    patient: dict[str, Any] | None = None,
) -> tuple[str, str, dict[str, Any] | None]:
    """(method, path, json body) for one request. `patient=None` sends the probe patient."""
    body = patient if patient is not None else PROBE_PATIENT
    if kind == "valid":
        return "POST", "/predict", body
    if kind == "violation":
        # always the same illegal patient, so the same check fails every time
        return "POST", "/predict", ILLEGAL_PATIENT
    if kind == "v1":
        return "POST", "/v1/models/diabetes:predict", {"instances": [body]}
    if kind == "notfound":
        # A different path every time. With `route_label` returning the route
        # template these collapse to one series. With the raw path as a label
        # they are `index` separate series.
        return "GET", f"/does-not-exist/{index}", None
    if kind == "health":
        return "GET", "/health", None
    raise ValueError(
        f"unknown traffic kind {kind!r}; expected one of "
        "valid, violation, v1, notfound, health."
    )


def generate(
    url: str,
    count: int = 300,
    mix: dict[str, float] | None = None,
    rate: float = 20.0,
    seed: int = 42,
    timeout: float = 10.0,
    cohort: str = DEFAULT_COHORT,
) -> TrafficResult:
    """Send `count` requests at roughly `rate` per second and report the mix.

    Paced, not as fast as possible, so the requests spread over many scrapes.
    """
    mix = mix or {"valid": 0.9, "violation": 0.1}
    kinds = plan(count, mix, seed=seed)
    result = TrafficResult()
    interval = 1.0 / rate if rate > 0 else 0.0

    # A separate RNG for patients, so changing the mix does not change which patients are sent.
    cohort_data = load_cohort(cohort)
    patients = random.Random(seed + 1)

    started = time.perf_counter()
    with httpx.Client(base_url=url.rstrip("/"), timeout=timeout) as client:
        for index, kind in enumerate(kinds):
            slot_started = time.perf_counter()
            method, path, body = _request_for(kind, index, cohort_data.patient(patients))
            try:
                response = client.request(method, path, json=body)
                result.statuses[response.status_code] += 1
            except httpx.HTTPError as exc:
                # a transport failure is not a status code, so it is counted separately
                result.errors.append(f"{type(exc).__name__}: {exc}")
                result.statuses["transport-error"] += 1
            result.kinds[kind] += 1
            result.requests += 1
            elapsed = time.perf_counter() - slot_started
            if interval > elapsed:
                time.sleep(interval - elapsed)
    result.wall_seconds = time.perf_counter() - started
    result.cohort = cohort_data
    return result


def parse_mix(text: str) -> dict[str, float]:
    """`"valid=9,violation=1"` -> `{"valid": 9.0, "violation": 1.0}`."""
    mix: dict[str, float] = {}
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" not in part:
            raise ValueError(
                f"cannot parse traffic mix {text!r}: expected `kind=weight` pairs, "
                "e.g. 'valid=9,violation=1'."
            )
        kind, _, weight = part.partition("=")
        if not kind.strip():
            raise ValueError(
                f"cannot parse traffic mix {text!r}: {part!r} has no kind before the `=`."
            )
        mix[kind.strip()] = float(weight)
    if not mix:
        raise ValueError(f"traffic mix {text!r} is empty.")
    return mix
