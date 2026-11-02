"""Read a DVC pointer file without needing DVC installed or a remote reachable.

New in Week 4. A `.dvc` file is just YAML, and reading it is the whole idea of
content-addressed data versioning made concrete:

    outs:
    - md5: 786c54f2770fa1e7ea5438e6e44b6486
      size: 19034
      hash: md5
      path: measurements.csv

Four fields. That is what Git stores in place of the data. The `md5` is the
plain md5 of the file's bytes, and it is also the object's address in the
remote: `<remote>/files/md5/78/6c54f2770fa1e7ea5438e6e44b6486`.

(The official docs' examples of this file are stale — they predate DVC 3.0 and
omit `hash:` and `size:`. Trust the file on your disk, not the docs.)
"""

from __future__ import annotations

from pathlib import Path

import yaml


def pointer_path(data_path: Path) -> Path:
    """`data/measurements.csv` -> `data/measurements.csv.dvc`."""
    return Path(str(data_path) + ".dvc")


def read_pointer(data_path: Path) -> dict:
    """Return the single `outs` entry from a `.dvc` file.

    Raises FileNotFoundError with an actionable message if the pointer is
    absent, which is the normal state before Exercise 2.
    """
    path = pointer_path(data_path)
    if not path.exists():
        raise FileNotFoundError(
            f"No DVC pointer at {path.name}. "
            "Run `dvc add data/measurements.csv` first (Exercise 2)."
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
