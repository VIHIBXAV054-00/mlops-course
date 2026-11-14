"""The state DVC creates (Exercises 1, 2, 5).

Pure file inspection — no `dvc` subprocess, no network — so these are fast and
work offline. Every test is guarded by a fixture that skips when the student has
not reached the relevant exercise yet.
"""

import configparser

import pytest
import yaml

from week_08_prefect_flow.dvc_meta import remote_object_key

pytestmark = [pytest.mark.data, pytest.mark.dvc]


def test_dvc_dir_and_dvcignore_exist(dvc_repo) -> None:
    assert (dvc_repo / ".dvc" / "config").is_file()
    assert (dvc_repo / ".dvcignore").is_file()


def test_dvc_local_state_is_git_ignored(dvc_repo) -> None:
    """The cache, tmp and config.local must never reach Git.

    Asserted as behaviour (`git check-ignore`) rather than by reading
    .dvc/.gitignore literally, because DVC omits an entry it can see is already
    covered by an ancestor .gitignore — and this repository's root .gitignore
    covers `**/.dvc/config.local`. Either way the file is ignored, which is the
    property that actually matters.
    """
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
    """The committed config must never carry keys.

    Credentials belong in the environment or in .dvc/config.local, which DVC
    git-ignores. This is the assertion form of that rule; the student bundle's
    leak scan enforces the same thing at publish time.
    """
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
    """The tracked data file must be git-ignored, and `dvc add` is what did it.

    Asserting the BEHAVIOUR rather than the literal contents of
    `data/.gitignore`, for the same reason as the test above: DVC omits an entry
    it can see an ancestor .gitignore already covers, so the rule may legitimately
    live somewhere else. What must be true either way is that Git will not stage
    the data — and that `dvc add` wrote its ignore file in the DATA directory
    rather than at the repo root, which is the detail worth remembering.
    """
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
    from week_08_prefect_flow.datasets import file_md5

    data_file = dvc_repo / "data" / "measurements.csv"
    if not data_file.exists():
        pytest.skip("measurements.csv not materialised — run `make dvc-pull`.")
    out = yaml.safe_load(measurements_pointer.read_text())["outs"][0]
    assert file_md5(data_file) == out["md5"]


def test_dvc_lock_dep_matches_pointer_md5(dvc_lock, measurements_pointer) -> None:
    """The join point of the whole week, guarded.

    dvc.lock records what `prepare` actually consumed. That md5 must be the same
    one the .dvc pointer publishes — otherwise the pipeline and the data version
    are telling different stories.
    """
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
