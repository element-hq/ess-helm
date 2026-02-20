# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Pytest tests for extra files discovery functionality.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import pytest

from ..extra_files import ExtraFilesDiscovery, ExtraFilesError
from ..interfaces import ExtraFilesDiscoveryStrategy, SecretDiscoveryStrategy
from ..models import DiscoveredPath, SecretConfig


def test_validate_extra_files_success(tmp_path):
    """Test successful validation of extra files."""
    # Create test files
    file1 = tmp_path / "test1.txt"
    file2 = tmp_path / "test2.yaml"

    file1.write_text("test content 1")
    file2.write_text("test: content 2")

    @dataclass
    class TestStrategy(ExtraFilesDiscoveryStrategy):
        @property
        def ignored_config_keys(self):
            return []

    @dataclass
    class TestSecretStrategy(SecretDiscoveryStrategy):
        @property
        def ess_secret_schema(self):
            return {}

    test1 = DiscoveredPath(config_key="a", source_file="test.yaml", source_path=tmp_path / "test1.txt")
    test2 = DiscoveredPath(config_key="b", source_file="test.yaml", source_path=tmp_path / "test2.yaml")
    discovery = ExtraFilesDiscovery(
        strategy=TestStrategy(),
        pretty_logger=logging.getLogger(),
        secrets_strategy=TestSecretStrategy(),
        source_file="test.yaml",
        discovered_file_paths=[
            test1,
            test2,
        ],
    )

    # Should validate successfully
    discovery._discover_extra_files()

    assert len(discovery.discovered_extra_files) == 2
    for file in discovery.discovered_extra_files.values():
        if file.discovered_source_paths[0] == test1:
            assert file.content == b"test content 1"
        elif file.discovered_source_paths[0] == test2:
            assert file.content == b"test: content 2"
        else:
            pytest.fail("Unexpected file")


def test_validate_extra_files_missing():
    """Test validation failure when files are missing."""

    @dataclass
    class TestStrategy(ExtraFilesDiscoveryStrategy):
        @property
        def ignored_config_keys(self):
            return []

    @dataclass
    class TestSecretStrategy(SecretDiscoveryStrategy):
        @property
        def ess_secret_schema(self):
            return {}

    discovery = ExtraFilesDiscovery(
        strategy=TestStrategy(),
        pretty_logger=logging.getLogger(),
        secrets_strategy=TestSecretStrategy(),
        source_file="test.yaml",
        discovered_file_paths=[
            DiscoveredPath(config_key="a", source_file="test.yaml", source_path="nonexistent/file1.txt"),
            DiscoveredPath(config_key="b", source_file="test.yaml", source_path="nonexistent/file2.yaml"),
        ],
    )

    # Should raise ExtraFilesError
    with pytest.raises(ExtraFilesError) as exc_info:
        discovery.validate_extra_files()

    # Should have missing files
    assert "Missing or invalid extra files" in str(exc_info.value)
    missing_files = [missing.source_path for missing in discovery.missing_file_paths]
    assert len(missing_files) == 2
    assert "nonexistent/file1.txt" in missing_files
    assert "nonexistent/file2.yaml" in missing_files


def test_file_path_detection():
    """Test file path detection logic."""

    @dataclass
    class TestStrategy(ExtraFilesDiscoveryStrategy):
        @property
        def ignored_config_keys(self):
            return []

    @dataclass
    class TestSecretStrategy(SecretDiscoveryStrategy):
        @property
        def ess_secret_schema(self):
            return {}

    discovery = ExtraFilesDiscovery(
        strategy=TestStrategy(),
        pretty_logger=logging.getLogger(),
        secrets_strategy=TestSecretStrategy(),
        source_file="test.yaml",
    )

    # Test various file path patterns
    test_cases = [
        ("/absolute/path/to/file.txt", True),
        ("./relative/path/to/file.yaml", True),
        ("../parent/dir/file.json", True),
        ("~/home/user/config.yml", True),
        ("https://example.com/file.txt", False),  # URL
        ("http://example.com/file.txt", False),  # URL
        ("just-a-string", False),  # Not a file path
        ("12345", False),  # Not a file path
    ]

    for test_value, expected_result in test_cases:
        result = discovery._is_file_path(test_value)
        assert result == expected_result, (
            f"File path detection failed for '{test_value}': expected {expected_result}, got {result}"
        )


def test_discover_file_paths_from_dict_and_list():
    """Test recursive file path discovery from dictionary."""
    config_data = {
        "server": {"name": "test.example.com", "config_file": "./server/config.yaml"},
        "templates": {
            "directory": "./templates",
            "files": ["./templates/header.html", "./templates/footer.html"],
        },
        "modules": [{"name": "custom_module", "config": "./modules/custom.yaml"}],
        "resources": ["./resources/style.css", "./resources/script.js"],
    }

    @dataclass
    class TestStrategy(ExtraFilesDiscoveryStrategy):
        @property
        def ignored_config_keys(self):
            return []

    @dataclass
    class TestSecretStrategy(SecretDiscoveryStrategy):
        @property
        def ess_secret_schema(self):
            return {}

    discovery = ExtraFilesDiscovery(
        strategy=TestStrategy(),
        pretty_logger=logging.getLogger(),
        secrets_strategy=TestSecretStrategy(),
        source_file="test.yaml",
    )
    discovery._discover_file_paths_from_list_or_dict(config_data)

    discovered_files = [d.source_path for d in discovery.discovered_file_paths if not d.skipped_reason]

    expected_files = [
        "./server/config.yaml",
        "./templates",
        "./templates/header.html",
        "./templates/footer.html",
        "./modules/custom.yaml",
        "./resources/style.css",
        "./resources/script.js",
    ]

    for expected_file in expected_files:
        assert Path(expected_file) in discovered_files, f"Expected file {expected_file} not found in discovered files"


def test_mixed_config_with_secrets_and_extra_files():
    """Test configuration with both secrets and extra files."""
    config_data = {
        "database": {
            "args": {
                "password": "db_password"  # Should be handled by secrets
            }
        },
        "email": {
            "template_dir": "./templates",  # Should be handled by extra files
            "template_html": "./email.html",  # Should be handled by extra files
        },
        "signing_key_path": "./secrets/signing.key",  # Should be handled by secrets
    }

    @dataclass
    class TestStrategy(ExtraFilesDiscoveryStrategy):
        @property
        def ignored_config_keys(self):
            return []

    @dataclass
    class TestSecretStrategy(SecretDiscoveryStrategy):
        @property
        def ess_secret_schema(self):
            return {
                # Synapse secrets
                "synapse.postgres.password": SecretConfig(
                    init_if_missing_from_source_cfg=False,  # Must be provided
                    description="Synapse database password",
                    config_inline="database.args.password",
                    config_path=None,
                ),
                "synapse.signingKey": SecretConfig(
                    init_if_missing_from_source_cfg=False,  # This would break federation if changing after migrating
                    description="Signing key",
                    config_inline="signing_key",
                    config_path="signing_key_path",
                ),
            }

    discovery = ExtraFilesDiscovery(
        strategy=TestStrategy(),
        pretty_logger=logging.getLogger(),
        secrets_strategy=TestSecretStrategy(),
        source_file="test.yaml",
    )

    discovery._discover_file_paths_from_list_or_dict(config_data)

    discovered_files = [d.source_path for d in discovery.discovered_file_paths if not d.skipped_reason]
    skipped_files = [d.source_path for d in discovery.discovered_file_paths if d.skipped_reason]

    # Should only include non-secret paths
    expected_files = ["./templates", "./email.html"]

    # Should include secret paths in skipped files
    expected_skipped_files = ["./secrets/signing.key"]

    assert len(expected_files) == len(discovered_files)
    for expected_file in expected_files:
        assert Path(expected_file) in discovered_files, f"Expected file {expected_file} not found in discovered files"

    assert len(skipped_files) == len(expected_skipped_files)
    for expected_skipped_file in expected_skipped_files:
        assert Path(expected_skipped_file) in skipped_files, (
            f"Expected skipped file {expected_skipped_file} not found in skipped files"
        )


def test_duplicate_file_paths(tmp_path):
    """Test handling of duplicate file paths."""
    config_data = {
        "template_dir": str(tmp_path / "templates"),
        "templates": {
            "directory": str(tmp_path / "templates")  # Duplicate
        },
        "resources": [
            str(tmp_path / "templates"),  # Another duplicate
            str(tmp_path / "other" / "file.txt"),
        ],
    }

    (tmp_path / "templates").mkdir()
    (tmp_path / "templates" / "header.html").write_text("header")
    (tmp_path / "other").mkdir()
    (tmp_path / "other" / "file.txt").write_text("other")

    @dataclass
    class TestStrategy(ExtraFilesDiscoveryStrategy):
        @property
        def ignored_config_keys(self):
            return []

    @dataclass
    class TestSecretStrategy(SecretDiscoveryStrategy):
        @property
        def ess_secret_schema(self):
            return {}

    discovery = ExtraFilesDiscovery(
        strategy=TestStrategy(),
        pretty_logger=logging.getLogger(),
        secrets_strategy=TestSecretStrategy(),
        source_file="test.yaml",
    )
    discovery.discover_extra_files_from_config(config_data)

    # Should have discovered 4 paths
    assert len(discovery.discovered_file_paths) == 4
    # But should only import 2 files as they are used in multiple places of the config
    assert len(discovery.discovered_extra_files) == 2

    for path, discovered_file in discovery.discovered_extra_files.items():
        if path == str(tmp_path / "templates"):
            assert discovered_file.content == "header"
            assert len(discovered_file.discovered_source_paths) == 3
            for discovered in discovered_file.discovered_source_paths:
                assert discovered.source_path == str(tmp_path / "templates")
        elif path == str(tmp_path / "other"):
            assert discovered_file.content == "other"
            assert discovered_file.discovered_source_paths[0].source_path == str(tmp_path / "other")


def test_binary_file_detection(tmp_path):
    """Test that binary files are detected and skipped."""
    # Create a text file
    text_file = tmp_path / "config.txt"
    text_file.write_text("This is a text configuration file")

    # Create a binary file (with null bytes)
    binary_file = tmp_path / "data.bin"
    binary_file.write_bytes(b"\x00\x01\x02\x03\x00Binary data with null bytes")

    # Create configuration with both files
    config_data = {
        "text_config": str(text_file),
        "binary_data": str(binary_file),
    }

    @dataclass
    class TestStrategy(ExtraFilesDiscoveryStrategy):
        @property
        def ignored_config_keys(self):
            return []

    @dataclass
    class TestSecretStrategy(SecretDiscoveryStrategy):
        @property
        def ess_secret_schema(self):
            return {}

    discovery = ExtraFilesDiscovery(
        strategy=TestStrategy(),
        pretty_logger=logging.getLogger(),
        secrets_strategy=TestSecretStrategy(),
        source_file="test.yaml",
    )
    discovery.discover_extra_files_from_config(config_data)

    # Should have discovered both files
    assert len(discovery.discovered_extra_files) == 2
    for discovered_file in discovery.discovered_extra_files.values():
        if discovered_file.discovered_source_paths[0].source_path == text_file:
            assert discovered_file.cleartext
            assert discovered_file.content == text_file.read_bytes()
        if discovered_file.discovered_source_paths[0].source_path == binary_file:
            assert not discovered_file.cleartext
            assert discovered_file.content == binary_file.read_bytes()


def test_ignored_config_keys():
    """Test that ignored configuration keys are properly skipped during discovery."""

    @dataclass
    class TestStrategy(ExtraFilesDiscoveryStrategy):
        @property
        def ignored_config_keys(self):
            return ["media_store_path"]

    @dataclass
    class TestSecretStrategy(SecretDiscoveryStrategy):
        @property
        def ess_secret_schema(self):
            return {}

    config_data = {
        "media_store_path": "/var/synapse/media_store",
        "log_config": "/var/synapse/log_config.yaml",
        "templates": "/var/synapse/templates",
        "email_config": "/var/synapse/email.yaml",
        "media_backup_path": "/backup/media_store",
    }

    discovery = ExtraFilesDiscovery(
        strategy=TestStrategy(),
        pretty_logger=logging.getLogger(),
        secrets_strategy=TestSecretStrategy(),
        source_file="test.yaml",
    )
    discovery._discover_file_paths_from_list_or_dict(config_data)

    discovered_files = [d.source_path for d in discovery.discovered_file_paths if not d.skipped_reason]
    skipped_files = [d.source_path for d in discovery.discovered_file_paths if d.skipped_reason]

    # Should only discover non-ignored config keys
    expected_files = ["/var/synapse/templates", "/var/synapse/email.yaml", "/backup/media_store"]
    expected_skipped_files = ["/var/synapse/media_store"]

    for expected_file in expected_files:
        assert Path(expected_file) in discovered_files, f"Expected file {expected_file} not found in discovered files"

    for expected_skipped_file in expected_skipped_files:
        assert Path(expected_skipped_file) in skipped_files, (
            f"Expected skipped file {expected_skipped_file} not found in skipped files"
        )

    # Verify ignored files are not in discovered files
    for expected_skipped_file in expected_skipped_files:
        assert expected_skipped_file not in discovered_files, (
            f"Ignored file {expected_skipped_file} should not be in discovered files"
        )
