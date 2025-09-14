"""Test network isolation and offline behavior in tests."""

from __future__ import annotations

import os
import socket
import pytest

pytestmark = pytest.mark.usefixtures("forbid_network")

# Note: ::1 (IPv6 localhost) is allowed alongside 127.0.0.1 for macOS/Linux loopback compatibility


def test_offline_network_guard_blocks_external():
    """Test that the network guard blocks outbound connections to non-local hosts."""
    # This should be blocked by the forbid_network fixture
    with pytest.raises(RuntimeError, match="Blocked outbound connection to"):
        socket.create_connection(("example.com", 80), timeout=1)

    with pytest.raises(RuntimeError, match="Blocked outbound connection to"):
        socket.create_connection(("8.8.8.8", 53), timeout=1)


def test_offline_network_guard_allows_localhost():
    """Test that the network guard allows localhost connections."""
    # These should be allowed
    allowed_hosts = ["127.0.0.1", "::1", "localhost"]

    for host in allowed_hosts:
        try:
            # Try to connect - this will likely fail due to no server listening,
            # but it should NOT fail with our "Blocked outbound connection" error
            socket.create_connection((host, 12345), timeout=0.1)
        except socket.error:
            # Expected - no server listening on that port
            pass
        except RuntimeError as e:
            if "Blocked outbound connection" in str(e):
                pytest.fail(
                    f"Network guard incorrectly blocked localhost connection to {host}: {e}"
                )
            # Some other RuntimeError is unexpected but not our concern
            pass


def test_offline_env_vars_set():
    """Test that offline environment variables are properly set."""

    expected_offline_vars = {
        "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1",
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "LX_OFFLINE": "1",
    }

    # Only run this test if LX_OFFLINE is '1'
    if os.environ.get("LX_OFFLINE") != "1":
        pytest.skip("LX_OFFLINE is not '1'; skipping offline env var test.")
    for var, expected_value in expected_offline_vars.items():
        assert os.environ.get(var) == expected_value, f"Expected {var}={expected_value}"
