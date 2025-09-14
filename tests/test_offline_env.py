import os
import pytest


@pytest.mark.parametrize(
    "env_var",
    [
        "HF_HUB_OFFLINE",
        "TRANSFORMERS_OFFLINE",
        "HF_HUB_DISABLE_TELEMETRY",
        "LOQUILEX_OFFLINE",
    ],
)
def test_offline_env_vars_set(env_var):
    """Ensure required offline environment variables are set."""
    if env_var not in os.environ:
        pytest.fail(f"Environment variable {env_var} is not set.")
