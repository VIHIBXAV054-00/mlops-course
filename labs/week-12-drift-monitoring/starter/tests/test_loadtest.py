"""The load generator's arithmetic, checked offline.

Percentiles and the per-revision tally are tested on lists whose answers are known by hand.
"""

from __future__ import annotations

from collections import Counter

import pytest

from week_12_drift_monitoring.loadtest import (
    LoadResult,
    format_split,
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
    """A run that got no responses still prints a table with its error count."""
    assert percentile([], 95) == 0.0


def test_the_tail_is_what_moves_and_the_mean_hides_it():
    """99 requests at 5 ms and one at 2 s: the mean (25 ms) describes no request."""
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
    """Counting which revision answered is how you check `canaryTrafficPercent`."""
    summary = summarise(_result())
    assert summary["served_by"]["v1/diabetes-predictor-00001"] == 8
    assert summary["served_by"]["v2/diabetes-predictor-00002"] == 1


def test_the_split_report_quotes_its_own_sampling_error():
    """With few responses, the measured share is a range, not a single number."""
    text = format_split(summarise(_result()), declared=10)
    assert "declared canary share: 10%" in text
    assert "±" in text, "a measured share without its sampling spread invites over-reading"
    assert "errors: 1 of 10" in text


def test_responses_that_do_not_identify_themselves_are_still_counted():
    """A response without a revision is counted as `?/?`, not dropped."""
    result = LoadResult(concurrency=1, requests=2, wall_seconds=1.0)
    result.statuses = Counter({200: 2})
    result.served_by = Counter({(None, None): 2})
    summary = summarise(result)
    assert summary["served_by"]["?/?"] == 2
