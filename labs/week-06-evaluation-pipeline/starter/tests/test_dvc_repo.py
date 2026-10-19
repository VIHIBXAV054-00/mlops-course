"""The DVC files that ship with the lab, checked as files (no `dvc` command, no network)."""

import configparser

import pytest
import yaml

from week_06_evaluation_pipeline.dvc_meta import remote_object_key

pytestmark = pytest.mark.dvc


def test_dvc_dir_and_dvcignore_exist(dvc_repo) -> None:
    assert (dvc_repo / ".dvc" / "config").is_file()
    assert (dvc_repo / ".dvcignore").is_file()


def test_dvc_local_state_is_git_ignored(dvc_repo) -> None:
    """`.dvc/cache`, `.dvc/tmp` and `.dvc/config.local` are git-ignored."""
    import subprocess

    for relative in (".dvc/cache", ".dvc/tmp", ".dvc/config.local"):
        result = subprocess.run(
            ["git", "check-ignore", "-q", relative],
            cwd=dvc_repo,
            capture_output=True,
        )
        assert result.returncode == 0, f"{relative} is NOT git-ignored"


def test_dvc_config_declares_default_storage_remote(dvc_repo, settings) -> None:
    parser = configparser.ConfigParser()
    parser.read(dvc_repo / ".dvc" / "config")
    assert parser["core"]["remote"] == settings.dvc_remote_name
    # DVC writes the header as ['remote "storage"'], so the section name that
    # configparser sees keeps the single quotes.
    section = f"'remote \"{settings.dvc_remote_name}\"'"
    assert parser[section]["url"] == (
        f"s3://{settings.dvc_bucket}/{settings.dvc_remote_path}"
    )
    assert "endpointurl" in parser[section]


def test_dvc_config_contains_no_credentials(dvc_repo) -> None:
    """The committed DVC config contains no credentials."""
    text = (dvc_repo / ".dvc" / "config").read_text()
    assert "access_key_id" not in text
    assert "secret_access_key" not in text


def test_pointer_file_schema(measurements_pointer) -> None:
    """A DVC 3 pointer has exactly four fields — the docs' examples are stale."""
    document = yaml.safe_load(measurements_pointer.read_text())
    assert set(document) == {"outs"}
    out = document["outs"][0]
    assert set(out) == {"md5", "size", "hash", "path"}
    assert out["hash"] == "md5"
    assert len(out["md5"]) == 32
    assert out["path"] == "measurements.csv"


def test_data_gitignore_hides_the_tracked_file(dvc_repo, measurements_pointer) -> None:
    """`data/measurements.csv` is git-ignored, and `data/.gitignore` holds the rule."""
    import subprocess

    assert (dvc_repo / "data" / ".gitignore").is_file(), (
        "dvc add should have written data/.gitignore"
    )
    result = subprocess.run(
        ["git", "check-ignore", "-q", "data/measurements.csv"],
        cwd=dvc_repo,
        capture_output=True,
    )
    assert result.returncode == 0, "data/measurements.csv is not git-ignored"


def test_pointer_md5_matches_the_workspace_file(dvc_repo, measurements_pointer) -> None:
    """If the file is materialised, its bytes must match what the pointer claims."""
    from week_06_evaluation_pipeline.datasets import file_md5

    data_file = dvc_repo / "data" / "measurements.csv"
    if not data_file.exists():
        pytest.skip("measurements.csv absent — build it with `make data-v2`.")
    out = yaml.safe_load(measurements_pointer.read_text())["outs"][0]
    assert file_md5(data_file) == out["md5"]


def test_dvc_lock_dep_matches_pointer_md5(dvc_lock, measurements_pointer) -> None:
    """The md5 of `data/measurements.csv` in `dvc.lock` equals the pointer's md5."""
    lock = yaml.safe_load(dvc_lock.read_text())
    assert lock["schema"] == "2.0"

    pointer_md5 = yaml.safe_load(measurements_pointer.read_text())["outs"][0]["md5"]
    deps = {d["path"]: d for d in lock["stages"]["prepare"]["deps"]}
    assert deps["data/measurements.csv"]["md5"] == pointer_md5


def test_dvc_lock_records_param_values(dvc_lock, params) -> None:
    """The lock stores param VALUES, which is how `repro` knows train is stale."""
    lock = yaml.safe_load(dvc_lock.read_text())
    recorded = lock["stages"]["prepare"]["params"]["params.yaml"]
    assert recorded["random_seed"] == params["random_seed"]
    assert recorded["prepare.test_size"] == params["prepare"]["test_size"]


def test_remote_object_key_splits_the_hash(measurements_pointer) -> None:
    """Objects are addressed by content: files/md5/<2 chars>/<30 chars>."""
    md5 = yaml.safe_load(measurements_pointer.read_text())["outs"][0]["md5"]
    key = remote_object_key(md5)
    assert key == f"files/md5/{md5[:2]}/{md5[2:]}"
    assert len(md5[2:]) == 30
