"""MLflow tracking helpers.

Trimmed from Week 3: the parameter sweep and its run-search machinery belong to
Week 3 and are gone. What remains is the connection, the git-commit tag, a
reachability probe, and one new query — finding runs by DATA VERSION, which is
the question Week 4 makes askable.
"""

from __future__ import annotations

import subprocess
import urllib.error
import urllib.request

import mlflow
import pandas as pd
from mlflow.exceptions import MlflowException

from .config import Settings


def connect(settings: Settings) -> None:
    """Point the MLflow client at the tracking server and select the experiment."""
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name)


def mlflow_available(settings: Settings, timeout: float = 2.0) -> bool:
    """Is the tracking server reachable?

    Lifted out of the test fixtures in Week 3 so that production code can use it
    too: the `train` DVC stage needs to run in CI, where no server exists.
    """
    try:
        urllib.request.urlopen(
            settings.mlflow_tracking_uri + "/health", timeout=timeout
        )
        return True
    except (urllib.error.URLError, OSError):
        return False


def git_commit() -> str:
    """The current git commit, or "unknown" outside a checkout."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def search_runs_by_data_version(settings: Settings, md5: str) -> pd.DataFrame:
    """Every run in this experiment that trained on a given data version.

    This is the query Week 3 could not express. The filter runs server-side
    against Postgres, and it is only possible because the `train` stage tagged
    the run with the data's content hash.
    """
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    try:
        return mlflow.search_runs(
            experiment_names=[settings.mlflow_experiment_name],
            filter_string=f"tags.dvc_md5 = '{md5}'",
            order_by=["attributes.start_time DESC"],
            output_format="pandas",
        )
    except MlflowException:
        return pd.DataFrame()


def prefect_available(settings, timeout: float = 3.0) -> bool:
    """Is the Prefect API answering?

    Same shape as `mlflow_available`, and for the same reason: production code
    needs to be able to say "the thing you configured is not there" in a
    sentence a student can act on, rather than surfacing a client library's
    connection error.
    """
    import urllib.error
    import urllib.request

    try:
        urllib.request.urlopen(settings.prefect_api_url.rstrip("/") + "/health", timeout=timeout)
        return True
    except (urllib.error.URLError, OSError):
        return False
