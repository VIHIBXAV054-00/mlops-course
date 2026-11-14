"""The smoke test: is this the model we meant to release, and does it behave?

Every check takes a client with `.get()` and `.post()`, so the same suite runs in-process
with FastAPI's `TestClient` and against a pod with `httpx.Client`.

  identity   is this the version we published, and did it pass the gate?
  contract   is the illegal `glucose: 0` still rejected with 422?
  behaviour  is a clearly ill patient positive and a healthy one negative?
  protocol   do `/predict` and the V1 route give the same answer?
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

# Exercise 2: two patients from the dataset at the two ends of the risk range.
# Every model the course has trained agrees on their labels.
CLEARLY_POSITIVE = {
    "pregnancies": 6.0,
    "glucose": 183.0,
    "blood_pressure": 84.0,
    "skin_thickness": 32.0,
    "insulin": 190.0,
    "bmi": 40.5,
    "diabetes_pedigree": 0.9,
    "age": 52.0,
}
CLEARLY_NEGATIVE = {
    "pregnancies": 1.0,
    "glucose": 85.0,
    "blood_pressure": 66.0,
    "skin_thickness": 29.0,
    "insulin": 94.0,
    "bmi": 26.6,
    "diabetes_pedigree": 0.351,
    "age": 22.0,
}
ILLEGAL = {**CLEARLY_POSITIVE, "glucose": 0.0}

# Used when no rollout plan is given, for example by `make smoke-local` without one.
DEFAULT_MIN_SPREAD = 0.10


class Caller(Protocol):
    """What `TestClient` and `httpx.Client` have in common."""

    def get(self, url: str, **kwargs: Any) -> Any: ...
    def post(self, url: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str


def check_identity(client: Caller, *, expect_version: str | None = None) -> list[Check]:
    """Who answered, and did it pass the gate?"""
    response = client.get("/health")
    if response.status_code != 200:
        return [
            Check("identity.health", False, f"/health returned {response.status_code}"),
            Check("identity.gate", False, "not checked: /health did not answer"),
        ]
    body = response.json()
    checks = [
        Check(
            "identity.health",
            body.get("status") == "ok",
            f"status={body.get('status')} revision={body.get('revision') or '-'} "
            f"store_version={body.get('store_version') or '-'}",
        )
    ]
    if expect_version is not None:
        checks.append(
            Check(
                "identity.version",
                body.get("store_version") == expect_version,
                f"expected {expect_version}, serving {body.get('store_version')}",
            )
        )
    verdict = body.get("gate_verdict")
    checks.append(
        Check("identity.gate", verdict == "GO", f"gate_verdict={verdict} (a release needs GO)")
    )
    return checks


def check_contract(client: Caller) -> list[Check]:
    """The data contract, at this endpoint."""
    response = client.post("/predict", json=ILLEGAL)
    if response.status_code != 422:
        return [
            Check(
                "contract.illegal_rejected",
                False,
                f"glucose: 0 returned {response.status_code}, expected 422",
            )
        ]
    detail = response.json().get("detail", {})
    failures = detail.get("failures", {}) if isinstance(detail, dict) else {}
    return [
        Check(
            "contract.illegal_rejected",
            any("greater_than" in key for key in failures),
            f"422 naming {sorted(failures) or 'nothing'}",
        )
    ]


def check_behaviour(client: Caller, *, min_spread: float = DEFAULT_MIN_SPREAD) -> list[Check]:
    """Does the model still tell a clearly ill patient from a healthy one?"""
    # TODO(student) Exercise 2: POST `CLEARLY_POSITIVE` and `CLEARLY_NEGATIVE` to /predict.
    # If either answer is not HTTP 200, return one failed Check named "behaviour.positive"
    # or "behaviour.negative". Otherwise return three Checks, in this order:
    #   "behaviour.positive_is_positive"  the positive patient's prediction is 1
    #   "behaviour.negative_is_negative"  the negative patient's prediction is 0
    #   "behaviour.not_a_constant"        the two probabilities differ by at least min_spread
    # Put the probabilities you saw in each Check's detail; check_identity above has the same shape.
    raise NotImplementedError("Exercise 2: write check_behaviour() in smoke.py")


def check_protocol(client: Caller) -> list[Check]:
    """Both routes give the same answer."""
    direct = client.post("/predict", json=CLEARLY_POSITIVE)
    v1 = client.post("/v1/models/diabetes:predict", json={"instances": [CLEARLY_POSITIVE]})
    if direct.status_code != 200 or v1.status_code != 200:
        return [
            Check(
                "protocol.v1_agrees",
                False,
                f"/predict {direct.status_code}, /v1/models/...:predict {v1.status_code}",
            )
        ]
    same = direct.json()["prediction"] == v1.json()["predictions"][0]
    return [
        Check(
            "protocol.v1_agrees",
            same,
            f"/predict {direct.json()['prediction']} vs V1 {v1.json()['predictions'][0]}",
        )
    ]


def run_smoke(
    client: Caller,
    *,
    expect_version: str | None = None,
    min_spread: float = DEFAULT_MIN_SPREAD,
) -> dict[str, Any]:
    """Run every check, without stopping at the first failure."""
    checks = [
        *check_identity(client, expect_version=expect_version),
        *check_contract(client),
        *check_behaviour(client, min_spread=min_spread),
        *check_protocol(client),
    ]
    failed = [c for c in checks if not c.passed]
    return {
        "verdict": "PASS" if not failed else "FAIL",
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail} for c in checks],
    }


def format_smoke(report: dict[str, Any]) -> str:
    lines = ["", "  smoke test"]
    for check in report["checks"]:
        mark = "pass" if check["passed"] else "FAIL"
        lines.append(f"    {mark:5} {check['name']:34} {check['detail']}")
    lines.append("")
    lines.append(f"  {report['verdict']} — {report['passed']} passed, {report['failed']} failed")
    return "\n".join(lines)
