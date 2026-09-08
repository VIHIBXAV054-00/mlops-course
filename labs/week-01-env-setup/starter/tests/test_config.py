import pytest

from week_01_env_setup.config import Settings, load_settings


def test_settings_defaults() -> None:
    """The Settings dataclass ships with the documented defaults."""
    settings = Settings()
    assert settings.random_seed == 42
    assert settings.test_size == 0.25
    assert settings.max_iter == 1000


def test_load_settings_returns_valid_settings() -> None:
    """load_settings produces values that pass validation, whatever .env says."""
    settings = load_settings()
    assert 0.0 < settings.test_size < 1.0
    assert settings.max_iter > 0
    assert settings.data_path.exists()


def test_invalid_test_size_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Validation rejects a test_size outside (0, 1)."""
    monkeypatch.setenv("PIPELINE_TEST_SIZE", "1.5")
    with pytest.raises(ValueError):
        load_settings()
