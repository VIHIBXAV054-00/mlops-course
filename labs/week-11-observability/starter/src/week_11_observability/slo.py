"""SLIs, SLOs, error budgets and burn rates — the arithmetic, with no network.

Every function here is pure. That is not tidiness: it is what lets the whole of
this week's decision-making be tested in the autograder, with no Prometheus, no
Docker and no clock. The queries live in `prometheus/rules/`, the numbers they
are compared against live in `slo.yaml`, and this module is the bridge that
proves the two agree.

THE FOUR WORDS, in the order they stop being interchangeable:

  **SLI** — a measurement. A ratio of good events to valid events. Not "uptime",
  not "p95": a fraction, between 0 and 1, that you could in principle count by
  hand from a request log.

  **SLO** — a target for that measurement over a window. `0.99 over 30 days`.
  Internal. You choose it, and choosing it is an engineering decision about how
  much reliability is worth paying for, not a wish.

  **SLA** — an SLO with a consequence attached, usually money, usually written
  by a lawyer. Always looser than the SLO it is built on, because you want to
  find out you are in trouble before your customer's contract says so.

  **Error budget** — `1 - target`, expressed as something you can spend. This is
  the one that changes behaviour, and it is the reason the whole apparatus
  exists: it turns "be reliable" (unfalsifiable, unarguable, and therefore
  ignorable) into a quantity that gets used up.

WHY A BUDGET IS A DECISION-MAKING DEVICE AND NOT A SCORE.

A 99% target over 30 days permits 7 hours 12 minutes of failure. Two things
follow, and the second one is the one people miss:

  * Budget spent → stop shipping features and fix reliability. Nobody argues,
    because the number was agreed in advance and everybody can read it.
  * Budget NOT spent → you are over-delivering, which is also information.
    Reliability bought is capacity, latency headroom or velocity not bought.
    A service that has spent none of its budget for six months is a service
    whose target is wrong.

The second point is why a 100% target is not an ambitious target but an
incoherent one: it forbids ever deploying anything.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

SECONDS_PER_DAY = 24 * 60 * 60

# Suffix -> seconds, for the window strings in slo.yaml ("5m", "6h", "3d").
# Deliberately the same suffixes Prometheus accepts, so a window can be copied
# between slo.yaml and a rule expression without translation. The set is small
# and closed on purpose: accepting "1w" here and not in the rules would be a
# silent divergence between the document and the alert.
_DURATION_UNITS = {"s": 1, "m": 60, "h": 3600, "d": SECONDS_PER_DAY}


def parse_duration(text: str) -> float:
    """`"5m"` -> 300.0. Raises on anything it does not fully understand.

    Refusing rather than defaulting matters here. A typo like `"5min"` that
    silently became 5 seconds would produce an alerting rule that is wrong in a
    direction nobody would look at again.
    """
    raw = str(text).strip()
    if len(raw) < 2 or raw[-1] not in _DURATION_UNITS:
        raise ValueError(
            f"cannot parse duration {text!r}: expected a number followed by one of "
            f"{sorted(_DURATION_UNITS)}, e.g. '5m', '6h', '3d'."
        )
    try:
        value = float(raw[:-1])
    except ValueError as exc:
        raise ValueError(f"cannot parse duration {text!r}: {exc}") from exc
    if value <= 0:
        raise ValueError(f"duration {text!r} must be positive.")
    return value * _DURATION_UNITS[raw[-1]]


def format_duration(seconds: float) -> str:
    """Seconds -> the shortest human sentence. For printing budgets, only."""
    seconds = float(seconds)
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {int(secs)}s"
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{int(hours)}h {int(minutes)}m"
    days, hours = divmod(hours, 24)
    return f"{int(days)}d {int(hours)}h {int(minutes)}m"


@dataclass(frozen=True)
class Objective:
    """One SLI with a target. `threshold_seconds` is set only for latency."""

    name: str
    description: str
    target: float
    window_days: int
    threshold_seconds: float | None = None

    @property
    def error_budget(self) -> float:
        """The fraction of events allowed to be bad. `1 - target`.

        ROUNDED, and not out of fussiness. `1.0 - 0.99` is
        `0.010000000000000009` in binary floating point, and that number would
        end up written into a PromQL threshold and printed on a dashboard —
        where it is not merely ugly but actively confusing, because it looks
        like somebody chose it. Twelve decimal places is far more precision than
        any SLO carries and removes the artefact exactly.
        """
        return round(1.0 - self.target, 12)

    @property
    def budget_seconds(self) -> float:
        """The budget as TIME, which is the form people actually reason in.

        A translation with a caveat that is worth stating out loud: this
        equates "1% of requests failed" with "1% of the window was down", and
        the two are the same only if traffic is uniform. A four-minute outage at
        the daily peak spends far more of a request-based budget than four
        minutes at 04:00. The minutes figure is for conversations; the ratio is
        what the alert actually evaluates.
        """
        return self.error_budget * self.window_days * SECONDS_PER_DAY


@dataclass(frozen=True)
class BurnAlert:
    """One row of the multi-window multi-burn-rate table."""

    name: str
    burn_rate: float
    long_window: str
    short_window: str
    budget_consumed: float
    severity: str

    def consumed_by_end_of_long_window(self, window_days: int) -> float:
        """`burn_rate * long_window / SLO window` — the fraction of the budget
        that has been spent by the time this row's long window is full.

        This is the number that makes the table make sense: 14.4x for one hour
        is not "very bad", it is "2% of the month, gone, in the last hour".
        """
        window_seconds = window_days * SECONDS_PER_DAY
        return self.burn_rate * parse_duration(self.long_window) / window_seconds

    def threshold(self, objective: Objective) -> float:
        """The error ratio the rule compares against.

        A burn rate multiplies the budget, so an alert on a 99% target at 14.4x
        fires when the observed error ratio exceeds `14.4 * 0.01 = 0.144`. That
        is the number that appears in the PromQL, and
        `tests/test_prometheus_rules.py` recomputes it from slo.yaml rather than
        trusting the literal in the rules file.
        """
        return self.burn_rate * objective.error_budget

    def time_to_exhaustion(self, objective: Objective) -> float:
        """Seconds until the whole budget is gone, if this rate continues."""
        return objective.window_days * SECONDS_PER_DAY / self.burn_rate


@dataclass(frozen=True)
class SloDocument:
    """Everything `slo.yaml` declares, parsed and validated."""

    service: str
    window_days: int
    objectives: dict[str, Objective]
    burn_alerts: tuple[BurnAlert, ...]

    def objective(self, name: str) -> Objective:
        try:
            return self.objectives[name]
        except KeyError as exc:
            raise KeyError(
                f"slo.yaml declares no objective named {name!r}; it has "
                f"{sorted(self.objectives)}."
            ) from exc


DEFAULT_SLO_PATH = Path("slo.yaml")


def load_slo(path: Path | None = None) -> SloDocument:
    """Read and VALIDATE slo.yaml.

    Validated at load time, with sentences you can act on, for the same reason
    Week 6 validates the acceptance block: a malformed threshold that silently
    defaults to something permissive is a promise nobody made and nobody can
    find.
    """
    slo_path = Path(path) if path is not None else _find_slo_file()
    raw = yaml.safe_load(slo_path.read_text()) or {}

    window_days = int(raw.get("window_days", 30))
    if window_days <= 0:
        raise ValueError("slo.yaml: window_days must be positive.")

    service = str(raw.get("service") or "").strip()
    if not service:
        raise ValueError("slo.yaml: `service` must name the service this promise is about.")

    objectives: dict[str, Objective] = {}
    for name, spec in (raw.get("objectives") or {}).items():
        target = float(spec.get("target", -1))
        if not 0.0 < target < 1.0:
            raise ValueError(
                f"slo.yaml: objectives.{name}.target must be strictly between 0 and 1; "
                f"got {target}. A target of 1.0 is not an ambitious promise, it is an "
                f"incoherent one — it forbids ever deploying anything."
            )
        threshold = spec.get("threshold_seconds")
        objectives[name] = Objective(
            name=name,
            description=str(spec.get("description", "")).strip(),
            target=target,
            window_days=window_days,
            threshold_seconds=None if threshold is None else float(threshold),
        )
    if not objectives:
        raise ValueError("slo.yaml declares no objectives — an empty promise is not a promise.")

    alerts: list[BurnAlert] = []
    for spec in raw.get("burn_rate_alerts") or []:
        alert = BurnAlert(
            name=str(spec["name"]),
            burn_rate=float(spec["burn_rate"]),
            long_window=str(spec["long_window"]),
            short_window=str(spec["short_window"]),
            budget_consumed=float(spec["budget_consumed"]),
            severity=str(spec["severity"]),
        )
        if parse_duration(alert.short_window) >= parse_duration(alert.long_window):
            raise ValueError(
                f"slo.yaml: burn_rate_alerts.{alert.name} has a short window "
                f"({alert.short_window}) that is not shorter than its long window "
                f"({alert.long_window}). The short window exists to ask 'is this STILL "
                f"happening?' — one that is longer asks nothing."
            )
        if alert.severity not in {"page", "ticket"}:
            raise ValueError(
                f"slo.yaml: burn_rate_alerts.{alert.name}.severity must be 'page' "
                f"(wake a human) or 'ticket' (it can wait). Got {alert.severity!r}."
            )
        alerts.append(alert)
    if not alerts:
        raise ValueError("slo.yaml declares no burn_rate_alerts — an SLO nothing watches is prose.")

    return SloDocument(
        service=service,
        window_days=window_days,
        objectives=objectives,
        burn_alerts=tuple(alerts),
    )


def _find_slo_file() -> Path:
    """Look next to the package's project root, then in the working directory.

    The same two-step every other file lookup in this project does, and for the
    same reason: `uv run` from the lab directory and a container with WORKDIR
    /app disagree about what "." means.
    """
    candidates = [
        Path(__file__).resolve().parents[2] / "slo.yaml",
        DEFAULT_SLO_PATH,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        "slo.yaml not found. It is the declaration every alerting rule in "
        "prometheus/rules/slo.yml is derived from; run make targets from the lab "
        "directory."
    )


# ── Budget arithmetic ────────────────────────────────────────────────────────


def burn_rate(bad_events: float, total_events: float, objective: Objective) -> float:
    """How fast the budget is being spent, in multiples of "exactly on plan".

    1.0 means the budget runs out precisely at the end of the window. 0 means
    nothing is being spent. 14.4 means a 30-day budget is gone in about 50
    hours.

    Zero traffic returns 0.0 rather than raising or returning NaN, and the
    choice deserves a sentence because it is a real trade-off: a service nobody
    is calling is not burning budget, which is true — and it is also how a
    completely dead service can look healthy on a ratio-based SLI. That gap is
    exactly what `ServiceDown` (`up == 0`) exists to cover, and it is why an
    availability SLO alone is not enough.
    """
    if total_events <= 0:
        return 0.0
    return (bad_events / total_events) / objective.error_budget


def budget_remaining(bad_events: float, total_events: float, objective: Objective) -> float:
    """The fraction of the budget still unspent, clamped to [0, 1].

    Clamped because "you are at -40% of your budget" is a number people argue
    about instead of acting on. Spent is spent.
    """
    if total_events <= 0:
        return 1.0
    allowed = objective.error_budget * total_events
    if allowed <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - bad_events / allowed))


def time_to_exhaustion(remaining_fraction: float, rate: float, objective: Objective) -> float:
    """Seconds until the budget is gone at the current burn rate.

    `inf` when nothing is burning, which prints as "never at this rate" and is
    the honest answer.
    """
    if rate <= 0:
        return math.inf
    return remaining_fraction * objective.window_days * SECONDS_PER_DAY / rate


def budget_table(doc: SloDocument) -> list[dict[str, Any]]:
    """One row per objective: the target, the budget, and what it means."""
    rows = []
    for objective in doc.objectives.values():
        rows.append(
            {
                "objective": objective.name,
                "target": objective.target,
                "window_days": objective.window_days,
                "error_budget": objective.error_budget,
                "budget_time": format_duration(objective.budget_seconds),
                "threshold_seconds": objective.threshold_seconds,
            }
        )
    return rows


def alert_table(doc: SloDocument, objective_name: str = "availability") -> list[dict[str, Any]]:
    """The burn-rate table, with every derived number computed rather than typed."""
    objective = doc.objective(objective_name)
    rows = []
    for alert in doc.burn_alerts:
        rows.append(
            {
                "name": alert.name,
                "severity": alert.severity,
                "burn_rate": alert.burn_rate,
                "long_window": alert.long_window,
                "short_window": alert.short_window,
                "budget_consumed": alert.consumed_by_end_of_long_window(doc.window_days),
                "declared_budget_consumed": alert.budget_consumed,
                "error_ratio_threshold": alert.threshold(objective),
                "exhausted_in": format_duration(alert.time_to_exhaustion(objective)),
            }
        )
    return rows


def format_report(doc: SloDocument) -> str:
    """What `make slo-budget` prints. Text, because it is meant to be read."""
    lines: list[str] = []
    lines.append(f"SLO document for `{doc.service}` — {doc.window_days}-day rolling window")
    lines.append("")
    lines.append("  objective     target    error budget            over the window")
    lines.append("  " + "-" * 66)
    for row in budget_table(doc):
        threshold = (
            f"  (good = faster than {row['threshold_seconds']}s)"
            if row["threshold_seconds"] is not None
            else ""
        )
        lines.append(
            f"  {row['objective']:<12}  {row['target']:>6.4f}  "
            f"{row['error_budget'] * 100:>6.2f}% of requests  =  {row['budget_time']:<14}{threshold}"
        )
    lines.append("")
    lines.append("  Burn-rate alerts (Google SRE Workbook, Alerting on SLOs, Table 5-8)")
    lines.append("  measured against the `availability` objective:")
    lines.append("")
    lines.append(
        "  name    sev     burn   long   short   budget spent   error ratio   budget gone in"
    )
    lines.append("  " + "-" * 76)
    for row in alert_table(doc):
        lines.append(
            f"  {row['name']:<7} {row['severity']:<7} {row['burn_rate']:>5.1f}x "
            f"{row['long_window']:>6} {row['short_window']:>7}   "
            f"{row['budget_consumed'] * 100:>10.1f}%   {row['error_ratio_threshold']:>11.4f}   "
            f"{row['exhausted_in']}"
        )
    lines.append("")
    lines.append(
        "  Read the `fast` row as: if more than "
        f"{alert_table(doc)[0]['error_ratio_threshold'] * 100:.1f}% of requests fail for an hour"
    )
    lines.append(
        "  (and are still failing in the last 5 minutes), 2% of the month's budget is"
    )
    lines.append("  already gone — and at that rate the rest goes in "
                 f"{alert_table(doc)[0]['exhausted_in']}. That is worth waking someone for.")
    return "\n".join(lines)


if __name__ == "__main__":  # pragma: no cover - a convenience for the container
    print(format_report(load_slo()))
