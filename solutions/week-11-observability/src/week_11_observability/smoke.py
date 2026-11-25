"""The smoke test: the check a probe cannot perform.

Week 9 ended on an honest limitation, and this module is its answer:

    "A service that answers /health is not a service that is correct. Nothing
    in this week checks the predictions, and a container serving a
    badly-broken model will pass every probe you wrote."

That is not hypothetical. Week 6 built the exhibit: `train.C: 0.001`
over-regularises the logistic regression until it predicts the negative class
for **all 192** test patients — and still scores **ROC-AUC 0.8407**, HIGHER than
the shipped model's 0.8345. Deployed, it loads in milliseconds, answers `/health`
with a 200, passes readiness, passes liveness, and serves HTTP 200s all day.
Kubernetes has no complaint to make. Neither does KServe. The traffic split works
perfectly, sending a tenth of real patients to a model that tells every one of
them they are fine.

A SMOKE TEST IS A DIFFERENT KIND OF QUESTION. A probe asks *is this process
alive?*. A smoke test asks *is this the model we meant to deploy, and does it
still behave like a model?* — after deployment, against the real endpoint,
before traffic is promoted. Four kinds of wrongness, four checks:

  identity   is this the version we published, and did it pass the gate?
  contract   does Week 5's contract still hold at this endpoint?
  behaviour  do obviously-positive and obviously-negative patients come back
             differently? (a constant classifier fails here, whatever its AUC)
  protocol   do both routes agree, so a caller using either gets one answer?

WHY IT RUNS AGAINST A CLIENT, NOT A URL. Every check takes an object with
`.get()`/`.post()`. FastAPI's `TestClient` and `httpx.Client` have the same
surface, so the identical suite runs in-process in the autograder (no server, no
Docker, no cluster) and against a pod through the cluster's ingress. A smoke
test that only exists as a shell script full of `curl` is a smoke test nobody
tests — and `tests/test_smoke_suite.py` includes the negative case, because a
check that has never failed is not known to work.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

# Two patients from the course dataset, chosen because no defensible model
# should confuse them. These are not "typical" rows; they are the ends of the
# distribution, which is what makes them safe to assert on across model
# families. The random forest and the logistic regression disagree about their
# exact probabilities and agree completely about their labels.
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
# `glucose: 0` — the sentinel Week 5 declared illegal. Missing is honest; zero
# is a lie, and the endpoint has to keep saying so.
ILLEGAL = {**CLEARLY_POSITIVE, "glucose": 0.0}

# How far apart the two ends must be. A model that returns nearly the same
# probability for both is not really making a prediction.
#
# MEASURED, and worth knowing before you trust this check: the C=0.001 exhibit
# still has a spread of 0.1754, so THIS check does not catch it — the label
# checks above do. Every check in a suite catches a different failure and none of
# them catches all of them; that is why there are four, and why a suite is not a
# single assertion with extra steps.
MIN_PROBABILITY_SPREAD = 0.10


class Caller(Protocol):
    """Whatever `TestClient` and `httpx.Client` both are."""

    def get(self, url: str, **kwargs: Any) -> Any: ...
    def post(self, url: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    detail: str

    @property
    def mark(self) -> str:
        return "pass" if self.passed else "FAIL"


def check_identity(client: Caller, *, expect_version: str | None = None) -> list[Check]:
    """Who answered, and was it allowed to be there?

    `expect_version` is the store version the rollout MEANT to deploy. Passing
    it turns "something is serving" into "the thing we published is serving",
    which is the difference between a smoke test and a ping.
    """
    response = client.get("/health")
    if response.status_code != 200:
        return [
            Check("identity.health", False, f"/health returned {response.status_code}"),
            Check("identity.gate", False, "not checked — /health did not answer"),
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
    # The gate, asked at the endpoint. Week 6's verdict travelled all the way
    # here inside provenance.json, so the last thing in front of real traffic
    # can refuse a model that was never approved — the check no probe would
    # ever think to make.
    verdict = body.get("gate_verdict")
    checks.append(
        Check(
            "identity.gate",
            verdict == "GO",
            f"gate_verdict={verdict} (a released model must record a GO)",
        )
    )
    return checks


def check_contract(client: Caller) -> list[Check]:
    """Week 5's contract, at whatever endpoint this is."""
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


def check_behaviour(client: Caller) -> list[Check]:
    """Does it still behave like a model?

    The check the C=0.001 exhibit fails (on the labels, not the spread), and
    the reason this module exists.
    """
    checks: list[Check] = []
    scores: dict[str, dict[str, Any]] = {}
    for label, payload in (("positive", CLEARLY_POSITIVE), ("negative", CLEARLY_NEGATIVE)):
        response = client.post("/predict", json=payload)
        if response.status_code != 200:
            return [
                Check(
                    f"behaviour.{label}",
                    False,
                    f"a legal payload returned {response.status_code}",
                )
            ]
        scores[label] = response.json()

    checks.append(
        Check(
            "behaviour.positive_is_positive",
            scores["positive"]["prediction"] == 1,
            f"p={scores['positive']['probability']} -> {scores['positive']['prediction']}",
        )
    )
    checks.append(
        Check(
            "behaviour.negative_is_negative",
            scores["negative"]["prediction"] == 0,
            f"p={scores['negative']['probability']} -> {scores['negative']['prediction']}",
        )
    )
    spread = abs(scores["positive"]["probability"] - scores["negative"]["probability"])
    checks.append(
        Check(
            "behaviour.not_a_constant",
            spread >= MIN_PROBABILITY_SPREAD,
            f"probability spread {spread:.4f} (minimum {MIN_PROBABILITY_SPREAD})",
        )
    )
    return checks


def check_protocol(client: Caller) -> list[Check]:
    """Both doors, one room. A protocol you serve inconsistently is worse than
    one you do not serve at all."""
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


def run_smoke(client: Caller, *, expect_version: str | None = None) -> dict[str, Any]:
    """Every check, in order, always all of them.

    Deliberately does NOT stop at the first failure: after a rollout you want
    the whole picture, because "identity wrong AND behaviour wrong" and
    "identity right BUT behaviour wrong" call for different decisions.
    """
    checks = [
        *check_identity(client, expect_version=expect_version),
        *check_contract(client),
        *check_behaviour(client),
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
    lines.append(
        f"  {report['verdict']} — {report['passed']} passed, {report['failed']} failed"
    )
    if report["verdict"] == "FAIL":
        lines += [
            "",
            "  Every one of those requests got an HTTP response from a pod that is",
            "  Ready, passing both probes, and serving traffic. A rollout that only",
            "  watches the platform would call this a success.",
        ]
    return "\n".join(lines)
