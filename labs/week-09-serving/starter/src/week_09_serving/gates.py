"""The model quality gate: acceptance criteria in, GO/NO-GO out. New in Week 6.

Week 5 put a gate at the ENTRANCE — is this data allowed in? Week 6 puts one at
the EXIT — is this model allowed out? Same idea, three differences that matter:

1. **It is at the end of the pipeline, so it cannot work by withholding work.**
   Week 5's gate had teeth because `prepare` declared the verdict file as a
   dependency: fail, and nothing downstream ran. There is nothing downstream of
   `evaluate`. So this gate writes a verdict, exits non-zero — and `register`
   and `promote` refuse without a GO. **A gate is only as strong as the thing
   that consults it.** A verdict file nobody reads is a log line.

2. **A failing model gate must not destroy the model.** You need the artifact to
   work out why it failed. `models/model.pkl` survives a NO-GO on purpose.

3. **The criteria are data, not code.** Everything this module decides comes from
   the `acceptance` block of `params.yaml`: a versioned, reviewable, diffable
   statement of what "good enough" means, that a person agreed to before the run.
   `evaluate_gate` itself is pure — plain dicts in, a plain dict out, no
   filesystem, no model, no network — which is what makes the whole criteria
   matrix unit-testable in CI with nothing installed but this package.

The four kinds of check, and why one of each is not enough:

    minimum      absolute floors. "Better than last time" is not the same as
                 "good enough", and a ratchet with no floor can walk downhill
                 one tolerated step at a time.
    regression   is this worse than the model we already have? Needs a recorded
                 baseline and a tolerance; see baseline.py.
    slice        is it good enough for each group we named, or only on average?
    fairness     are the errors distributed in a way we are willing to defend?

And the reason for four rather than one, measured on this lab's own model: set
`train.C: 0.001` in params.yaml and logistic regression predicts "no diabetes"
for all 192 test patients. Accuracy 0.6510 — exactly the majority-class rate.
F1 0.0000. **ROC-AUC 0.8407, higher than the shipped model's.** A gate that
looked only at ROC-AUC would wave that model into production.
"""

from __future__ import annotations

PASS, FAIL, SKIPPED = "pass", "fail", "skipped"


def _round(value):
    return None if value is None else round(float(value), 4)


def _check(**fields) -> dict:
    """One check result. `id`, `kind` and `status` are mandatory by convention."""
    return fields


def evaluate_gate(
    metrics: dict,
    slices: dict,
    baseline: dict,
    acceptance: dict,
) -> dict:
    """Apply every acceptance criterion and return the verdict. Pure function.

    `metrics`  — the aggregate scores from `metrics/metrics.json`.
    `slices`   — the per-group report from `metrics/slices.json` (may be {}).
    `baseline` — the recorded champion, `{"metrics": {...}}` (may be {}).
    `acceptance` — the `acceptance` block of `params.yaml`.

    A missing input never silently becomes a pass. It becomes a `skipped` check
    with a reason, the skipped count is reported in the headline, and the
    verdict is computed from the checks that actually ran. That distinction —
    "we looked and it was fine" versus "we did not look" — is the whole reason
    this returns a list of checks rather than a boolean.
    """
    checks: list[dict] = []

    checks += _minimum_checks(metrics, acceptance.get("minimum") or {})
    regression_checks, deltas = _regression_checks(
        metrics, baseline, acceptance.get("regression") or {}
    )
    checks += regression_checks
    checks += _slice_checks(metrics, slices, acceptance.get("slice_rules") or {})
    checks += _fairness_checks(slices, acceptance.get("fairness") or {})

    passed = sum(1 for c in checks if c["status"] == PASS)
    failed = sum(1 for c in checks if c["status"] == FAIL)
    skipped = sum(1 for c in checks if c["status"] == SKIPPED)

    return {
        "verdict": "NO-GO" if failed else "GO",
        "criteria_version": str(acceptance.get("criteria_version", "unset")),
        "primary_metric": (acceptance.get("regression") or {}).get("primary_metric"),
        "summary": {"passed": passed, "failed": failed, "skipped": skipped},
        "deltas": deltas,
        "checks": checks,
    }


def _minimum_checks(metrics: dict, minimum: dict) -> list[dict]:
    """Absolute floors. True regardless of what came before, or of any baseline.

    `minimum.accuracy` in this lab is 0.70, and the number is chosen rather than
    inherited: the majority-class rate on this test set is 0.6510, so a constant
    "nobody has diabetes" classifier scores 0.6510. **A floor a constant
    classifier clears is not a floor.**
    """
    out = []
    for metric in sorted(minimum):
        required = float(minimum[metric])
        observed = metrics.get(metric)
        if observed is None:
            out.append(
                _check(
                    id=f"minimum.{metric}",
                    kind="minimum",
                    metric=metric,
                    required=_round(required),
                    observed=None,
                    status=SKIPPED,
                    reason=f"{metric} was not recorded by the evaluate stage",
                )
            )
            continue
        out.append(
            _check(
                id=f"minimum.{metric}",
                kind="minimum",
                metric=metric,
                required=_round(required),
                observed=_round(observed),
                status=PASS if float(observed) >= required else FAIL,
                reason=None
                if float(observed) >= required
                else f"{metric} {observed:.4f} is below the floor {required:.4f}",
            )
        )
    return out


def _regression_checks(metrics: dict, baseline: dict, rules: dict) -> tuple[list, dict]:
    """Is this model worse than the one we already have?

    Two decisions are encoded here and both belong to a human:

    - WHICH metric is primary. On this dataset the choice is not academic:
      `train.C: 0.01` drops F1 by 0.0254 while ROC-AUC *rises* by 0.0100 and
      accuracy does not move at all. Gate on ROC-AUC and that change is an
      improvement; gate on F1 and it is a regression. Same model.
    - HOW MUCH drop is tolerated. `max_drop` is a noise band, not a budget for
      getting worse. It exists because re-running a pipeline on a different
      machine moves the fourth decimal, not because a 1% loss is acceptable.

    With no baseline recorded the check is SKIPPED, loudly. It is emphatically
    not a pass: "the first model is always fine" is how a ratchet starts at the
    bottom.
    """
    primary = rules.get("primary_metric")
    max_drop = rules.get("max_drop")
    also = list(rules.get("also_report") or [])
    baseline_metrics = (baseline or {}).get("metrics") or {}

    deltas = {}
    for metric in ([primary] if primary else []) + also:
        if metric and metric in metrics and metric in baseline_metrics:
            deltas[metric] = _round(float(metrics[metric]) - float(baseline_metrics[metric]))

    if not primary or max_drop is None:
        return [
            _check(
                id="regression",
                kind="regression",
                status=SKIPPED,
                reason="acceptance.regression declares no primary_metric/max_drop",
            )
        ], deltas

    if not baseline_metrics:
        return [
            _check(
                id=f"regression.{primary}",
                kind="regression",
                metric=primary,
                observed=_round(metrics.get(primary)),
                baseline=None,
                status=SKIPPED,
                reason="no baseline recorded — run `make baseline-sync` once a "
                "champion exists (metrics/baseline.json is absent or empty)",
            )
        ], deltas

    observed, previous = metrics.get(primary), baseline_metrics.get(primary)
    if observed is None or previous is None:
        return [
            _check(
                id=f"regression.{primary}",
                kind="regression",
                metric=primary,
                observed=_round(observed),
                baseline=_round(previous),
                status=SKIPPED,
                reason=f"{primary} missing from the metrics or the baseline",
            )
        ], deltas

    delta = float(observed) - float(previous)
    dropped = delta < -float(max_drop)
    return [
        _check(
            id=f"regression.{primary}",
            kind="regression",
            metric=primary,
            baseline=_round(previous),
            observed=_round(observed),
            delta=_round(delta),
            max_drop=_round(max_drop),
            status=FAIL if dropped else PASS,
            reason=(
                f"{primary} fell {abs(delta):.4f} against the champion's "
                f"{previous:.4f}, past the tolerated {float(max_drop):.4f}"
            )
            if dropped
            else None,
        )
    ], deltas


def _slice_checks(metrics: dict, slices: dict, rules: dict) -> list[dict]:
    """One check per group in the slice report.

    A group with fewer than `min_support` rows or `min_positives` positives is
    skipped, because its metrics mean nothing. Otherwise it fails when its F1 is
    below `min_f1` or more than `max_f1_gap` below the aggregate F1.
    """
    min_support = int(rules.get("min_support", 0))
    min_positives = int(rules.get("min_positives", 0))
    min_f1 = rules.get("min_f1")
    max_gap = rules.get("max_f1_gap")
    aggregate_f1 = metrics.get("f1")

    if not slices or not slices.get("slices"):
        return [
            _check(
                id="slice",
                kind="slice",
                status=SKIPPED,
                reason="no slice report — the evaluate stage produced no "
                "metrics/slices.json",
            )
        ]

    out = []
    for axis, groups in slices["slices"].items():
        for group, m in groups.items():
            check = _check(
                id=f"slice.{axis}.{group}",
                kind="slice",
                axis=axis,
                group=group,
                n=m["n"],
                n_positives=m["n_positives"],
                f1=m["f1"],
            )

            too_small = None
            if m["n"] < min_support:
                too_small = f"support {m['n']} < min_support {min_support}"
            elif m["n_positives"] < min_positives:
                too_small = f"positives {m['n_positives']} < min_positives {min_positives}"
            if too_small:
                out.append(dict(check, status=SKIPPED, reason=too_small))
                continue

            gap = None
            if aggregate_f1 is not None and m["f1"] is not None:
                gap = round(float(aggregate_f1) - float(m["f1"]), 4)

            violations: list[str] = []
            if min_f1 is not None and m["f1"] is not None and m["f1"] < float(min_f1):
                violations.append(
                    f"f1 {m['f1']:.4f} below the slice floor {float(min_f1):.4f}"
                )
            if max_gap is not None and gap is not None and gap > float(max_gap):
                violations.append(
                    f"f1 is {gap:.4f} below the aggregate, past the tolerated "
                    f"{float(max_gap):.4f}"
                )

            out.append(
                dict(
                    check,
                    gap_to_aggregate=gap,
                    min_f1=_round(min_f1),
                    max_f1_gap=_round(max_gap),
                    status=FAIL if violations else PASS,
                    reason="; ".join(violations) or None,
                )
            )
    return out


def _fairness_checks(slices: dict, rules: dict) -> list[dict]:
    """Gate each axis named in `rules` with its own limits; the other axes are only reported."""
    out = []
    for axis in sorted(rules):
        if not slices or axis not in (slices.get("fairness") or {}):
            out.append(
                _check(
                    id=f"fairness.{axis}",
                    kind="fairness",
                    axis=axis,
                    status=SKIPPED,
                    reason=f"no fairness report for axis {axis!r}",
                )
            )
            continue

        block = slices["fairness"][axis]
        axis_rules = rules[axis] or {}
        limits = {
            "selection_rate_gap": axis_rules.get("max_selection_rate_gap"),
            "tpr_gap": axis_rules.get("max_tpr_gap"),
            "equalized_odds_difference": axis_rules.get("max_equalized_odds_difference"),
        }
        for key, limit in limits.items():
            if limit is None:
                continue
            observed = block.get(key)
            if observed is None:
                out.append(
                    _check(
                        id=f"fairness.{axis}.{key}",
                        kind="fairness",
                        axis=axis,
                        metric=key,
                        limit=_round(limit),
                        observed=None,
                        status=SKIPPED,
                        reason=f"{key} is undefined for this axis (fewer than two "
                        "groups have the rate)",
                    )
                )
                continue
            exceeded = float(observed) > float(limit)
            out.append(
                _check(
                    id=f"fairness.{axis}.{key}",
                    kind="fairness",
                    axis=axis,
                    metric=key,
                    limit=_round(limit),
                    observed=_round(observed),
                    status=FAIL if exceeded else PASS,
                    reason=f"{key} {observed:.4f} exceeds the limit {float(limit):.4f}"
                    if exceeded
                    else None,
                )
            )
    return out


def format_gate(report: dict) -> str:
    """The verdict, for the CLI.

    Three rules about this output, each of which exists because of a mistake
    made earlier in this course:

    1. The SKIPPED count is in the headline, never only in the JSON. A guard
       whose failure mode is a green tick is worse than no guard, because it is
       believed.
    2. A NO-GO names the failing checks and the size of the miss, first, before
       anything else. "The gate failed" is not an actionable sentence.
    3. Every number that went into the decision is printed, including the ones
       that passed. A gate you cannot audit is a gate you will eventually
       switch off.
    """
    if not report:
        return "No gate report."

    summary = report["summary"]
    lines = [
        f"{report['verdict']} — {summary['passed']} passed, "
        f"{summary['failed']} failed, {summary['skipped']} SKIPPED "
        f"(criteria v{report['criteria_version']})"
    ]

    failures = [c for c in report["checks"] if c["status"] == FAIL]
    if failures:
        lines.append("")
        lines.append("  FAILED:")
        for c in failures:
            lines.append(f"    {c['id']:<40} {c.get('reason')}")

    skips = [c for c in report["checks"] if c["status"] == SKIPPED]
    if skips:
        lines.append("")
        lines.append("  SKIPPED (not checked — read these before you trust the verdict):")
        for c in skips:
            lines.append(f"    {c['id']:<40} {c.get('reason')}")

    lines.append("")
    lines.append(f"  {'check':<40} {'status':<8} detail")
    lines.append(f"  {'-' * 40} {'-' * 8} {'-' * 40}")
    for c in report["checks"]:
        lines.append(f"  {c['id']:<40} {c['status']:<8} {_detail(c)}")

    if report.get("deltas"):
        lines.append("")
        lines.append("  versus the recorded champion:")
        for metric, delta in report["deltas"].items():
            arrow = "+" if delta >= 0 else ""
            lines.append(f"    {metric:<12} {arrow}{delta:.4f}")
    return "\n".join(lines)


def _detail(check: dict) -> str:
    kind = check.get("kind")
    if kind == "minimum":
        return f"observed {check.get('observed')} vs floor {check.get('required')}"
    if kind == "regression":
        if check.get("delta") is None:
            return check.get("reason") or ""
        return (
            f"{check.get('observed')} vs champion {check.get('baseline')} "
            f"(delta {check['delta']:+.4f}, tolerated -{check.get('max_drop')})"
        )
    if kind == "slice":
        if check["status"] == SKIPPED:
            return check.get("reason") or ""
        return (
            f"n={check.get('n')} pos={check.get('n_positives')} "
            f"f1={check.get('f1')} gap={check.get('gap_to_aggregate')}"
        )
    if kind == "fairness":
        return f"observed {check.get('observed')} vs limit {check.get('limit')}"
    return check.get("reason") or ""


def format_gate_markdown(report: dict) -> str:
    """The gate verdict as GitHub-flavoured markdown, for a job summary.

    Why this lives here rather than as a shell heredoc inside the workflow:
    a `run:` block is the one place in a project that nothing tests. Logic that
    ends up there is invisible to the linter, invisible to pytest, and only
    runs on a machine you have to push to in order to observe. Keep workflows
    thin -- checkout, install, invoke -- and put anything with a branch in it
    somewhere a test can reach.
    """
    if not report:
        return "### Gate\n\nNo verdict recorded — the gate never ran.\n"

    verdict = report["verdict"]
    summary = report.get("summary", {})
    mark = "PASS" if verdict == "GO" else "FAIL"

    lines = [
        f"### {mark} — gate verdict: `{verdict}`",
        "",
        f"criteria `{report.get('criteria_version', 'unset')}` · "
        f"**{summary.get('passed', 0)} passed** · "
        f"**{summary.get('failed', 0)} failed** · "
        f"**{summary.get('skipped', 0)} skipped**",
        "",
    ]

    failed = [c for c in report.get("checks", []) if c.get("status") == "fail"]
    if failed:
        lines += ["| failed check | detail |", "| --- | --- |"]
        for check in failed:
            lines.append(f"| `{check['id']}` | {check.get('reason', '')} |")
        lines.append("")

    skipped = [c for c in report.get("checks", []) if c.get("status") == "skipped"]
    if skipped:
        lines.append(f"<details><summary>{len(skipped)} criteria were NOT evaluated</summary>")
        lines.append("")
        lines += ["| skipped check | why |", "| --- | --- |"]
        for check in skipped:
            lines.append(f"| `{check['id']}` | {check.get('reason', '')} |")
        lines += ["", "</details>", ""]

    deltas = report.get("deltas") or {}
    if deltas:
        lines += ["| metric | delta vs champion |", "| --- | ---: |"]
        for name, value in deltas.items():
            lines.append(f"| {name} | {value:+.4f} |")
        lines.append("")

    return "\n".join(lines)
