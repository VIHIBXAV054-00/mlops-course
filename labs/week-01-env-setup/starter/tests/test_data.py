import pytest

from week_01_env_setup.config import load_settings
from week_01_env_setup.data import build_dataset, load_dataframe


def test_split_ratios() -> None:
   """Verify the train/test split preserves the configured test fraction."""
   settings = load_settings()
   frame = load_dataframe(settings)
   x_train, x_test, _, _ = build_dataset(settings)

   assert len(x_train) + len(x_test) == len(frame)
   assert len(x_test) / len(frame) == pytest.approx(settings.test_size, abs=0.01)
