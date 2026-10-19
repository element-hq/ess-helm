# Copyright 2024 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
import tempfile
from pathlib import Path

import pytest

from .construct_helm_schema import (
    construct_helm_schema,
    default_additionalProperties_to_off,
    move_sub_schemas_to_defs,
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


def test_leaves_schema_part_for_a_ref_alone():
    schema_part = {"$ref": "#/$defs/something"}
    assert default_additionalProperties_to_off(None, schema_part) == schema_part


def test_move_sub_schemas_to_defs_returns_reference_to_the_sub_schema():
    source_root = Path(__file__).parent / "testdata" / "schema_construction"
    sub_schemas = {}
    sub_schema_refs = {}

    schema_part = move_sub_schemas_to_defs(
        source_root / "schema.json", {"$ref": "file://sub_schema1.json"}, sub_schemas, sub_schema_refs
    )

    assert schema_part == {"$ref": "#/$defs/sub_schema1"}
    assert sub_schemas["sub_schema1"]["type"] == "object"
    assert sub_schemas["sub_schema1"]["properties"].keys() == set(["first", "second"])


def test_move_sub_schemas_to_defs_stores_each_sub_schema_once():
    source_root = Path(__file__).parent / "testdata" / "schema_construction"
    sub_schemas = {}
    sub_schema_refs = {}

    first_reference = move_sub_schemas_to_defs(
        source_root / "schema.json", {"$ref": "file://sub_schema1.json"}, sub_schemas, sub_schema_refs
    )
    second_reference = move_sub_schemas_to_defs(
        source_root / "schema.json", {"$ref": "file://sub_schema1.json"}, sub_schemas, sub_schema_refs
    )

    assert first_reference == second_reference == {"$ref": "#/$defs/sub_schema1"}
    assert sub_schemas.keys() == {"sub_schema1"}


def test_move_sub_schemas_to_defs_moves_nested_sub_schemas_too():
    source_root = Path(__file__).parent / "testdata" / "schema_construction"
    sub_schemas = {}
    sub_schema_refs = {}

    schema_part = move_sub_schemas_to_defs(
        source_root / "schema.json", {"$ref": "file://sub_schema2.json"}, sub_schemas, sub_schema_refs
    )

    assert schema_part == {"$ref": "#/$defs/sub_schema2"}
    assert sub_schemas["sub_schema2"]["properties"]["nested"] == {"$ref": "#/$defs/sub_schema1"}
    assert sub_schemas["sub_schema1"]["properties"].keys() == set(["first", "second"])


def test_move_sub_schemas_to_defs_strips_the_sub_schema_identity():
    source_root = Path(__file__).parent / "testdata" / "schema_construction"
    sub_schemas = {}
    sub_schema_refs = {}

    move_sub_schemas_to_defs(
        source_root / "schema.json", {"$ref": "file://sub_schema2.json"}, sub_schemas, sub_schema_refs
    )

    # The compiled schema is a single document so the $def cannot have its own identity
    assert "$id" not in sub_schemas["sub_schema2"]
    assert "$schema" not in sub_schemas["sub_schema2"]


def test_move_sub_schemas_to_defs_disallows_other_properties_on_reference_point():
    source_root = Path(__file__).parent / "testdata" / "schema_construction"
    with pytest.raises(AssertionError):
        move_sub_schemas_to_defs(
            source_root / "schema.json",
            {"$ref": "file://sub_schema1.json", "other": "disallowed"},
            {},
            {},
        )


def test_move_sub_schemas_to_defs_disallows_non_object_sub_schemas():
    source_root = Path(__file__).parent / "testdata" / "schema_construction"
    with pytest.raises(AssertionError):
        move_sub_schemas_to_defs(
            source_root / "schema.json",
            {"$ref": "file://invalid_sub_schema1.json"},
            {},
            {},
        )


def test_move_sub_schemas_to_defs_disallows_immediately_referencing_another_sub_schema():
    source_root = Path(__file__).parent / "testdata" / "schema_construction"
    with pytest.raises(AssertionError):
        move_sub_schemas_to_defs(
            source_root / "schema.json",
            {"$ref": "file://invalid_sub_schema2.json"},
            {},
            {},
        )


def test_move_sub_schemas_to_defs_rejects_sub_schemas_with_the_same_name():
    source_root = Path(__file__).parent / "testdata" / "schema_construction"
    sub_schemas = {}
    sub_schema_refs = {}

    move_sub_schemas_to_defs(
        source_root / "schema.json", {"$ref": "file://collision/sub.json"}, sub_schemas, sub_schema_refs
    )
    with pytest.raises(Exception, match="Multiple sub-schemas would be named"):
        move_sub_schemas_to_defs(
            source_root / "schema.json", {"$ref": "file://collision_sub.json"}, sub_schemas, sub_schema_refs
        )


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

        # Property directly in the source schema
        assert destination_schema_contents["properties"]["presentDirectly"] == {
            "type": "object",
            "additionalProperties": False,
        }

        # The referenced sub-schema is referenced through an internal $ref
        assert destination_schema_contents["properties"]["merged"] == {"$ref": "#/$defs/sub_schema1"}
        assert destination_schema_contents["$defs"]["sub_schema1"]["properties"].keys() == set(["first", "second"])
        # Objects in $defs also have additionalProperties defaulted to false
        assert destination_schema_contents["$defs"]["sub_schema1"]["additionalProperties"] is False


def test_constructs_schema_storing_repeated_sub_schemas_once():
    with tempfile.TemporaryDirectory() as destination_folder:
        source_schema = Path(__file__).parent / "testdata" / "schema_construction" / "schema_with_repeated_refs.json"
        destination_schema = Path(destination_folder) / "values.schema.json"

        construct_helm_schema(source_schema, destination_schema)

        destination_schema_contents = json.loads(destination_schema.read_text(encoding="UTF-8"))

        assert destination_schema_contents["properties"]["first"] == {"$ref": "#/$defs/sub_schema2"}
        assert destination_schema_contents["properties"]["second"] == {"$ref": "#/$defs/sub_schema2"}
        assert destination_schema_contents["$defs"]["sub_schema2"]["properties"]["nested"] == {
            "$ref": "#/$defs/sub_schema1"
        }
        assert list(destination_schema_contents["$defs"].keys()) == ["sub_schema2", "sub_schema1"]
