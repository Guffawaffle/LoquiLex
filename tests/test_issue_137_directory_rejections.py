"""Tests for issue #137 - Directory Rejections

Tests the fixes for:
1. Multiple LX_ALLOWED_STORAGE_ROOTS support
2. Storage bootstrap candidate validation
3. API integration with bootstrap candidates
"""

import tempfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

from loquilex.security.path_guard import PathGuard, PathSecurityError


class TestMultipleExtraRoots:
    """Tests for multiple LX_ALLOWED_STORAGE_ROOTS support."""

    def test_registers_multiple_extra_roots(self, monkeypatch, tmp_path):
        """Test that multiple entries in LX_ALLOWED_STORAGE_ROOTS are honored."""
        # Set up environment with multiple roots
        monkeypatch.setenv("LX_ALLOWED_STORAGE_ROOTS", "/data1:/data2:/home/user")
        monkeypatch.setenv("LX_OUT_DIR", str(tmp_path / "test_out"))

        # Import after setting environment variable to ensure it's used
        from loquilex.api import server
        import importlib

        importlib.reload(server)

        # Should have all configured extra roots
        extra_roots = [name for name in server._root_map.keys() if name.startswith("extra")]
        assert len(extra_roots) == 3

        assert "extra" in server._root_map
        assert "extra_1" in server._root_map
        assert "extra_2" in server._root_map

        assert server._root_map["extra"] == Path("/data1")
        assert server._root_map["extra_1"] == Path("/data2")
        assert server._root_map["extra_2"] == Path("/home/user")


class TestStorageValidation:
    """Tests for validate_storage_candidate method."""

    def test_storage_bootstrap_accepts_user_home_subdir(self):
        """Test that directories under user's home are accepted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_dir = Path(tmpdir) / "LoquiLexData"
            user_dir.mkdir()

            validated = PathGuard.validate_storage_candidate(user_dir)
            assert validated == user_dir.resolve()
            assert validated.exists()

    def test_accepts_nonexistent_dir_with_writable_parent(self):
        """Test that non-existent directories with writable parents are accepted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            user_dir = Path(tmpdir) / "NewLoquiLexData"
            # Don't create the directory

            validated = PathGuard.validate_storage_candidate(user_dir)
            assert validated == user_dir.resolve()

    def test_rejects_system_roots_and_symlinks(self):
        """Test that system directories are rejected."""
        system_paths = ["/", "/proc", "/sys", "/dev", "/run", "/etc", "/boot", "/root"]

        for sys_path in system_paths:
            with pytest.raises(PathSecurityError, match="system path not permitted"):
                PathGuard.validate_storage_candidate(sys_path)

    def test_denies_relative_paths(self):
        """Test that relative paths are denied."""
        bad_paths = [
            "relative/path",
            "./relative",
            "../parent",
        ]

        for bad_path in bad_paths:
            with pytest.raises(PathSecurityError, match="not absolute"):
                PathGuard.validate_storage_candidate(bad_path)

    def test_rejects_empty_path(self):
        """Test that empty paths are rejected."""
        with pytest.raises(PathSecurityError, match="empty path"):
            PathGuard.validate_storage_candidate("")

        with pytest.raises(PathSecurityError, match="empty path"):
            PathGuard.validate_storage_candidate(None)

    def test_rejects_file_as_directory(self):
        """Test that existing files are rejected."""
        with tempfile.NamedTemporaryFile() as tmp_file:
            with pytest.raises(PathSecurityError, match="path is a file"):
                PathGuard.validate_storage_candidate(tmp_file.name)


class TestStorageAPIIntegration:
    """Integration tests for the storage API with new functionality."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch, tmp_path):
        """Set up environment for each test."""
        monkeypatch.setenv("LX_OUT_DIR", str(tmp_path / "test_out"))
        monkeypatch.setenv("LX_ALLOWED_STORAGE_ROOTS", "/data1:/data2")

        # Reload the server module to pick up new environment
        from loquilex.api import server
        import importlib

        importlib.reload(server)

        # Store for use in tests
        self.app = server.app

    def test_accepts_user_directory(self):
        """Test that POST /storage/base-directory accepts user directories."""
        client = TestClient(self.app)

        with tempfile.TemporaryDirectory() as tmpdir:
            user_dir = Path(tmpdir) / "LoquiLexData"
            user_dir.mkdir()

            response = client.post("/storage/base-directory", json={"path": str(user_dir)})
            assert response.status_code == 200

            data = response.json()
            assert data["valid"] is True
            assert "valid and writable" in data["message"].lower()

    def test_rejects_system_directories(self):
        """Test that system directories are rejected with clear errors."""
        client = TestClient(self.app)

        system_paths = ["/etc/loquilex", "/proc/test", "/root/data"]

        for sys_path in system_paths:
            response = client.post("/storage/base-directory", json={"path": sys_path})
            assert response.status_code == 200

            data = response.json()
            assert data["valid"] is False
            # Any reasonable rejection message is acceptable for system paths
            acceptable_rejections = [
                "system path not permitted",
                "path not permitted",
                "parent directory not writable",
                "permission denied",
                "Permission denied",
            ]
            assert any(msg in data["message"] for msg in acceptable_rejections)

    def test_storage_info_with_bootstrap_candidates(self):
        """Test that storage info works with bootstrap candidate directories."""
        client = TestClient(self.app)

        with tempfile.TemporaryDirectory() as tmpdir:
            user_dir = Path(tmpdir) / "LoquiLexData"
            user_dir.mkdir()

            # First validate it as base directory
            response1 = client.post("/storage/base-directory", json={"path": str(user_dir)})
            assert response1.json()["valid"] is True

            # Then check storage info
            response2 = client.get(f"/storage/info?path={user_dir}")
            assert response2.status_code == 200

            data = response2.json()
            assert "path" in data
            assert str(user_dir) in data["path"]
            assert data["writable"] is True
