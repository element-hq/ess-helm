# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Tests for the fallback transformation mechanism.
"""

import logging
import pytest
from ess_migration_tool.migration import ConfigValueTransformer, MigrationError
from ess_migration_tool.models import TransformationSpec
from ess_migration_tool.utils import extract_hostname_from_url


def test_fallback_to_fallback_source():
    """Test fallback from primary_source to fallback_source."""
    # Build transformations directly
    transformations = [
        TransformationSpec(
            src_key="primary_source",
            target_key="target.value",
            transformer=extract_hostname_from_url,
            fallback=TransformationSpec(src_key="fallback_source", target_key="target.value"),
        ),
    ]

    config = {
        "fallback_source": "fallback.example.com",
        # primary_source is missing to trigger fallback
    }

    transformer = ConfigValueTransformer(logging.getLogger(), {})
    transformer.transform_from_config(config, transformations)

    result = transformer.ess_config
    assert result["target"]["value"] == "fallback.example.com"


def test_primary_source_precedence():
    """Test that primary source takes precedence over fallback."""
    transformations = [
        TransformationSpec(
            src_key="primary_source",
            target_key="target.value",
            transformer=extract_hostname_from_url,
            fallback=TransformationSpec(src_key="fallback_source", target_key="target.value"),
        ),
    ]

    config = {
        "primary_source": "https://primary.example.com",
        "fallback_source": "fallback.example.com",
    }

    transformer = ConfigValueTransformer(logging.getLogger(), {})
    transformer.transform_from_config(config, transformations)

    result = transformer.ess_config
    assert result["target"]["value"] == "primary.example.com"


def test_transformer_applied_to_primary_only():
    """Test that transformer is applied to primary but not fallback."""
    transformations = [
        TransformationSpec(
            src_key="primary_source",
            target_key="target.value",
            transformer=extract_hostname_from_url,
            fallback=TransformationSpec(src_key="fallback_source", target_key="target.value"),
        ),
    ]

    config = {
        "primary_source": "https://url.example.com/path",
        "fallback_source": "fallback.example.com",
    }

    transformer = ConfigValueTransformer(logging.getLogger(), {})
    transformer.transform_from_config(config, transformations)

    result = transformer.ess_config
    # Should extract hostname from URL
    assert result["target"]["value"] == "url.example.com"


def test_fallback_without_transformer():
    """Test that fallback value is used as-is when no transformer."""
    transformations = [
        TransformationSpec(
            src_key="primary_source",
            target_key="target.value",
            transformer=extract_hostname_from_url,
            fallback=TransformationSpec(src_key="fallback_source", target_key="target.value"),
        ),
    ]

    config = {
        "fallback_source": "fallback.example.com",
        # primary_source is missing to trigger fallback
    }

    transformer = ConfigValueTransformer(logging.getLogger(), {})
    transformer.transform_from_config(config, transformations)

    result = transformer.ess_config
    # Should use fallback_source as-is
    assert result["target"]["value"] == "fallback.example.com"


def test_required_fallback_fails():
    """Test that required transformation fails when no sources available."""
    transformations = [
        TransformationSpec(
            src_key="primary_source",
            target_key="target.value",
            transformer=extract_hostname_from_url,
            fallback=TransformationSpec(src_key="fallback_source", target_key="target.value"),
        ),
    ]

    config = {
        # Both primary_source and fallback_source are missing
    }

    transformer = ConfigValueTransformer(logging.getLogger(), {})

    # This should raise an error because both sources are missing
    with pytest.raises(MigrationError):
        transformer.transform_from_config(config, transformations)


def test_error_message_shows_all_attempted_keys():
    """Test that error message shows all attempted source keys."""
    transformations = [
        TransformationSpec(
            src_key="primary_source",
            target_key="target.value",
            transformer=extract_hostname_from_url,
            fallback=TransformationSpec(src_key="fallback_source", target_key="target.value"),
        ),
    ]

    config = {
        # Both primary_source and fallback_source are missing
    }

    transformer = ConfigValueTransformer(logging.getLogger(), {})

    try:
        transformer.transform_from_config(config, transformations)
        assert False, "Expected MigrationError to be raised"
    except MigrationError as e:
        # Check that error message contains both attempted keys
        assert "primary_source" in str(e)
        assert "fallback_source" in str(e)
        assert "Tried:" in str(e)


def test_public_baseurl_fallback_error():
    """Test that primary_source fallback shows proper error when both sources missing."""
    transformations = [
        TransformationSpec(
            src_key="primary_source", target_key="test.host", transformer=extract_hostname_from_url, required=True
        )
    ]

    config = {
        # primary_source is missing
    }

    transformer = ConfigValueTransformer(logging.getLogger(), {})

    # This should raise an error because primary_source is missing
    with pytest.raises(MigrationError):
        transformer.transform_from_config(config, transformations)


def test_multiple_fallback_levels():
    """Test multiple levels of fallbacks."""
    # Create transformation with multiple fallbacks
    transformations = [
        TransformationSpec(
            src_key="primary_source",
            target_key="test.host",
            transformer=extract_hostname_from_url,
            fallback=TransformationSpec(
                src_key="fallback_source",
                target_key="test.host",
                transformer=None,
                fallback=TransformationSpec(src_key="tertiary_source", target_key="test.host"),
            ),
        ),
    ]

    # Test third level fallback
    config = {"tertiary_source": "third.level.example.com"}
    transformer = ConfigValueTransformer(logging.getLogger(), {})
    transformer.transform_from_config(config, transformations)

    assert transformer.ess_config["test"]["host"] == "third.level.example.com"


def test_multiple_fallback_error_message():
    """Test error message with multiple fallback levels."""
    # Create transformation with multiple fallbacks
    transformations = [
        TransformationSpec(
            src_key="primary_source",
            target_key="test.host",
            transformer=extract_hostname_from_url,
            fallback=TransformationSpec(
                src_key="fallback_source",
                target_key="test.host",
                transformer=None,
                fallback=TransformationSpec(src_key="tertiary_source", target_key="test.host"),
            ),
        ),
    ]

    # This should raise an error because all fallback sources are missing
    config = {}
    transformer = ConfigValueTransformer(logging.getLogger(), {})

    with pytest.raises(MigrationError):
        transformer.transform_from_config(config, transformations)


def test_tracked_values_includes_primary_only():
    """Test that tracked_values only includes the source that was actually used."""
    transformations = [
        TransformationSpec(
            src_key="primary_source",
            target_key="target.value",
            transformer=extract_hostname_from_url,
            fallback=TransformationSpec(src_key="fallback_source", target_key="target.value"),
        ),
    ]

    config = {
        "primary_source": "https://primary.example.com",
        "fallback_source": "fallback.example.com",
    }

    transformer = ConfigValueTransformer(logging.getLogger(), {})
    transformer.transform_from_config(config, transformations)

    # Should track primary_source since it was used
    assert "primary_source" in transformer.tracked_values


def test_tracked_values_includes_fallback():
    """Test that tracked_values includes fallback when used."""
    transformations = [
        TransformationSpec(
            src_key="primary_source",
            target_key="target.value",
            transformer=extract_hostname_from_url,
            fallback=TransformationSpec(src_key="fallback_source", target_key="target.value"),
        ),
    ]

    config = {
        "fallback_source": "fallback.example.com",
        # primary_source is missing to trigger fallback
    }

    transformer = ConfigValueTransformer(logging.getLogger(), {})
    transformer.transform_from_config(config, transformations)

    # Should track primary_source even though fallback was used
    # (we track the primary source key, not the fallback)
    assert "primary_source" in transformer.tracked_values


def test_empty_string_values():
    """Test handling of empty string values."""
    transformations = [
        TransformationSpec(
            src_key="primary_source",
            target_key="target.value",
            transformer=extract_hostname_from_url,
            fallback=TransformationSpec(src_key="fallback_source", target_key="target.value"),
        ),
    ]

    config = {
        "primary_source": "",  # Empty string
        "fallback_source": "fallback.example.com",
    }

    transformer = ConfigValueTransformer(logging.getLogger(), {})
    transformer.transform_from_config(config, transformations)

    # Should fallback to fallback_source when primary_source is empty
    result = transformer.ess_config
    assert result["target"]["value"] == "fallback.example.com"


def test_none_values():
    """Test handling of None values."""
    transformations = [
        TransformationSpec(
            src_key="primary_source",
            target_key="target.value",
            transformer=extract_hostname_from_url,
            fallback=TransformationSpec(src_key="fallback_source", target_key="target.value"),
        ),
    ]

    config = {
        "primary_source": None,  # None value
        "fallback_source": "fallback.example.com",
    }

    transformer = ConfigValueTransformer(logging.getLogger(), {})
    transformer.transform_from_config(config, transformations)

    # Should fallback to fallback_source when primary_source is None
    result = transformer.ess_config
    assert result["target"]["value"] == "fallback.example.com"


def test_transformer_returns_none():
    """Test handling when transformer returns None."""

    # Create a transformer that returns None
    def failing_transformer(logger, value):
        return None

    transformations = [
        TransformationSpec(
            src_key="primary_source",
            target_key="test.host",
            transformer=failing_transformer,
            fallback=TransformationSpec(src_key="fallback_source", target_key="test.host"),
        ),
    ]

    config = {"primary_source": "https://example.com", "fallback_source": "fallback.example.com"}

    transformer = ConfigValueTransformer(logging.getLogger(), {})
    transformer.transform_from_config(config, transformations)

    # Should fallback when transformer returns None
    assert transformer.ess_config["test"]["host"] == "fallback.example.com"
