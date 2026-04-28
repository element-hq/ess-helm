# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest
from ess_migration_tool.utils import (
    find_matching_schema_key,
    get_nested_value,
    is_wildcard_pattern,
    path_matches_pattern,
    remove_nested_value,
    set_nested_value,
    sort_tracked_values_for_filtering,
)


@pytest.fixture
def sample_config():
    """Fixture to provide a fresh config dictionary for each test."""
    return {"a": {"b": {"c": 42, "d": [10, 20, 30]}, "e": "hello"}, "f": [{"x": 1}, {"x": 2}, {"x": 3}]}


def test_get_nested_value(sample_config):
    # Test direct key access
    assert get_nested_value(sample_config, "a") == {"b": {"c": 42, "d": [10, 20, 30]}, "e": "hello"}
    assert get_nested_value(sample_config, "f") == [{"x": 1}, {"x": 2}, {"x": 3}]

    # Test nested dictionary access
    assert get_nested_value(sample_config, "a.b.c") == 42
    assert get_nested_value(sample_config, "a.e") == "hello"

    # Test list access
    assert get_nested_value(sample_config, "a.b.d.1") == 20
    assert get_nested_value(sample_config, "a.b.d.-1") == 30
    assert get_nested_value(sample_config, "f.1.x") == 2

    # Test invalid paths
    assert get_nested_value(sample_config, "a.b.x") is None
    assert get_nested_value(sample_config, "a.b.d.5") is None
    assert get_nested_value(sample_config, "a.b.d.x") is None
    assert get_nested_value(sample_config, "x") is None
    assert get_nested_value(sample_config, "a.x.y") is None

    # Test edge cases
    assert get_nested_value({}, "a") is None
    assert get_nested_value(sample_config, "") is None
    assert get_nested_value(sample_config, "a.b.d.4") is None  # Invalid list index


def test_set_nested_value_direct_key(sample_config):
    set_nested_value(sample_config, "a", {"new": "value"})
    assert sample_config["a"] == {"new": "value"}


def test_set_nested_value_nested_dict(sample_config):
    set_nested_value(sample_config, "a.b.c", 100)
    assert sample_config["a"]["b"]["c"] == 100


def test_set_nested_value_list(sample_config):
    set_nested_value(sample_config, "a.b.d.1", 200)
    assert sample_config["a"]["b"]["d"][1] == 200


def test_set_nested_value_new_nested_keys(sample_config):
    set_nested_value(sample_config, "a.new.nested.key", "created")
    assert sample_config["a"]["new"]["nested"]["key"] == "created"


def test_set_nested_value_list_index(sample_config):
    set_nested_value(sample_config, "f.1.x", 42)
    assert sample_config["f"][1]["x"] == 42


def test_set_nested_value_empty_config():
    config = {}
    set_nested_value(config, "a.b.c", 1)
    assert config == {"a": {"b": {"c": 1}}}


def test_remove_nested_value_direct_key(sample_config):
    remove_nested_value(sample_config, "a")
    assert sample_config == {"f": [{"x": 1}, {"x": 2}, {"x": 3}]}


def test_remove_nested_value_nested_dict(sample_config):
    remove_nested_value(sample_config, "a.b.c")
    assert sample_config == {"a": {"b": {"d": [10, 20, 30]}, "e": "hello"}, "f": [{"x": 1}, {"x": 2}, {"x": 3}]}


def test_remove_nested_value_list_item(sample_config):
    remove_nested_value(sample_config, "a.b.d.1")
    assert sample_config == {"a": {"b": {"c": 42, "d": [10, 30]}, "e": "hello"}, "f": [{"x": 1}, {"x": 2}, {"x": 3}]}


def test_remove_nested_value_list_dict(sample_config):
    remove_nested_value(sample_config, "f.1")
    assert sample_config == {"a": {"b": {"c": 42, "d": [10, 20, 30]}, "e": "hello"}, "f": [{"x": 1}, {"x": 3}]}


def test_remove_nested_value_nonexistent_path(sample_config):
    remove_nested_value(sample_config, "a.b.x")
    assert sample_config == {
        "a": {"b": {"c": 42, "d": [10, 20, 30]}, "e": "hello"},
        "f": [{"x": 1}, {"x": 2}, {"x": 3}],
    }


def test_remove_nested_value_empty_path(sample_config):
    remove_nested_value(sample_config, "")
    assert sample_config == {
        "a": {"b": {"c": 42, "d": [10, 20, 30]}, "e": "hello"},
        "f": [{"x": 1}, {"x": 2}, {"x": 3}],
    }


def test_remove_nested_value_empty_config():
    config = {}
    remove_nested_value(config, "a.b.c")
    assert config == {}


# Tests for set_nested_value list creation


def test_set_nested_value_creates_list_from_scratch():
    config = {}
    set_nested_value(config, "a.0", "val")
    assert config == {"a": ["val"]}


def test_set_nested_value_creates_list_with_multiple_items():
    config = {}
    set_nested_value(config, "a.0", "first")
    set_nested_value(config, "a.1", "second")
    assert config == {"a": ["first", "second"]}


def test_set_nested_value_creates_nested_list():
    config = {}
    set_nested_value(config, "a.0.b", "val")
    assert config == {"a": [{"b": "val"}]}


def test_set_nested_value_extends_list():
    config = {"a": ["x"]}
    set_nested_value(config, "a.1", "val")
    assert config == {"a": ["x", "val"]}


def test_set_nested_value_extends_list_with_gap():
    config = {"a": ["x"]}
    set_nested_value(config, "a.3", "val")
    assert config == {"a": ["x", None, None, "val"]}


def test_set_nested_value_deep_path_creates_lists():
    config = {}
    set_nested_value(config, "a.b.0.c.1.d", "val")
    assert config["a"]["b"][0]["c"][1]["d"] == "val"


# Tests for wildcard pattern matching


def test_is_wildcard_pattern_true():
    assert is_wildcard_pattern("a.*.c") is True
    assert is_wildcard_pattern("*") is True
    assert is_wildcard_pattern("a.*") is True


def test_is_wildcard_pattern_false():
    assert is_wildcard_pattern("a.b.c") is False
    assert is_wildcard_pattern("normal.path") is False
    assert is_wildcard_pattern("") is False


def test_path_matches_pattern_basic():
    assert path_matches_pattern("certificates.0.value", "certificates.*.value") is True
    assert path_matches_pattern("certificates.1.value", "certificates.*.value") is True
    assert path_matches_pattern("certificates.999.value", "certificates.*.value") is True


def test_path_matches_pattern_no_match():
    assert path_matches_pattern("certificates.0.name", "certificates.*.value") is False
    assert path_matches_pattern("other.0.value", "certificates.*.value") is False
    assert path_matches_pattern("certificates.value", "certificates.*.value") is False


def test_path_matches_pattern_exact_components():
    assert path_matches_pattern("a.1.c", "a.*.c") is True
    assert path_matches_pattern("a.b.c", "a.*.c") is True
    assert path_matches_pattern("a.x.c", "a.*.c") is True
    assert path_matches_pattern("x.1.c", "a.*.c") is False
    assert path_matches_pattern("a.1.x", "a.*.c") is False


def test_path_matches_pattern_different_length():
    assert path_matches_pattern("a.b", "a.*.c") is False
    assert path_matches_pattern("a.b.c.d", "a.*.c") is False


def test_path_matches_pattern_multiple_wildcards():
    # path_matches_pattern doesn't support multiple wildcards in pattern
    # It will just check component by component
    assert path_matches_pattern("a.1.c.2", "a.*.c.*") is True


# Tests for find_matching_schema_key


def test_find_matching_schema_key_exact_match():
    schema = {"a.b.c": "config"}
    assert find_matching_schema_key("a.b.c", schema) == "a.b.c"


def test_find_matching_schema_key_wildcard_match():
    schema = {"a.*.c": "wildcard_config"}
    assert find_matching_schema_key("a.999.c", schema) == "a.*.c"


def test_find_matching_schema_key_wildcard_no_match():
    schema = {"a.*.c": "wildcard_config"}
    assert find_matching_schema_key("a.999.z", schema) is None


def test_find_matching_schema_key_no_match():
    schema = {"a.b.c": "config"}
    assert find_matching_schema_key("x.y.z", schema) is None


def test_find_matching_schema_key_prefers_exact():
    # When both exact and wildcard match, exact takes precedence
    schema = {"a.0.c": "exact_config", "a.*.c": "wildcard_config"}
    assert find_matching_schema_key("a.0.c", schema) == "a.0.c"


def test_find_matching_schema_key_multiple_patterns():
    schema = {"a.*.c": "pattern1", "x.*.y": "pattern2"}
    assert find_matching_schema_key("a.5.c", schema) == "a.*.c"
    assert find_matching_schema_key("x.5.y", schema) == "x.*.y"
    assert find_matching_schema_key("z.5.y", schema) is None


# Tests for sort_tracked_values_for_filtering


def test_sort_tracked_values_basic():
    """Test basic sorting of list indices in descending order."""
    tracked = ["a", "b.0", "b.1", "b.2"]
    result = sort_tracked_values_for_filtering(tracked)
    # Regular paths first (in their original order), then indexed paths sorted descending
    assert result == ["a", "b.2", "b.1", "b.0"]


def test_sort_tracked_values_multiple_parents():
    """Test sorting with multiple parent groups."""
    tracked = ["secrets.keys.0", "secrets.encryption", "secrets.keys.1", "other.value", "secrets.keys.2"]
    result = sort_tracked_values_for_filtering(tracked)
    # Regular paths first, then each parent's indices in descending order
    assert result == ["secrets.encryption", "other.value", "secrets.keys.2", "secrets.keys.1", "secrets.keys.0"]


def test_sort_tracked_values_no_indices():
    """Test with no list indices."""
    tracked = ["a", "b.c", "d.e.f"]
    result = sort_tracked_values_for_filtering(tracked)
    assert result == ["a", "b.c", "d.e.f"]


def test_sort_tracked_values_nested_list_indices():
    """Test with deeply nested paths where last part is an index."""
    tracked = ["a.b.c.0", "a.b.c.1", "a.b.c.2"]
    result = sort_tracked_values_for_filtering(tracked)
    assert result == ["a.b.c.2", "a.b.c.1", "a.b.c.0"]


def test_sort_tracked_values_mixed_numeric_non_numeric():
    """Test with mixed paths - some ending in numbers, some not."""
    tracked = ["a.0", "b.name", "a.1", "c.5", "b.other"]
    result = sort_tracked_values_for_filtering(tracked)
    # Regular paths first (in original order), then indexed paths sorted by parent then by index descending
    assert result == ["b.name", "b.other", "a.1", "a.0", "c.5"]


def test_sort_tracked_values_empty_list():
    """Test with empty input."""
    assert sort_tracked_values_for_filtering([]) == []


def test_sort_tracked_values_single_element():
    """Test with single element."""
    assert sort_tracked_values_for_filtering(["a.0"]) == ["a.0"]


def test_sort_tracked_values_index_zero():
    """Test that index 0 is handled correctly."""
    tracked = ["keys.0"]
    result = sort_tracked_values_for_filtering(tracked)
    assert result == ["keys.0"]


def test_sort_tracked_values_real_world_mas_keys():
    """Test the real-world case from MAS individual keys migration."""
    tracked = ["secrets.encryption", "secrets.keys.0", "secrets.keys.1", "secrets.keys.2"]
    result = sort_tracked_values_for_filtering(tracked)
    assert result == ["secrets.encryption", "secrets.keys.2", "secrets.keys.1", "secrets.keys.0"]
