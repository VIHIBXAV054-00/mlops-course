import pytest

from week_01_env_setup.config import load_settings
from week_01_env_setup.data import build_dataset, load_dataframe


def test_split_ratios() -> None:
    """Verify the train/test split.

    TODO(student) — Exercise 3:
    1. Load settings with `load_settings()`.
    2. Load the full dataset with `load_dataframe(settings)`.
    3. Build the split with `build_dataset(settings)`.
    4. Assert that train rows + test rows == total rows.
    5. Assert that the test fraction is approximately `settings.test_size`
       (hint: `pytest.approx(..., abs=0.01)`).
    6. Delete the `@pytest.mark.skip` line above and re-run pytest.
    """
    settings = load_settings()
    frame = load_dataframe(settings)
    x_train, x_test, y_train, y_test = build_dataset(settings)

    total_rows = len(frame)
    train_rows = len(x_train)
    test_rows = len(x_test)
    assert train_rows + test_rows == total_rows
    assert len(y_train) + len(y_test) == total_rows

    test_fraction = test_rows / total_rows
    assert test_fraction == pytest.approx(settings.test_size, abs=0.01)
