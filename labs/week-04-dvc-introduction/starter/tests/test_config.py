import pytest

from week_04_dvc_introduction.config import Settings, load_settings


def test_settings_defaults() -> None:
    """The Settings dataclass ships with the documented defaults."""
    defaults = Settings()
    assert defaults.random_seed == 42
    assert defaults.test_size == 0.25
    assert defaults.mlflow_experiment_name == "diabetes-week4"
    assert defaults.dvc_bucket == "dvc-storage"
    assert defaults.dvc_remote_name == "storage"
    assert defaults.dvc_remote_path == "dvcstore"


def test_load_settings_returns_valid_settings(settings) -> None:
    """load_settings produces values that pass validation."""
    assert 0.0 < settings.test_size < 1.0
    assert settings.max_iter > 0
    assert settings.data_path.exists()
    assert settings.mlflow_tracking_uri.startswith("http")


def test_params_come_from_params_yaml(settings, params) -> None:
    """Hyperparameters are read from params.yaml, not from the environment."""
    assert settings.random_seed == params["random_seed"]
    assert settings.test_size == params["prepare"]["test_size"]
    assert settings.model_c == params["train"]["C"]
    assert settings.model_family == params["train"]["family"]
    assert settings.max_iter == params["train"]["max_iter"]


def test_pipeline_params_ignore_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Setting PIPELINE_RANDOM_SEED does not change the seed: params.yaml wins."""
    monkeypatch.setenv("PIPELINE_RANDOM_SEED", "999")
    monkeypatch.setenv("PIPELINE_TEST_SIZE", "0.9")
    settings = load_settings()
    assert settings.random_seed == 42
    assert settings.test_size == 0.25


def test_missing_measurements_file_is_not_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing DVC-tracked dataset does not stop the settings from loading."""
    monkeypatch.setenv("PIPELINE_MEASUREMENTS_PATH", "data/does-not-exist.csv")
    settings = load_settings()
    assert not settings.measurements_path.exists()


def test_missing_canonical_dataset_is_still_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing data/diabetes.csv is an error, because it is committed to Git."""
    monkeypatch.setenv("PIPELINE_DATA_PATH", "data/nope.csv")
    with pytest.raises(FileNotFoundError):
        load_settings()


def test_invalid_test_size_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Validation rejects a test_size outside (0, 1)."""
    import shutil

    from week_04_dvc_introduction.config import load_settings as load

    root = tmp_path
    (root / "data").mkdir()
    shutil.copy(
        load().data_path, root / "data" / "diabetes.csv"
    )
    (root / "params.yaml").write_text(
        "random_seed: 42\nprepare:\n  test_size: 1.5\ntrain:\n  C: 1.0\n"
    )
    with pytest.raises(ValueError):
        load(project_root=root)


def test_mlflow_tracking_uri_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment wiring (as opposed to hyperparameters) IS overridable."""
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://custom-server:9999")
    settings = load_settings()
    assert settings.mlflow_tracking_uri == "http://custom-server:9999"
