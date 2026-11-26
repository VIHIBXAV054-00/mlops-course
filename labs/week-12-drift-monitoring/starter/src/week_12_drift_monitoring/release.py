"""Read and check `release.yaml`, the rollout plan for a rollout.

The smoke test, the canary manifest test and the load test read their thresholds from it.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

PLACEHOLDER = "<fill in>"
VERSION_PATTERN = re.compile(r"^v\d+$")


def release_path(project_root: Path | None = None) -> Path:
    root = project_root or Path(__file__).resolve().parents[2]
    return root / "release.yaml"


def load_release(path: Path | None = None) -> dict[str, Any]:
    path = path or release_path()
    return yaml.safe_load(path.read_text()) or {}


def value(release: dict[str, Any], key: str) -> Any:
    """Look up a dotted key, such as `smoke.min_probability_spread`."""
    current: Any = release
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(f"release.yaml has no `{key}`")
        current = current[part]
    return current


def _placeholders(node: Any, prefix: str = "") -> list[str]:
    if isinstance(node, dict):
        found: list[str] = []
        for key, child in node.items():
            found += _placeholders(child, f"{prefix}{key}.")
        return found
    if isinstance(node, list):
        return [f"{prefix}{i}" for i, item in enumerate(node) if item == PLACEHOLDER]
    return [prefix.rstrip(".")] if node == PLACEHOLDER else []


def _number(release: dict[str, Any], key: str, low: float, high: float) -> str | None:
    try:
        number = value(release, key)
    except KeyError as missing:
        return str(missing)
    if isinstance(number, bool) or not isinstance(number, (int, float)):
        return f"`{key}` must be a number, not {number!r}"
    if not low < number <= high:
        return f"`{key}` is {number}; it must be above {low} and at most {high}"
    return None


def problems(release: dict[str, Any]) -> list[str]:
    """Everything that stops this request from being used. An empty list means it is ready."""
    found = [f"`{key}` is still `{PLACEHOLDER}`" for key in _placeholders(release)]
    if found:
        return found

    for key in ("model.candidate", "model.replaces"):
        try:
            version = value(release, key)
        except KeyError as missing:
            found.append(str(missing))
            continue
        if not VERSION_PATTERN.match(str(version)):
            found.append(f"`{key}` is {version!r}; use a store version such as v2")
    if release.get("model", {}).get("candidate") == release.get("model", {}).get("replaces"):
        found.append("`model.candidate` and `model.replaces` name the same version")

    percent = release.get("canary", {}).get("percent")
    if isinstance(percent, bool) or not isinstance(percent, int) or not 1 <= percent <= 50:
        found.append(f"`canary.percent` is {percent!r}; use a whole number from 1 to 50")

    for key, low, high in (
        ("smoke.min_probability_spread", 0, 1),
        ("load.expected_rps", 0, 10_000),
        ("load.max_p95_ms", 0, 60_000),
        ("load.max_error_rate", 0, 1),
    ):
        problem = _number(release, key, low, high)
        if problem:
            found.append(problem)

    for section in ("promote", "rollback"):
        conditions = (release.get(section) or {}).get("when")
        if not isinstance(conditions, list) or not conditions or not all(
            isinstance(item, str) and item.strip() for item in conditions
        ):
            found.append(f"`{section}.when` must list at least one condition, one sentence each")
    return found
