import pytest

from week_03_mlflow_integration.config import Settings, load_settings


def test_settings_defaults() -> None:
    """The Settings dataclass ships with the documented defaults."""
    settings = Settings()
    assert settings.random_seed == 42
    assert settings.test_size == 0.25
    assert settings.max_iter == 1000
    assert settings.mlflow_tracking_uri == "http://127.0.0.1:5500"
    assert settings.mlflow_experiment_name == "diabetes-week3"
    assert settings.registered_model_name == "diabetes-classifier"
    assert settings.model_alias == "staging"


def test_load_settings_returns_valid_settings() -> None:
    """load_settings produces values that pass validation, whatever .env says."""
    settings = load_settings()
    assert 0.0 < settings.test_size < 1.0
    assert settings.max_iter > 0
    assert settings.data_path.exists()
    assert settings.mlflow_tracking_uri.startswith("http")
    assert len(settings.mlflow_experiment_name) > 0
    assert len(settings.registered_model_name) > 0


def test_invalid_test_size_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validation rejects a test_size outside (0, 1)."""
    monkeypatch.setenv("PIPELINE_TEST_SIZE", "1.5")
    with pytest.raises(ValueError):
        load_settings()


def test_mlflow_tracking_uri_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    """MLFLOW_TRACKING_URI env var is respected."""
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://custom-server:9999")
    settings = load_settings()
    assert settings.mlflow_tracking_uri == "http://custom-server:9999"


def test_mlflow_experiment_name_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    """MLFLOW_EXPERIMENT_NAME env var is respected."""
    monkeypatch.setenv("MLFLOW_EXPERIMENT_NAME", "my-experiment")
    settings = load_settings()
    assert settings.mlflow_experiment_name == "my-experiment"


def test_registered_model_name_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    """MLFLOW_REGISTERED_MODEL_NAME env var is respected (new in Week 3)."""
    monkeypatch.setenv("MLFLOW_REGISTERED_MODEL_NAME", "my-model")
    settings = load_settings()
    assert settings.registered_model_name == "my-model"


def test_empty_registered_model_name_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validation fails fast on an empty registered-model name (new in Week 3)."""
    monkeypatch.setenv("MLFLOW_REGISTERED_MODEL_NAME", "")
    with pytest.raises(ValueError):
        load_settings()
