# Copyright 2024 New Vector Ltd
# Copyright 2025 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
import tempfile
from pathlib import Path

import pytest

from .construct_helm_schema import (
    construct_helm_schema,
    default_additionalProperties_to_off,
    inline_sub_schemas,
    schema_walker,
)


def test_schema_walker_returns_callable_result():
    to_return = {"something": "fwibble"}
    result = schema_walker({}, lambda x: to_return)
    assert result == to_return


def test_schema_walker_returns_none_from_callable():
    assert schema_walker({}, lambda x: None) is None


def test_schema_walker_calls_callable_with_non_deep_copy():
    schema_part = {"something": "fwible", "else": ["value"]}
    result = schema_walker(schema_part, lambda x: x)
    assert result == schema_part

    # We prove at least a shallow copy of the input dict here
    # i.e. modifying the keys of one dict doesn't impact the other dict
    del schema_part["something"]
    assert "something" in result

    # We prove this is not a deep copy of the input dict here
    # i.e. the values in both dict are the same object
    # We don't need to deepcopy everytime as we copy before each callable call
    assert len(schema_part["else"]) == len(result["else"])
    schema_part["else"].append("other")
    assert len(schema_part["else"]) == len(result["else"])


def test_schema_walker_recurses_into_properties():
    schema_part = {
        "properties": {
            "nested": {"something": "present"},
        },
        "something": "else",
    }

    visited = []

    def handle_visit(visitor):
        visited.append(visitor)
        return visitor

    result = schema_walker(schema_part, handle_visit)
    assert result == schema_part
    assert visited[0] == schema_part
    assert visited[1] == schema_part["properties"]["nested"]


def test_schema_walker_removes_properties_callable_returns_none_for():
    schema_part = {
        "properties": {
            "to_remove": {"remove_me": True},
            "nested": {"something": "present"},
        }
    }

    visited = []

    def handle_visit(visitor):
        visited.append(visitor)
        if "remove_me" in visitor:
            return None
        return visitor

    result = schema_walker(schema_part, handle_visit)
    assert "properties" in result
    assert "nested" in result["properties"]
    assert result["properties"]["nested"] == schema_part["properties"]["nested"]
    assert "to_remove" not in result["properties"]


def test_schema_walker_visits_array_items():
    schema_part = {"items": {"something": "present"}}

    visited = []

    def handle_visit(visitor):
        visited.append(visitor)
        return visitor

    result = schema_walker(schema_part, handle_visit)
    assert result == schema_part
    assert visited[0] == schema_part
    assert visited[1] == schema_part["items"]


def test_leaves_schema_part_for_non_object_alone():
    assert "additionalProperties" not in default_additionalProperties_to_off(None, {"type": "integer"})
    assert "additionalProperties" not in default_additionalProperties_to_off(None, {"type": "string"})
    assert "additionalProperties" not in default_additionalProperties_to_off(None, {"type": "array"})


def test_inline_sub_schema_returns_referenced_sub_schema():
    source_root = Path(__file__).parent / "testdata" / "schema_construction"
    sub_schema = inline_sub_schemas(source_root / "schema.json", {"$ref": "file://sub_schema1.json"})
    assert sub_schema["type"] == "object"
    assert sub_schema["properties"].keys() == set(["first", "second"])


def test_inline_sub_schemas_disallows_other_properties_on_attachment_point():
    source_root = Path(__file__).parent / "testdata" / "schema_construction"
    with pytest.raises(AssertionError):
        inline_sub_schemas(
            source_root / "schema.json",
            {"$ref": "file://sub_schema1.json", "other": "disallowed"},
        )


def test_inline_sub_schemas_disallows_non_object_sub_schemas():
    source_root = Path(__file__).parent / "testdata" / "schema_construction"
    with pytest.raises(AssertionError):
        inline_sub_schemas(source_root / "schema.json", {"$ref": "file://invalid_sub_schema1.json"})


def test_inline_sub_schemas_disallows_immediately_referencing_another_sub_schema():
    source_root = Path(__file__).parent / "testdata" / "schema_construction"
    with pytest.raises(AssertionError):
        inline_sub_schemas(source_root / "schema.json", {"$ref": "file://invalid_sub_schema2.json"})


def test_sets_additionalProperties_false_for_objects_where_unspecified():
    updated_schema_part = default_additionalProperties_to_off(None, {"type": "object"})
    assert "additionalProperties" in updated_schema_part
    assert not updated_schema_part["additionalProperties"]


def test_respects_explicit_additionalProperties_true():
    updated_schema_part = default_additionalProperties_to_off(None, {"type": "object", "additionalProperties": True})
    assert "additionalProperties" in updated_schema_part
    assert updated_schema_part["additionalProperties"]


def test_constructs_merged_schema():
    with tempfile.TemporaryDirectory() as destination_folder:
        source_schema = Path(__file__).parent / "testdata" / "schema_construction" / "schema.json"
        destination_schema = Path(destination_folder) / "values.schema.json"

        construct_helm_schema(source_schema, destination_schema)

        destination_schema_contents = json.loads(destination_schema.read_text(encoding="UTF-8"))

        # Property directly in the referenced
        assert "presentDirectly" in destination_schema_contents["properties"]
        assert destination_schema_contents["properties"]["presentDirectly"]["type"] == "object"

        assert "merged" in destination_schema_contents["properties"]
        assert "type" in destination_schema_contents["properties"]["merged"]
        assert destination_schema_contents["properties"]["merged"]["type"] == "object"
        assert "properties" in destination_schema_contents["properties"]["merged"]
