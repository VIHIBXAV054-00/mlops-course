"""Read a DVC pointer (.dvc) file as YAML, without DVC or a remote."""

from __future__ import annotations

from pathlib import Path

import yaml


def pointer_path(data_path: Path) -> Path:
    """`data/measurements.csv` -> `data/measurements.csv.dvc`."""
    return Path(str(data_path) + ".dvc")


def read_pointer(data_path: Path) -> dict:
    """Return the single `outs` entry from a `.dvc` file.

    Raises FileNotFoundError if the pointer is missing.
    """
    path = pointer_path(data_path)
    if not path.exists():
        raise FileNotFoundError(
            f"No DVC pointer at {path.name}. "
            "Run `make dvc-pull` or `dvc add data/measurements.csv` first."
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
    """Where DVC stores an object, relative to the remote root.

    DVC splits the hash after two characters so no single directory ends up with
    millions of entries: `files/md5/78/6c54f2770fa1e7ea5438e6e44b6486`.
    """
    return f"files/md5/{md5[:2]}/{md5[2:]}"


def remote_object_uri(settings, md5: str) -> str:
    """The full s3:// URI of the tracked object in the Silo remote."""
    return (
        f"s3://{settings.dvc_bucket}/{settings.dvc_remote_path}/"
        f"{remote_object_key(md5)}"
    )
