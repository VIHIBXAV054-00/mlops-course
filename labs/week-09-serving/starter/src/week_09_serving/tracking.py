"""MLflow and Prefect helpers: connect, tag the git commit, check a server is up, find runs."""

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
    """Is the tracking server reachable? Lets the `train` stage run in CI, where there is none."""
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
    """Every run in this experiment tagged with this data version (`tags.dvc_md5`)."""
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
    """Is the Prefect API answering? Lets the CLI say clearly that the server is down."""
    import urllib.error
    import urllib.request

    try:
        urllib.request.urlopen(settings.prefect_api_url.rstrip("/") + "/health", timeout=timeout)
        return True
    except (urllib.error.URLError, OSError):
        return False
