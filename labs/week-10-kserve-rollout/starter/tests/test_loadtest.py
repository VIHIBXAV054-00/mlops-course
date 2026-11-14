"""The load generator's arithmetic, checked offline.

A load test is a measuring instrument, and an instrument nobody calibrated is a
rumour. Percentiles are the easy thing to get subtly wrong — there are nine
common definitions, off-by-one errors are invisible against real data, and the
number still *looks* fine. So the maths is a pure function over a list, and this
file feeds it lists whose answers are known by hand.

Nothing here touches the network. The tally logic is checked the same way, with
a hand-built `LoadResult`, because "which revision answered?" is the claim the
whole canary exercise rests on.
"""

from __future__ import annotations

from collections import Counter

import pytest

from week_10_kserve_rollout.loadtest import (
    LoadResult,
    format_split,
    format_against_release,
    percentile,
    summarise,
)

pytestmark = pytest.mark.unit

ONE_TO_HUNDRED = [float(n) for n in range(1, 101)]


def test_percentiles_on_a_known_list():
    """1..100, nearest-rank: p50 is 50, p95 is 95, p99 is 99."""
    assert percentile(ONE_TO_HUNDRED, 50) == 50.0
    assert percentile(ONE_TO_HUNDRED, 95) == 95.0
    assert percentile(ONE_TO_HUNDRED, 99) == 99.0
    assert percentile(ONE_TO_HUNDRED, 100) == 100.0


def test_percentiles_do_not_care_about_input_order():
    assert percentile(list(reversed(ONE_TO_HUNDRED)), 95) == 95.0


def test_a_single_sample_is_every_percentile():
    assert percentile([4.2], 50) == 4.2
    assert percentile([4.2], 99) == 4.2


def test_an_empty_sample_is_zero_rather_than_a_crash():
    """A run that got no responses must still print a table.

    The alternative is an IndexError in the middle of a rollout, which loses the
    error count as well — and the error count was the interesting part.
    """
    assert percentile([], 95) == 0.0


def test_the_tail_is_what_moves_and_the_mean_hides_it():
    """Why this course quotes p95 and never a mean.

    Ninety-nine requests at 5 ms and one at 2 s: the mean says 25 ms, which
    describes nobody. The p99 says 2 s, which describes the person who left.
    """
    latencies = [5.0] * 99 + [2000.0]
    assert percentile(latencies, 50) == 5.0
    assert percentile(latencies, 99) == 5.0
    assert percentile(latencies, 100) == 2000.0
    mean = sum(latencies) / len(latencies)
    assert mean > 4 * percentile(latencies, 50)


def _result() -> LoadResult:
    result = LoadResult(concurrency=4, requests=10, wall_seconds=2.0)
    result.latencies_ms = [float(n) for n in range(1, 11)]
    result.statuses = Counter({200: 9, 0: 1})
    result.served_by = Counter({("v1", "diabetes-predictor-00001"): 8,
                                ("v2", "diabetes-predictor-00002"): 1})
    return result


def test_a_summary_reports_errors_and_throughput():
    summary = summarise(_result())
    assert summary["requests"] == 10
    assert summary["errors"] == 1, "a connection failure is a result, not an exception"
    assert summary["error_rate"] == 0.1
    assert summary["throughput_rps"] == 5.0
    assert summary["p50_ms"] == 5.0


def test_the_tally_attributes_responses_to_revisions():
    """The claim the canary exercise rests on.

    Without this, `canaryTrafficPercent: 10` is something the manifest says and
    nobody checked.
    """
    summary = summarise(_result())
    assert summary["served_by"]["v1/diabetes-predictor-00001"] == 8
    assert summary["served_by"]["v2/diabetes-predictor-00002"] == 1


def test_the_split_report_quotes_its_own_sampling_error():
    """An honest small-sample number is a range.

    9 responses is not evidence about a 10% split, and the report has to say so
    rather than print "11.1%" as though it were a measurement of the policy.
    """
    text = format_split(summarise(_result()), declared=10)
    assert "declared canary percentage: 10%" in text
    assert "±" in text, "a measured percentage without its sampling spread invites over-reading"
    assert "errors: 1 of 10" in text


def test_responses_that_do_not_identify_themselves_are_still_counted():
    """An older image that reports no revision must not vanish from the tally.

    Silently dropping unattributable responses would make a split look cleaner
    than it is — the worst direction for a measurement to be wrong in.
    """
    result = LoadResult(concurrency=1, requests=2, wall_seconds=1.0)
    result.statuses = Counter({200: 2})
    result.served_by = Counter({(None, None): 2})
    summary = summarise(result)
    assert summary["served_by"]["?/?"] == 2


def test_the_release_comparison_marks_a_level_over_the_limit():
    rows = [
        {"concurrency": 1, "throughput_rps": 120.0, "p95_ms": 9.0, "error_rate": 0.0},
        {"concurrency": 64, "throughput_rps": 98.0, "p95_ms": 1657.0, "error_rate": 0.0},
    ]
    text = format_against_release(rows, max_p95_ms=300, max_error_rate=0.01)
    lines = [line for line in text.splitlines() if "concurrency" in line]
    assert lines[0].endswith("within")
    assert lines[1].endswith("OVER")
