"""The prediction log: one JSON line per scored request, so drift can be computed on the inputs.

Off unless PREDICTION_LOG_PATH is set. It holds patient measurements, so it is bounded.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import pandas as pd

# read once, when the app is built
PATH_ENV = "PREDICTION_LOG_PATH"
MAX_ROWS_ENV = "PREDICTION_LOG_MAX_ROWS"

# a few megabytes, so a classroom run never reaches it by accident
DEFAULT_MAX_ROWS = 50_000

# the `event` field tells this line apart from the access log line on stdout
EVENT = "prediction"


class PredictionLog:
    """An append-only JSONL sink for scored requests. Disabled unless a path is set."""

    def __init__(
        self,
        path: str | Path | None = None,
        max_rows: int = DEFAULT_MAX_ROWS,
        logger: logging.Logger | None = None,
    ) -> None:
        self.path = Path(path) if path else None
        self.max_rows = int(max_rows)
        self.enabled = self.path is not None
        self._logger = logger or logging.getLogger("week12.predictions")
        # counted, not re-read from disk on every request
        self._written = 0
        self._warned = False
        if self.enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._written = _count_lines(self.path)

    @classmethod
    def from_env(cls, logger: logging.Logger | None = None) -> PredictionLog:
        """Build from the environment. No `PREDICTION_LOG_PATH` gives a disabled log."""
        raw_max = os.getenv(MAX_ROWS_ENV)
        try:
            max_rows = int(raw_max) if raw_max else DEFAULT_MAX_ROWS
        except ValueError as exc:
            raise ValueError(
                f"{MAX_ROWS_ENV}={raw_max!r} is not an integer. It bounds the "
                f"prediction log; a malformed bound is worse than none, because "
                f"nobody would look at it again."
            ) from exc
        if max_rows <= 0:
            raise ValueError(f"{MAX_ROWS_ENV} must be positive; got {max_rows}.")
        return cls(path=os.getenv(PATH_ENV), max_rows=max_rows, logger=logger)

    def record(
        self,
        features: dict[str, Any],
        probability: float,
        prediction: int,
        model_version: str | None = None,
        request_id: str | None = None,
    ) -> bool:
        """Append one scored request. Returns whether anything was written.

        At `max_rows` it stops writing and warns once, so the window goes stale. `logged_at` shows that.
        """
        if not self.enabled or self.path is None:
            return False
        if self._written >= self.max_rows:
            if not self._warned:
                self._warned = True
                self._logger.warning(
                    json.dumps(
                        {
                            "event": "prediction_log_full",
                            "path": str(self.path),
                            "max_rows": self.max_rows,
                            "note": (
                                "no further predictions will be logged; the drift "
                                "window will go stale rather than empty, which is "
                                "why every row carries logged_at"
                            ),
                        },
                        sort_keys=True,
                    )
                )
            return False

        record = {
            "event": EVENT,
            # seconds since the epoch, so the window age is a subtraction
            "logged_at": time.time(),
            "request_id": request_id,
            "model_version": model_version,
            "prediction": int(prediction),
            "probability": float(probability),
            # flat, one key per feature, like the reference window
            **{str(name): _as_number(value) for name, value in features.items()},
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
        self._written += 1
        return True

    @property
    def rows_written(self) -> int:
        """Rows this instance believes are on disk. For tests and `make` targets."""
        return self._written


def _as_number(value: Any) -> Any:
    """Coerce to float where possible, so a numpy scalar cannot fail the request."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _count_lines(path: Path) -> int:
    """How many rows are already there. Zero for a missing file."""
    if not path.exists():
        return 0
    with path.open("rb") as handle:
        return sum(1 for _ in handle)


def read_window(
    path: str | Path,
    window_rows: int | None = None,
    columns: list[str] | None = None,
) -> pd.DataFrame:
    """Read the log as a frame, keeping the newest `window_rows` rows.

    Malformed lines, such as a truncated last line, are skipped and counted in `attrs`.
    """
    log_path = Path(path)
    if not log_path.exists():
        raise FileNotFoundError(
            f"no prediction log at {log_path}. Drift needs the ROWS, and Week 11's "
            f"metrics do not contain them. Turn the log on and send some traffic:\n"
            f"    make predictions-on\n"
            f"    make traffic-drift"
        )

    records: list[dict[str, Any]] = []
    skipped = 0
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            skipped += 1
            continue
        if record.get("event") == EVENT:
            records.append(record)

    if window_rows is not None and window_rows > 0:
        records = records[-window_rows:]

    frame = pd.DataFrame.from_records(records)
    frame.attrs["skipped_lines"] = skipped
    frame.attrs["source"] = str(log_path)
    if columns is not None and not frame.empty:
        missing = [name for name in columns if name not in frame.columns]
        if missing:
            raise KeyError(
                f"the prediction log at {log_path} has no column(s) {missing}. "
                f"drift.yaml gates features the log does not contain, which means "
                f"one of the two was changed without the other. Columns present: "
                f"{sorted(frame.columns)}"
            )
        frame = frame[columns]
    return frame


def window_age_seconds(frame: pd.DataFrame, now: float | None = None) -> float | None:
    """How old the newest row in the window is, in seconds. `None` if unknown."""
    if frame.empty or "logged_at" not in frame.columns:
        return None
    newest = pd.to_numeric(frame["logged_at"], errors="coerce").max()
    if pd.isna(newest):
        return None
    return float((time.time() if now is None else now) - float(newest))
