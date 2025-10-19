"""Tests for path_policy module focusing on filesystem policy enforcement."""

import tempfile
from pathlib import Path

import pytest

from loquilex.security.path_policy import PathPolicy, PathPolicyConfig
from loquilex.security.path_sanitizer import PathInputError, PathSecurityError


class TestPathPolicyConfig:
    """Test PathPolicyConfig dataclass."""

    def test_empty_config(self):
        """Test empty configuration."""
        config = PathPolicyConfig()
        assert config.allowed_roots == ()

    def test_config_with_roots(self):
        """Test configuration with allowed roots."""
        root1 = Path("/tmp/root1").resolve()
        root2 = Path("/tmp/root2").resolve()
        config = PathPolicyConfig(allowed_roots=(root1, root2))
        assert config.allowed_roots == (root1, root2)

    def test_config_immutable(self):
        """Test that config is immutable (frozen dataclass)."""
        config = PathPolicyConfig()
        with pytest.raises(AttributeError):
            config.allowed_roots = (Path("/new"),)


class TestPathPolicy:
    """Test PathPolicy class."""

    @pytest.fixture
    def temp_roots(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test root directories
            root1 = temp_path / "root1"
            root2 = temp_path / "root2"
            outside = temp_path / "outside"

            root1.mkdir()
            root2.mkdir()
            outside.mkdir()

            # Create some test files and subdirectories
            (root1 / "file1.txt").write_text("test1")
            (root1 / "subdir").mkdir()
            (root1 / "subdir" / "file2.txt").write_text("test2")

            (root2 / "data.json").write_text('{"test": true}')

            (outside / "forbidden.txt").write_text("not allowed")

            yield {"root1": root1, "root2": root2, "outside": outside, "temp": temp_path}

    def test_policy_initialization(self, temp_roots):
        """Test PathPolicy initialization."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"], temp_roots["root2"]))
        policy = PathPolicy(config)
        assert policy.config == config

    def test_policy_rejects_relative_roots(self):
        """Test that policy rejects relative paths as allowed roots."""
        relative_root = Path("relative/path")
        config = PathPolicyConfig(allowed_roots=(relative_root,))

        with pytest.raises(ValueError, match="allowed root must be absolute"):
            PathPolicy(config)

    def test_resolve_under_basic_cases(self, temp_roots):
        """Test basic path resolution under allowed roots."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"], temp_roots["root2"]))
        policy = PathPolicy(config)

        # Test resolving under root1
        resolved = policy.resolve_under(temp_roots["root1"], "file1.txt")
        assert resolved == temp_roots["root1"] / "file1.txt"
        assert resolved.exists()

        # Test resolving under root2
        resolved = policy.resolve_under(temp_roots["root2"], "data.json")
        assert resolved == temp_roots["root2"] / "data.json"
        assert resolved.exists()

        # Test subdirectory resolution
        resolved = policy.resolve_under(temp_roots["root1"], "subdir/file2.txt")
        assert resolved == temp_roots["root1"] / "subdir" / "file2.txt"
        assert resolved.exists()

    def test_resolve_under_with_string_root(self, temp_roots):
        """Test path resolution with string root path."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        # Pass root as string
        resolved = policy.resolve_under(str(temp_roots["root1"]), "file1.txt")
        assert resolved == temp_roots["root1"] / "file1.txt"

    def test_resolve_under_empty_path(self, temp_roots):
        """Test resolving empty path (should return root itself)."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        # Empty path components should resolve to root
        resolved = policy.resolve_under(temp_roots["root1"], "")
        assert resolved == temp_roots["root1"]

    def test_resolve_under_rejects_disallowed_root(self, temp_roots):
        """Test that resolution rejects disallowed roots."""
        # Only allow root1
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        # Try to resolve under root2 (not allowed)
        with pytest.raises(PathSecurityError, match="root not in allowed roots"):
            policy.resolve_under(temp_roots["root2"], "data.json")

        # Try to resolve under outside directory
        with pytest.raises(PathSecurityError, match="root not in allowed roots"):
            policy.resolve_under(temp_roots["outside"], "forbidden.txt")

    def test_resolve_under_rejects_relative_root(self, temp_roots):
        """Test that resolution rejects relative root paths."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        with pytest.raises(PathSecurityError, match="root must be absolute"):
            policy.resolve_under("relative/path", "file.txt")

    def test_resolve_under_path_sanitization(self, temp_roots):
        """Test that resolve_under properly sanitizes user paths."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        # Test path traversal rejection
        with pytest.raises(PathSecurityError, match="path traversal not permitted"):
            policy.resolve_under(temp_roots["root1"], "../outside/forbidden.txt")

        # Test absolute path rejection
        with pytest.raises(PathSecurityError, match="absolute paths are not permitted"):
            policy.resolve_under(temp_roots["root1"], "/etc/passwd")

        # Test control character rejection
        with pytest.raises(PathInputError, match="NUL byte"):
            policy.resolve_under(temp_roots["root1"], "file\x00name.txt")

    def test_resolve_under_separator_normalization(self, temp_roots):
        """Test that path separators are properly normalized."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        # Test mixed separators
        resolved = policy.resolve_under(temp_roots["root1"], "subdir\\file2.txt")
        assert resolved == temp_roots["root1"] / "subdir" / "file2.txt"

        # Test collapsed separators
        resolved = policy.resolve_under(temp_roots["root1"], "subdir//file2.txt")
        assert resolved == temp_roots["root1"] / "subdir" / "file2.txt"

    def test_containment_verification(self, temp_roots):
        """Test that resolved paths are verified to be within allowed roots."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        # This should work - file is within root1
        resolved = policy.resolve_under(temp_roots["root1"], "file1.txt")
        assert resolved.exists()

        # Manually test containment verification
        policy._verify_containment(resolved)  # Should not raise

        # Test containment failure
        outside_path = temp_roots["outside"] / "forbidden.txt"
        with pytest.raises(PathSecurityError, match="path outside allowed roots"):
            policy._verify_containment(outside_path)

    def test_containment_with_relative_path(self, temp_roots):
        """Test containment verification rejects relative paths."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        with pytest.raises(PathSecurityError, match="path must be absolute"):
            policy._verify_containment(Path("relative/path"))

    def test_ensure_dir(self, temp_roots):
        """Test directory creation."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        # Create a new directory
        new_dir = temp_roots["root1"] / "new_subdir"
        assert not new_dir.exists()

        policy.ensure_dir(new_dir)
        assert new_dir.exists()
        assert new_dir.is_dir()

        # Test that it handles existing directories
        policy.ensure_dir(new_dir)  # Should not raise
        assert new_dir.exists()

    def test_ensure_dir_with_parents(self, temp_roots):
        """Test directory creation with parent directories."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        # Create nested directories
        nested_dir = temp_roots["root1"] / "level1" / "level2" / "level3"
        assert not nested_dir.exists()

        policy.ensure_dir(nested_dir)
        assert nested_dir.exists()
        assert nested_dir.is_dir()
        assert (temp_roots["root1"] / "level1").exists()
        assert (temp_roots["root1"] / "level1" / "level2").exists()

    def test_ensure_dir_rejects_outside_paths(self, temp_roots):
        """Test that ensure_dir rejects paths outside allowed roots."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        # Try to create directory outside allowed root
        outside_dir = temp_roots["outside"] / "new_dir"
        with pytest.raises(PathSecurityError, match="path outside allowed roots"):
            policy.ensure_dir(outside_dir)

    def test_ensure_dir_with_custom_mode(self, temp_roots):
        """Test directory creation with custom permissions."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        # Create directory with custom mode
        custom_dir = temp_roots["root1"] / "custom_mode_dir"
        policy.ensure_dir(custom_dir, mode=0o755)

        assert custom_dir.exists()
        # Note: actual mode checking is platform-dependent and affected by umask
        # so we just verify the directory was created

    def test_open_read_nofollow_basic(self, temp_roots):
        """Test basic file opening for reading."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        file_path = temp_roots["root1"] / "file1.txt"

        with policy.open_read_nofollow(file_path) as f:
            content = f.read()
            assert content == b"test1"

    def test_open_read_nofollow_rejects_outside_paths(self, temp_roots):
        """Test that open_read_nofollow rejects paths outside allowed roots."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        outside_file = temp_roots["outside"] / "forbidden.txt"
        with pytest.raises(PathSecurityError, match="path outside allowed roots"):
            policy.open_read_nofollow(outside_file)

    def test_open_write_atomic_basic(self, temp_roots):
        """Test basic file opening for writing."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        new_file = temp_roots["root1"] / "new_file.txt"

        with policy.open_write_atomic(new_file) as f:
            f.write(b"new content")

        # Verify file was written
        assert new_file.exists()
        assert new_file.read_bytes() == b"new content"

    def test_open_write_atomic_rejects_outside_paths(self, temp_roots):
        """Test that open_write_atomic rejects paths outside allowed roots."""
        config = PathPolicyConfig(allowed_roots=(temp_roots["root1"],))
        policy = PathPolicy(config)

        outside_file = temp_roots["outside"] / "new_file.txt"
        with pytest.raises(PathSecurityError, match="path outside allowed roots"):
            policy.open_write_atomic(outside_file)


class TestIntegrationWithSanitizer:
    """Test integration between PathPolicy and path_sanitizer."""

    @pytest.fixture
    def policy_with_temp_root(self):
        """Create a policy with a temporary root for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "test_root"
            root.mkdir()

            config = PathPolicyConfig(allowed_roots=(root,))
            policy = PathPolicy(config)

            yield policy, root

    def test_sanitizer_integration(self, policy_with_temp_root):
        """Test that PathPolicy properly integrates with sanitizer functions."""
        policy, root = policy_with_temp_root

        # Test normal path
        resolved = policy.resolve_under(root, "normal/file.txt")
        expected = root / "normal" / "file.txt"
        assert resolved == expected

        # Test path that requires sanitization
        resolved = policy.resolve_under(root, "mixed\\\\separators//file.txt")
        expected = root / "mixed" / "separators" / "file.txt"
        assert resolved == expected

    def test_error_propagation(self, policy_with_temp_root):
        """Test that sanitizer errors are properly propagated."""
        policy, root = policy_with_temp_root

        # PathInputError should propagate
        with pytest.raises(PathInputError):
            policy.resolve_under(root, "file\x00name.txt")

        # PathSecurityError should propagate
        with pytest.raises(PathSecurityError):
            policy.resolve_under(root, "../traversal")

    def test_component_validation_integration(self, policy_with_temp_root):
        """Test that component validation works through the policy."""
        policy, root = policy_with_temp_root

        # Test reserved name rejection
        with pytest.raises(PathInputError, match="invalid path component"):
            policy.resolve_under(root, "dir/CON.txt")

        # Test hidden file rejection (default)
        with pytest.raises(PathInputError, match="invalid path component"):
            policy.resolve_under(root, "dir/.hidden")


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_empty_allowed_roots(self):
        """Test policy with no allowed roots."""
        config = PathPolicyConfig(allowed_roots=())
        policy = PathPolicy(config)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            # Should fail since no roots are allowed
            with pytest.raises(PathSecurityError, match="root not in allowed roots"):
                policy.resolve_under(root, "file.txt")

    def test_nested_allowed_roots(self):
        """Test with nested allowed roots."""
        with tempfile.TemporaryDirectory() as temp_dir:
            parent = Path(temp_dir) / "parent"
            child = parent / "child"

            parent.mkdir()
            child.mkdir()

            # Allow both parent and child
            config = PathPolicyConfig(allowed_roots=(parent, child))
            policy = PathPolicy(config)

            # Should work for both
            resolved1 = policy.resolve_under(parent, "file.txt")
            assert resolved1 == parent / "file.txt"

            resolved2 = policy.resolve_under(child, "file.txt")
            assert resolved2 == child / "file.txt"
