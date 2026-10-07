"""MLflow tracking helpers: connect, check the server, tag the commit, search runs.

You do not need to change this module.
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
    """Return True if the tracking server answers."""
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
    """Every run in this experiment tagged with the given `dvc_md5`."""
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
