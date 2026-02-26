# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import pytest

from ..utils import get_nested_value, remove_nested_value, set_nested_value


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
