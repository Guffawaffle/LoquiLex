"""Test configuration parsing and environment variables."""

import os
import pytest  # noqa: F401
from unittest.mock import patch

from loquilex.config.defaults import _env_time_seconds
from loquilex.api.ws_protocol import WSProtocolManager


class TestConfigurationParsing:
    """Test configuration parsing with unit suffixes."""

    def test_time_parsing_with_seconds(self):
        """Test parsing time values with 's' suffix."""
        with patch.dict(os.environ, {"LX_TEST_TIME": "10s"}):
            result = _env_time_seconds("LX_TEST_TIME", 5.0)
            assert result == 10.0

    def test_time_parsing_with_milliseconds(self):
        """Test parsing time values with 'ms' suffix."""
        with patch.dict(os.environ, {"LX_TEST_TIME": "1500ms"}):
            result = _env_time_seconds("LX_TEST_TIME", 5.0)
            assert result == 1.5

    def test_time_parsing_with_minutes(self):
        """Test parsing time values with 'm' suffix."""
        with patch.dict(os.environ, {"LX_TEST_TIME": "2m"}):
            result = _env_time_seconds("LX_TEST_TIME", 5.0)
            assert result == 120.0

    def test_time_parsing_with_hours(self):
        """Test parsing time values with 'h' suffix."""
        with patch.dict(os.environ, {"LX_TEST_TIME": "0.5h"}):
            result = _env_time_seconds("LX_TEST_TIME", 5.0)
            assert result == 1800.0

    def test_time_parsing_plain_number(self):
        """Test parsing plain numbers (assumed to be seconds)."""
        with patch.dict(os.environ, {"LX_TEST_TIME": "7.5"}):
            result = _env_time_seconds("LX_TEST_TIME", 5.0)
            assert result == 7.5

    def test_time_parsing_invalid_value(self):
        """Test parsing invalid values falls back to default."""
        with patch.dict(os.environ, {"LX_TEST_TIME": "invalid"}):
            result = _env_time_seconds("LX_TEST_TIME", 5.0)
            assert result == 5.0

    def test_time_parsing_no_env_var(self):
        """Test parsing when env var doesn't exist."""
        with patch.dict(os.environ, {}, clear=False):
            if "LX_TEST_TIME" in os.environ:
                del os.environ["LX_TEST_TIME"]
            result = _env_time_seconds("LX_TEST_TIME", 5.0)
            assert result == 5.0

    def test_ws_protocol_config_with_time_suffixes(self):
        """Test WSProtocolManager configuration with time suffixes."""
        env_vars = {
            "LX_WS_HEARTBEAT_SEC": "3s",
            "LX_WS_HEARTBEAT_TIMEOUT_SEC": "10s",
            "LX_WS_RESUME_TTL": "5s",
            "LX_WS_RESUME_MAX_EVENTS": "100",
            "LX_CLIENT_EVENT_BUFFER": "150",
        }

        with patch.dict(os.environ, env_vars):
            manager = WSProtocolManager("test_session")

            # Check heartbeat config (converted from seconds to milliseconds)
            assert manager.hb_config.interval_ms == 3000
            assert manager.hb_config.timeout_ms == 10000

            # Check resume window config
            assert manager.resume_window.seconds == 5

            # Check replay buffer config
            assert manager._replay_buffer.maxsize == 100
            assert manager._replay_buffer.ttl_seconds == 5.0

    def test_ws_protocol_config_defaults(self):
        """Test WSProtocolManager uses default values when env vars not set."""
        # Ensure relevant env vars are not set
        env_keys = [
            "LX_WS_HEARTBEAT_SEC",
            "LX_WS_HEARTBEAT_TIMEOUT_SEC",
            "LX_WS_RESUME_TTL",
            "LX_WS_RESUME_MAX_EVENTS",
            "LX_CLIENT_EVENT_BUFFER",
        ]

        env_backup = {}
        for key in env_keys:
            if key in os.environ:
                env_backup[key] = os.environ[key]
                del os.environ[key]

        try:
            manager = WSProtocolManager("test_session")

            # Check defaults match issue requirements
            assert manager.hb_config.interval_ms == 5000  # 5 seconds
            assert manager.hb_config.timeout_ms == 15000  # 15 seconds
            assert manager.resume_window.seconds == 10
            assert manager._replay_buffer.maxsize == 500
        finally:
            # Restore env vars
            for key, value in env_backup.items():
                os.environ[key] = value

    def test_complex_time_formats(self):
        """Test parsing various complex time formats."""
        test_cases = [
            ("10", 10.0),  # Plain number
            ("10s", 10.0),  # Seconds
            ("500ms", 0.5),  # Milliseconds
            ("1.5m", 90.0),  # Minutes with decimal
            ("0.25h", 900.0),  # Hours with decimal
            ("  2s  ", 2.0),  # With whitespace
        ]

        for input_val, expected in test_cases:
            with patch.dict(os.environ, {"LX_TEST_TIME": input_val}):
                result = _env_time_seconds("LX_TEST_TIME", 0.0)
                assert result == expected, f"Failed for input: {input_val}"
