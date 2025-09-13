"""
Tests for scripts.env helper functions.
"""

from __future__ import annotations

import warnings


from scripts.env import getenv, getenv_bool, is_truthy


class TestIsTruthy:
    """Test is_truthy function behavior."""

    def test_none_returns_false(self):
        assert is_truthy(None) is False

    def test_empty_string_returns_false(self):
        assert is_truthy("") is False

    def test_whitespace_only_returns_false(self):
        assert is_truthy("   ") is False

    def test_true_values(self):
        true_values = ["1", "true", "yes", "on", "TRUE", "Yes", "ON", " 1 ", " TRUE "]
        for val in true_values:
            assert is_truthy(val) is True, f"Expected {val!r} to be truthy"

    def test_false_values(self):
        false_values = ["0", "false", "no", "off", "FALSE", "No", "OFF", "random", "2"]
        for val in false_values:
            assert is_truthy(val) is False, f"Expected {val!r} to be falsy"


class TestGetenv:
    """Test getenv function behavior."""

    def test_primary_env_var_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("LX_FOO", "primary")
        monkeypatch.setenv("GF_FOO", "legacy")

        result = getenv("LX_FOO", "default", aliases=("GF_FOO",))
        assert result == "primary"

    def test_legacy_env_var_used_when_primary_missing(self, monkeypatch):
        # Clear warning state
        import scripts.env

        scripts.env._warned.clear()

        monkeypatch.delenv("LX_FOO", raising=False)
        monkeypatch.setenv("GF_FOO", "legacy")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", DeprecationWarning)
            result = getenv("LX_FOO", "default", aliases=("GF_FOO",))

        assert result == "legacy"
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
        assert "GF_FOO" in str(w[0].message)

    def test_default_used_when_no_env_vars(self, monkeypatch):
        monkeypatch.delenv("LX_FOO", raising=False)
        monkeypatch.delenv("GF_FOO", raising=False)

        result = getenv("LX_FOO", "default", aliases=("GF_FOO",))
        assert result == "default"

    def test_none_default(self, monkeypatch):
        monkeypatch.delenv("LX_FOO", raising=False)

        result = getenv("LX_FOO")
        assert result is None

    def test_first_alias_wins(self, monkeypatch):
        # Clear warning state
        import scripts.env

        scripts.env._warned.clear()

        monkeypatch.delenv("LX_FOO", raising=False)
        monkeypatch.setenv("GF_FOO", "first")
        monkeypatch.setenv("OLD_FOO", "second")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", DeprecationWarning)
            result = getenv("LX_FOO", "default", aliases=("GF_FOO", "OLD_FOO"))

        assert result == "first"
        assert len(w) == 1
        assert "GF_FOO" in str(w[0].message)

    def test_deprecation_warning_only_once(self, monkeypatch):
        # Clear warning state
        import scripts.env

        scripts.env._warned.clear()

        monkeypatch.delenv("LX_FOO", raising=False)
        monkeypatch.setenv("GF_FOO", "legacy")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", DeprecationWarning)
            getenv("LX_FOO", "default", aliases=("GF_FOO",))
            getenv("LX_FOO", "default", aliases=("GF_FOO",))  # Second call

        # Should only warn once per variable
        deprecation_warnings = [
            warning for warning in w if issubclass(warning.category, DeprecationWarning)
        ]
        assert len(deprecation_warnings) == 1


class TestGetenvBool:
    """Test getenv_bool function behavior."""

    def test_true_values(self, monkeypatch):
        for val in ["1", "true", "yes", "on", "TRUE"]:
            monkeypatch.setenv("LX_BOOL", val)
            assert getenv_bool("LX_BOOL") is True

    def test_false_values(self, monkeypatch):
        for val in ["0", "false", "no", "off", "FALSE", "random"]:
            monkeypatch.setenv("LX_BOOL", val)
            assert getenv_bool("LX_BOOL") is False

    def test_default_false(self, monkeypatch):
        monkeypatch.delenv("LX_BOOL", raising=False)
        assert getenv_bool("LX_BOOL") is False

    def test_custom_default(self, monkeypatch):
        monkeypatch.delenv("LX_BOOL", raising=False)
        assert getenv_bool("LX_BOOL", default=True) is True

    def test_legacy_alias_support(self, monkeypatch):
        # Clear warning state
        import scripts.env

        scripts.env._warned.clear()

        monkeypatch.delenv("LX_BOOL", raising=False)
        monkeypatch.setenv("GF_BOOL", "1")

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always", DeprecationWarning)
            result = getenv_bool("LX_BOOL", aliases=("GF_BOOL",))

        assert result is True
        assert len(w) == 1
        assert "GF_BOOL" in str(w[0].message)
