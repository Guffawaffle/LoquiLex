"""Tests for path_sanitizer module with comprehensive edge case coverage."""

import pytest
import unicodedata

from loquilex.security.path_sanitizer import (
    PathInputError,
    PathSecurityError,
    normalize_filename,
    sanitize_path_string,
    split_and_validate_components,
)


class TestNormalizeFilename:
    """Test normalize_filename function."""

    def test_basic_valid_filenames(self):
        """Test basic valid filename cases."""
        assert normalize_filename("file.txt") == "file.txt"
        assert normalize_filename("document") == "document"
        assert normalize_filename("my-file_2.json") == "my-file_2.json"
        assert normalize_filename("IMG_001.JPG") == "IMG_001.JPG"

    def test_unicode_nfc_normalization(self):
        """Test Unicode NFC normalization."""
        # é as composed vs decomposed
        composed = "café.txt"  # é = U+00E9
        decomposed = "cafe\u0301.txt"  # e + ́ = U+0065 + U+0301

        result_composed = normalize_filename(composed)
        result_decomposed = normalize_filename(decomposed)

        # Both should normalize to the same NFC form
        assert result_composed == result_decomposed
        assert unicodedata.is_normalized("NFC", result_composed)

    def test_control_character_stripping(self):
        """Test removal of C0 control characters and DEL."""
        # Test various control characters
        assert normalize_filename("file\x00name.txt") == "filename.txt"  # NUL
        assert normalize_filename("file\x01name.txt") == "filename.txt"  # SOH
        assert normalize_filename("name\x1F.txt") == "name.txt"  # Unit separator
        assert normalize_filename("file\x7Fname.txt") == "filename.txt"  # DEL
        assert normalize_filename("\x08file\x09name\x0A.txt") == "filename.txt"  # BS, TAB, LF

    def test_trailing_space_dot_stripping(self):
        """Test trailing space and dot removal (Windows compatibility)."""
        assert normalize_filename("file.txt   ") == "file.txt"
        assert normalize_filename("file.txt...") == "file.txt"
        assert normalize_filename("file.txt . . ") == "file.txt"
        assert normalize_filename("document  .  .  ") == "document"

    def test_path_separator_rejection(self):
        """Test rejection of path separators in filenames."""
        with pytest.raises(PathInputError, match="path separators"):
            normalize_filename("file/name.txt")
        with pytest.raises(PathInputError, match="path separators"):
            normalize_filename("file\\name.txt")
        with pytest.raises(PathInputError, match="path separators"):
            normalize_filename("path/to/file.txt")

    def test_hidden_file_policy(self):
        """Test hidden file handling."""
        # Default: hidden files not allowed
        with pytest.raises(PathInputError, match="hidden files not allowed"):
            normalize_filename(".hidden")
        with pytest.raises(PathInputError, match="hidden files not allowed"):
            normalize_filename(".config.json")

        # Allow hidden files
        assert normalize_filename(".hidden", allow_hidden=True) == ".hidden"
        assert normalize_filename(".vscode", allow_hidden=True) == ".vscode"

    def test_reserved_windows_names(self):
        """Test Windows reserved device name rejection."""
        reserved_names = [
            "CON",
            "PRN",
            "AUX",
            "NUL",
            "COM1",
            "COM2",
            "COM9",
            "LPT1",
            "LPT2",
            "LPT9",
        ]

        for name in reserved_names:
            # Test uppercase
            with pytest.raises(PathInputError, match="reserved filename"):
                normalize_filename(name)
            # Test lowercase
            with pytest.raises(PathInputError, match="reserved filename"):
                normalize_filename(name.lower())
            # Test with extension
            with pytest.raises(PathInputError, match="reserved filename"):
                normalize_filename(f"{name}.txt")

        # Allow reserved names when disabled
        assert normalize_filename("CON", forbid_reserved=False) == "CON"
        assert normalize_filename("con.txt", forbid_reserved=False) == "con.txt"

    def test_length_constraints(self):
        """Test filename length limits."""
        # Default max length 255
        long_name = "a" * 255
        assert normalize_filename(long_name) == long_name

        too_long = "a" * 256
        with pytest.raises(PathInputError, match="filename too long"):
            normalize_filename(too_long)

        # Custom max length
        assert normalize_filename("short", max_length=10) == "short"
        with pytest.raises(PathInputError, match="filename too long"):
            normalize_filename("toolongname", max_length=5)

    def test_empty_and_invalid_inputs(self):
        """Test empty and invalid input handling."""
        with pytest.raises(PathInputError, match="filename cannot be empty"):
            normalize_filename("")

        with pytest.raises(PathInputError, match="filename must be a string"):
            normalize_filename(None)  # type: ignore

        with pytest.raises(PathInputError, match="filename must be a string"):
            normalize_filename(123)  # type: ignore

        # Empty after normalization
        with pytest.raises(PathInputError, match="empty after normalization"):
            normalize_filename("   ...")


class TestSanitizePathString:
    """Test sanitize_path_string function."""

    def test_basic_relative_paths(self):
        """Test basic relative path sanitization."""
        assert sanitize_path_string("file.txt") == "file.txt"
        assert sanitize_path_string("dir/file.txt") == "dir/file.txt"
        assert sanitize_path_string("path/to/file.json") == "path/to/file.json"

    def test_unicode_nfc_normalization(self):
        """Test path-level Unicode normalization."""
        decomposed = "café/résumé.txt"  # With decomposed characters
        result = sanitize_path_string(decomposed)
        assert unicodedata.is_normalized("NFC", result)

    def test_control_character_rejection(self):
        """Test strict control character rejection for paths."""
        # Unlike filenames, paths should error on control chars (no silent removal)
        with pytest.raises(PathInputError, match="NUL byte"):
            sanitize_path_string("file\x00name.txt")

        with pytest.raises(PathInputError, match="NUL byte"):
            sanitize_path_string("path\x00/file.txt")

        with pytest.raises(PathInputError, match="control characters not permitted"):
            sanitize_path_string("dir\x1F/file.txt")

    def test_absolute_path_rejection(self):
        """Test absolute path rejection."""
        # Unix absolute paths
        with pytest.raises(PathSecurityError, match="absolute paths are not permitted"):
            sanitize_path_string("/absolute/path")

        with pytest.raises(PathSecurityError, match="absolute paths are not permitted"):
            sanitize_path_string("/")

        # Allow absolute paths when disabled
        assert sanitize_path_string("/path", forbid_absolute=False) == "/path"

    def test_unc_path_rejection(self):
        """Test UNC path rejection."""
        with pytest.raises(PathSecurityError, match="UNC paths are not permitted"):
            sanitize_path_string("\\\\server\\share")

        with pytest.raises(PathSecurityError, match="UNC paths are not permitted"):
            sanitize_path_string("\\\\")

        # Allow when absolute paths disabled (but note separator normalization)
        result = sanitize_path_string("\\\\server", forbid_absolute=False)
        # The double backslash gets normalized to forward slash due to collapse_separators
        assert result == "/server"

    def test_drive_path_rejection(self):
        """Test Windows drive path rejection."""
        with pytest.raises(PathSecurityError, match="drive-prefixed paths"):
            sanitize_path_string("C:/Windows")

        with pytest.raises(PathSecurityError, match="drive-prefixed paths"):
            sanitize_path_string("D:\\Data")

        # Allow when absolute disabled
        assert sanitize_path_string("C:/test", forbid_absolute=False) == "C:/test"

    def test_tilde_expansion_rejection(self):
        """Test tilde expansion rejection."""
        with pytest.raises(PathSecurityError, match="tilde expansion is not permitted"):
            sanitize_path_string("~/Documents")

        with pytest.raises(PathSecurityError, match="tilde expansion is not permitted"):
            sanitize_path_string("~user/file")

        # Allow when disabled
        assert sanitize_path_string("~/test", forbid_tilde=False) == "~/test"

    def test_traversal_rejection(self):
        """Test path traversal rejection."""
        traversal_cases = [
            "../",
            "..",
            "../..",
            "dir/../..",
            "dir/../../file",
            "file/../../../etc",
            "../file.txt",
            "dir\\..\\file",  # Windows style
        ]

        for case in traversal_cases:
            with pytest.raises(PathSecurityError, match="path traversal not permitted"):
                sanitize_path_string(case)

        # Allow when disabled
        assert sanitize_path_string("../test", forbid_traversal=False) == "../test"

    def test_separator_collapsing(self):
        """Test separator collapsing and excessive separator detection."""
        # Test excessive separators
        with pytest.raises(PathSecurityError, match="excessive path separators"):
            sanitize_path_string("path///file")

        with pytest.raises(PathSecurityError, match="excessive path separators"):
            sanitize_path_string("path\\\\\\\\file")

        # Test normal separator collapsing
        assert sanitize_path_string("path//file") == "path/file"
        assert sanitize_path_string("path\\\\file") == "path/file"
        assert sanitize_path_string("path/\\file") == "path/file"

        # Disable collapsing
        result = sanitize_path_string("path//file", collapse_separators=False)
        assert "//" in result

    def test_length_limits(self):
        """Test path length and component limits."""
        # Test total length limit - create a single long path
        long_path = "a" * 5000  # Single component longer than 4096
        with pytest.raises(PathInputError, match="path too long"):
            sanitize_path_string(long_path)

        # Custom length limit
        assert sanitize_path_string("short/path", max_total_length=20) == "short/path"
        with pytest.raises(PathInputError, match="path too long"):
            sanitize_path_string("very/long/path/name", max_total_length=10)

        # Test component limit - create many short components
        many_components = "/".join([f"d{i}" for i in range(200)])
        with pytest.raises(PathInputError, match="too many path components"):
            sanitize_path_string(many_components, max_components=128)

    def test_empty_and_invalid_inputs(self):
        """Test empty and invalid input handling."""
        with pytest.raises(PathInputError, match="path cannot be empty"):
            sanitize_path_string("")

        with pytest.raises(PathInputError, match="path must be a string"):
            sanitize_path_string(None)  # type: ignore

        # Empty after sanitization
        with pytest.raises(PathInputError, match="empty after sanitization"):
            sanitize_path_string("   ...")


class TestSplitAndValidateComponents:
    """Test split_and_validate_components function."""

    def test_basic_path_splitting(self):
        """Test basic path component splitting."""
        assert split_and_validate_components("file.txt") == ["file.txt"]
        assert split_and_validate_components("dir/file.txt") == ["dir", "file.txt"]
        assert split_and_validate_components("path/to/file.json") == ["path", "to", "file.json"]

    def test_separator_handling(self):
        """Test handling of different path separators."""
        # Forward slashes
        assert split_and_validate_components("a/b/c") == ["a", "b", "c"]
        # Backslashes
        assert split_and_validate_components("a\\b\\c") == ["a", "b", "c"]
        # Mixed separators
        assert split_and_validate_components("a/b\\c") == ["a", "b", "c"]
        # Multiple separators
        assert split_and_validate_components("a//b\\\\c") == ["a", "b", "c"]

    def test_empty_component_filtering(self):
        """Test filtering of empty, '.', and '..' components."""
        # Empty components
        assert split_and_validate_components("a//b") == ["a", "b"]
        assert split_and_validate_components("//a/b//") == ["a", "b"]

        # Current directory components
        assert split_and_validate_components("./a/./b/.") == ["a", "b"]

        # Parent directory components (filtered out)
        assert split_and_validate_components("a/../b") == ["a", "b"]

        # Mixed cases
        assert split_and_validate_components("./a//b/../c/.") == ["a", "b", "c"]

    def test_component_validation(self):
        """Test individual component validation."""
        # Valid components
        result = split_and_validate_components("good/file.txt")
        assert result == ["good", "file.txt"]

        # Invalid component (control chars would be caught in sanitize_path_string first)
        # Here we test other validation like reserved names
        with pytest.raises(PathInputError, match="invalid path component"):
            split_and_validate_components("dir/CON.txt")

        # Hidden files
        with pytest.raises(PathInputError, match="invalid path component"):
            split_and_validate_components("dir/.hidden")

        # Allow hidden files
        result = split_and_validate_components("dir/.config", allow_hidden=True)
        assert result == ["dir", ".config"]

    def test_length_limits(self):
        """Test component length limits."""
        # Valid length
        assert split_and_validate_components("a/b", max_length=10) == ["a", "b"]

        # Component too long
        long_component = "a" * 300
        with pytest.raises(PathInputError, match="invalid path component"):
            split_and_validate_components(f"dir/{long_component}")

    def test_empty_path(self):
        """Test empty path handling."""
        assert split_and_validate_components("") == []
        assert split_and_validate_components("///") == []
        assert split_and_validate_components(".//..//.") == []

    def test_invalid_input(self):
        """Test invalid input handling."""
        with pytest.raises(PathInputError, match="path must be a string"):
            split_and_validate_components(None)  # type: ignore


class TestIntegration:
    """Test integration between functions and invariants."""

    def test_round_trip_invariant(self):
        """Test that '/'.join(split_and_validate_components(sanitize_path_string(x))) is stable."""
        test_paths = [
            "file.txt",
            "dir/file.txt",
            "path/to/deep/file.json",
            "mixed\\separators/path",
            "a//b\\\\c/d",  # Multiple separators get collapsed
        ]

        for path in test_paths:
            sanitized = sanitize_path_string(path)
            components = split_and_validate_components(sanitized)
            rejoined = "/".join(components)

            # Should be stable (or at least equivalent)
            re_sanitized = sanitize_path_string(rejoined)
            re_components = split_and_validate_components(re_sanitized)

            assert components == re_components, f"Round trip failed for {path}"

    def test_policy_consistency(self):
        """Test consistent policy application across functions."""
        # Hidden file policy should be consistent
        with pytest.raises((PathInputError, PathSecurityError)):
            sanitized = sanitize_path_string("dir/.hidden")
            split_and_validate_components(sanitized, allow_hidden=False)

        # Should work when allowed
        sanitized = sanitize_path_string("dir/.config")
        result = split_and_validate_components(sanitized, allow_hidden=True)
        assert ".config" in result

    def test_comprehensive_edge_cases(self):
        """Test comprehensive edge cases."""
        edge_cases = [
            # Unicode edge cases
            ("café/résumé.txt", ["café", "résumé.txt"]),
            # Multiple separators with normalization
            ("a//b\\\\c", ["a", "b", "c"]),
            # Trailing separators
            ("a/b/", ["a", "b"]),
            # Leading separators (in relative context)
            ("./a/b", ["a", "b"]),
        ]

        for path_input, expected in edge_cases:
            sanitized = sanitize_path_string(path_input)
            result = split_and_validate_components(sanitized)
            assert result == expected, f"Failed for {path_input}"

    def test_deterministic_behavior(self):
        """Test that functions are deterministic."""
        test_input = "café//dir\\.\\file.txt"

        # Multiple runs should produce identical results
        results = []
        for _ in range(5):
            sanitized = sanitize_path_string(test_input)
            components = split_and_validate_components(sanitized)
            results.append((sanitized, components))

        # All results should be identical
        first_result = results[0]
        for result in results[1:]:
            assert result == first_result
