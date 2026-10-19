#!/usr/bin/env python3

# Copyright 2024-2025 New Vector Ltd
# Copyright 2025-2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer


# Implements the visitor pattern over a JSON schema to return a mutated JSON schema.
#
# For a given JSON schema fragment a function will be called to either mutate or remove
# this schema fragment (or parts of it).
# - For schema fragments that are objects, each sub-property will be recursively mutated
#   after the fragment itself has been mutated
# - For schema fragments that are arrays, the type of the array will be recursively mutated
#   after the fragment itself has been mutated
# - For schema fragments that are scalars, the value after mutation is simply returned
def schema_walker(schema_part: dict[Any], callable: Callable[[dict[any]], dict[any]]) -> dict[Any]:
    result = callable(schema_part.copy())
    if result is None:
        return None

    # This is an object, so look at all its properties recursively
    if "properties" in result:
        updated_properties = {}
        for property in result["properties"]:
            walked_property = schema_walker(result["properties"][property], callable)
            # Skip re-adding properties that have been removed by the callable
            if walked_property is not None:
                updated_properties[property] = walked_property
        result["properties"] = updated_properties
    # This is an array so look at the definition of the array items
    elif "items" in result:
        result["items"] = schema_walker(result["items"], callable)
    return result


# Move any sub-schemas referenced in other files into the $defs of the compiled schema
#
# When running `helm lint` (or other sub-commands that use the schema to validate the values)
# The relative path is relative to the current working directory rather than the schema file.
# This means that you can't use file relative refs and have `helm lint` work both for the
# parent chart and the sub-chart. We can't use HTTP as that won't work in airgapped envs, so
# the sub-schemas are collected in the $defs of the compiled schema and referenced with
# internal $refs. Symlinks were tried but they were obnoxiously noisy due to
# https://helm.sh/blog/2019-10-30-helm-symlink-security-notice/. We don't want to rely on keeping
# complex sub-schemas in-sync for multiple charts/containers/etc, so use this script to merge
def move_sub_schemas_to_defs(
    source_schema: Path,
    schema_part: dict[Any],
    sub_schemas: dict[str, dict[Any]],
    sub_schema_refs: dict[str, str],
) -> dict[Any]:
    # We're currently assuming that all $refs are file relative refs.
    # This won't always be true but lets keep this as simple as we need it for now
    if "$ref" in schema_part:
        # Internal $refs point at $defs of the compiled schema, so there is nothing to move
        if not schema_part["$ref"].startswith("file://"):
            return schema_part

        # If we're referencing a sub-schema we only return a reference to the matching $def
        assert len(schema_part.keys()) == 1

        sub_schema_ref = schema_part["$ref"]
        sub_schema_path = sub_schema_ref.replace("file://", "")
        sub_schema_file = source_schema.parent / sub_schema_path
        sub_schema_name = sub_schema_path.removesuffix(".json").replace("/", "_")

        # A sub-schema referenced multiple times only needs to be stored in $defs once
        if sub_schema_name in sub_schemas:
            if sub_schema_refs[sub_schema_name] != sub_schema_path:
                raise Exception(f"Multiple sub-schemas would be named {sub_schema_name}. Please rename one of them")

            return {"$ref": f"#/$defs/{sub_schema_name}"}

        if not sub_schema_file.exists() or not sub_schema_file.is_file():
            raise Exception(
                f"{sub_schema_file} does not exist relative to {source_schema}. Please appropriately create it"
            )

        inlined_sub_schema = json.loads(sub_schema_file.read_text(encoding="UTF-8"))

        # It doesn't make sense for the root of the sub-schema to immediately be referencing something else
        assert "$ref" not in inlined_sub_schema

        # A $def cannot have its own identity. An $id would change the base URI that
        # internal $refs inside the $def resolve against
        inlined_sub_schema.pop("$id", None)
        inlined_sub_schema.pop("$schema", None)

        # We're only moving objects or arrays into $defs for now to keep this easy to reason about
        assert inlined_sub_schema["type"] in ["object", "array"]

        # Reserve the name before walking so that a sub-schema can reference itself
        sub_schemas[sub_schema_name] = {}
        sub_schema_refs[sub_schema_name] = sub_schema_path
        # The sub-schema may itself reference further sub-schemas, these are moved into $defs too
        sub_schemas[sub_schema_name] = schema_walker(
            inlined_sub_schema,
            lambda part: move_sub_schemas_to_defs(source_schema, part, sub_schemas, sub_schema_refs),
        )

        return {"$ref": f"#/$defs/{sub_schema_name}"}

    return schema_part


# We don't want people setting values by mistake that don't do anything.
# https://json-schema.org/understanding-json-schema/reference/object#additionalproperties:
# "By default any additional properties are allowed."
def default_additionalProperties_to_off(_: Path, schema_part: dict[Any]) -> dict[Any]:
    # A schema part that only references a $def cannot have additional properties
    if "$ref" in schema_part:
        return schema_part

    if schema_part["type"] == "object" and "additionalProperties" not in schema_part:
        schema_part["additionalProperties"] = False

    return schema_part


def construct_helm_schema(source_schema: Path, destination_schema: Path):
    sub_schemas: dict[str, dict[Any]] = {}
    sub_schema_refs: dict[str, str] = {}
    schema_manipulators = [
        lambda schema_part: move_sub_schemas_to_defs(source_schema, schema_part, sub_schemas, sub_schema_refs),
        lambda schema_part: default_additionalProperties_to_off(source_schema, schema_part),
    ]
    schema_contents = json.loads(source_schema.read_text(encoding="UTF-8"))
    for schema_manipulator in schema_manipulators:
        schema_contents = schema_walker(schema_contents, schema_manipulator)
        # The collected sub-schemas are not part of the walked schema, so apply the manipulators to them too
        for sub_schema_name in sub_schemas:
            sub_schemas[sub_schema_name] = schema_walker(sub_schemas[sub_schema_name], schema_manipulator)
    if sub_schemas:
        schema_contents["$defs"] = sub_schemas

    destination_schema.write_text(json.dumps(schema_contents, indent=2) + "\n")


def main():
    typer.run(construct_helm_schema)


if __name__ == "__main__":
    main()
