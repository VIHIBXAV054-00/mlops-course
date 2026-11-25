"""Reading workflow files as data.

Week 7's subject is a YAML file that a machine you do not own executes on your
behalf. That file is worth treating like any other input: parse it, assert
things about it, and refuse to trust a claim you have not checked.

Everything here is offline and pure. `KNOWN_ACTIONS` is a **recorded
snapshot**, not a live query — a lint that phones GitHub would fail in the
autograder, and a course that quietly depended on the network would be
teaching the opposite of Weeks 4 to 6.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

# Recorded from the GitHub API on 2026-08-06. Re-verify before each term; the
# whole point of Exercise 1 is that this table goes stale and nobody notices.
#
# TWO NUMBERS PER ACTION, and the difference between them cost this lab a red
# build before it cost you one.
#
#   major_tag     the highest `vN` tag that actually EXISTS in the repository.
#                 This is the only thing `uses: owner/action@vN` can resolve.
#   release_major the major of the newest published RELEASE.
#
# They are usually equal, because most action authors move a `vN` tag forward
# with each release. `astral-sh/setup-uv` does not: its newest release is
# v9.0.0 and there is no `v8` or `v9` tag at all, so `@v9` fails with
# "Unable to resolve action ... unable to find version v9" — measured, on a
# real runner, while writing this lab.
#
# The lesson generalises past this one action: **"latest release" is not the
# same question as "what can I pin to".** An API that answers the first will
# happily hand you something that does not exist as a ref.
KNOWN_ACTIONS: dict[str, dict[str, int]] = {
    "actions/checkout": {"major_tag": 7, "release_major": 7},
    "actions/setup-node": {"major_tag": 7, "release_major": 7},
    "actions/setup-python": {"major_tag": 7, "release_major": 7},
    "actions/upload-artifact": {"major_tag": 7, "release_major": 7},
    "actions/cache": {"major_tag": 6, "release_major": 6},
    "actions/upload-pages-artifact": {"major_tag": 5, "release_major": 5},
    "actions/deploy-pages": {"major_tag": 5, "release_major": 5},
    # The outlier. Pin the exact release tag, not a major that is not there.
    "astral-sh/setup-uv": {"major_tag": 7, "release_major": 9},
}
KNOWN_LATEST_AS_OF = "2026-08-06"


# `owner/repo@ref`, optionally `owner/repo/path@ref` for actions in a subdir.
_USES = re.compile(r"^(?P<action>[\w.-]+/[\w.-]+)(?:/[\w./-]+)?@(?P<ref>.+)$")


def load_workflow(path: Path) -> dict:
    """Parse a workflow file.

    One trap worth knowing about, and it is the reason this returns the raw
    mapping rather than a tidied object: YAML 1.1 parses an unquoted `on` as
    the BOOLEAN True, so a workflow's trigger block arrives under the key
    `True` rather than `"on"`. PyYAML's safe_load does exactly this. Callers
    should use `triggers()` instead of indexing `["on"]` and hoping.
    """
    return yaml.safe_load(path.read_text())


def triggers(workflow: dict) -> dict:
    """The `on:` block, whichever key YAML decided to put it under."""
    for key in ("on", True, "true", "On", "ON"):
        if key in workflow:
            block = workflow[key]
            # `on: [push]` and `on: push` are both legal shorthand.
            if isinstance(block, list):
                return {name: None for name in block}
            if isinstance(block, str):
                return {block: None}
            return block or {}
    return {}


def uses_refs(workflow: dict) -> list[tuple[str, str]]:
    """Every `uses:` in the file, as (action, ref) pairs."""
    found: list[tuple[str, str]] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "uses" and isinstance(value, str):
                    match = _USES.match(value.strip())
                    if match:
                        found.append((match["action"], match["ref"]))
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(workflow)
    return found


def run_commands(workflow: dict) -> list[str]:
    """Every `run:` block in the file, as raw strings."""
    found: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "run" and isinstance(value, str):
                    found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(workflow)
    return found


def make_targets(workflow: dict) -> set[str]:
    """Which `make <target>`s this workflow invokes.

    This is what makes the anti-drift property checkable: if `ci.yml` and
    `ct.yml` call the same target, there is one definition of the build.
    """
    targets: set[str] = set()
    for command in run_commands(workflow):
        for match in re.finditer(r"\bmake\s+(?:--?\S+\s+)*([a-z][\w-]*)", command):
            targets.add(match.group(1))
    return targets


def pin_status(action: str, ref: str) -> tuple[str, str]:
    """Classify one pin. Returns (status, detail).

    Outcomes, and only the first three are acceptable in a repository you
    intend to keep:

      sha        a 40-hex commit. Immutable, and the only pin that truly pins —
                 a tag can be moved by whoever owns the action.
      exact      a full `vX.Y.Z`. The right answer when no major tag exists.
      current    a major tag matching the newest major tag we recorded.
      stale      an older major tag than the one we recorded.
      unresolvable  a major tag that DOES NOT EXIST upstream. The build fails
                 before a single step runs, which is at least loud.
      floating   a branch name. Whatever that branch says today runs in your
                 repository, with your token, tomorrow.
    """
    if re.fullmatch(r"[0-9a-f]{40}", ref):
        return "sha", "immutable"

    match = re.fullmatch(r"v(\d+)(?:\.(\d+)\.(\d+))?", ref)
    if not match:
        return "floating", f"`{ref}` is a branch or a moving tag, not a version"

    known = KNOWN_ACTIONS.get(action)
    if known is None:
        return "unknown", "not in the recorded snapshot"

    major = int(match.group(1))
    exact = match.group(2) is not None

    if exact:
        if major < known["release_major"]:
            return "exact", f"pinned to {ref}; newest release is v{known['release_major']}.x"
        return "exact", f"pinned to {ref}, the newest release"

    # A bare major tag. Does it exist?
    if major > known["major_tag"]:
        return (
            "unresolvable",
            f"no `v{major}` tag exists upstream (highest is v{known['major_tag']}); "
            f"pin the exact release instead",
        )
    if major == known["major_tag"]:
        if known["release_major"] > known["major_tag"]:
            return (
                "current",
                f"v{major} is the newest major TAG, but v{known['release_major']} "
                "has been released without one",
            )
        return "current", f"v{major}"
    return "stale", f"v{major} -> v{known['major_tag']} ({known['major_tag'] - major} major(s) behind)"


def audit(paths: list[Path]) -> list[dict]:
    """Every pin across every given workflow, with its status."""
    rows: list[dict] = []
    for path in sorted(paths):
        workflow = load_workflow(path)
        for action, ref in uses_refs(workflow):
            status, detail = pin_status(action, ref)
            rows.append(
                {
                    "file": path.name,
                    "action": action,
                    "ref": ref,
                    "status": status,
                    "detail": detail,
                }
            )
    return rows


def format_audit(rows: list[dict]) -> str:
    """The Exercise 1 table."""
    if not rows:
        return "No workflow files found."

    width = max(len(r["action"]) for r in rows)
    lines = [
        f"Action pins, against a snapshot recorded {KNOWN_LATEST_AS_OF}:",
        "",
        f"  {'file':<22} {'action':<{width}} {'ref':<10} status   detail",
        f"  {'-' * 22} {'-' * width} {'-' * 10} -------- {'-' * 34}",
    ]
    for row in rows:
        lines.append(
            f"  {row['file']:<22} {row['action']:<{width}} {row['ref']:<10} "
            f"{row['status']:<8} {row['detail']}"
        )

    def count(status):
        return [r for r in rows if r["status"] == status]

    lines.append("")
    for status, message in (
        ("unresolvable", "pin(s) name a tag that DOES NOT EXIST — the build fails at setup"),
        ("stale", "pin(s) behind the newest published major tag"),
        ("floating", "pin(s) tracking a branch rather than a version"),
    ):
        hits = count(status)
        if hits:
            lines.append(f"  {len(hits)} {message}.")
    if not (count("unresolvable") or count("stale") or count("floating")):
        lines.append("  Every pin is current, exact or immutable.")
    lines.append("")
    lines.append(
        "  A major tag is a compromise: it moves under you within a major, which\n"
        "  is how you get security fixes without editing anything, and it means\n"
        "  the code you run tomorrow is not the code you reviewed today. A commit\n"
        "  SHA is the honest pin. This course uses major tags and says so."
    )
    return "\n".join(lines)
