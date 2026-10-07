"""Read a DVC pointer file without running DVC. You do not need to change this module.

A `.dvc` file is YAML with four fields:

    outs:
    - md5: a8fd7b4f0d6d1bc4e378a8f76c5fff0c
      size: 31750
      hash: md5
      path: measurements.csv
"""

from __future__ import annotations

from pathlib import Path

import yaml


def pointer_path(data_path: Path) -> Path:
    """`data/measurements.csv` -> `data/measurements.csv.dvc`."""
    return Path(str(data_path) + ".dvc")


def read_pointer(data_path: Path) -> dict:
    """Return the single `outs` entry from a `.dvc` file."""
    path = pointer_path(data_path)
    if not path.exists():
        raise FileNotFoundError(
            f"No DVC pointer at {path.name}. Run `dvc add data/measurements.csv` first."
        )
    document = yaml.safe_load(path.read_text()) or {}
    outs = document.get("outs") or []
    if not outs:
        raise ValueError(f"{path} has no `outs` entry — is it a valid .dvc file?")
    return outs[0]


def pointer_md5(data_path: Path) -> str:
    """The content hash of the tracked data, straight from the pointer."""
    return str(read_pointer(data_path)["md5"])


def remote_object_key(md5: str) -> str:
    """Where DVC stores an object, relative to the remote root: files/md5/a8/fd7b...."""
    return f"files/md5/{md5[:2]}/{md5[2:]}"


def remote_object_uri(settings, md5: str) -> str:
    """The full s3:// URI of the tracked object in the Silo remote."""
    return (
        f"s3://{settings.dvc_bucket}/{settings.dvc_remote_path}/"
        f"{remote_object_key(md5)}"
    )
