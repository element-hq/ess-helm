#!/usr/bin/env python3

# Copyright 2024-2025 New Vector Ltd
# Copyright 2025 Element Creations Ltd
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


# Inline any sub-schemas referenced in other files
#
# When running `helm lint` (or other sub-commands that use the schema to validate the values)
# The relative path is relative to the current working directory rather than the schema file.
# This means that you can't use file relative refs and have `helm lint` work both for the
# parent chart and the sub-chart. We can't use HTTP as that won't work in airgapped envs, so
# inline the sub-schemas. Symlinks were tried but they were obnoxiously noisy due to
# https://helm.sh/blog/2019-10-30-helm-symlink-security-notice/. We don't want to rely on keeping
# complex sub-schemas in-sync for multiple charts/containers/etc, so use this script to merge
def inline_sub_schemas(source_schema: Path, schema_part: dict[Any]) -> dict[Any]:
    # We're currently assuming that all $refs are file relative refs.
    # This won't always be true but lets keep this as simple as we need it for now
    if "$ref" in schema_part:
        # If we're inlining a sub-schema we're only returning things from the inlined sub-schema
        assert len(schema_part.keys()) == 1

        sub_schema_ref = schema_part["$ref"]
        sub_schema = source_schema.parent / sub_schema_ref.replace("file://", "")
        if not sub_schema.exists() or not sub_schema.is_file():
            raise Exception(f"{sub_schema} does not exist relative to {source_schema}. Please appropriately create it")

        inlined_sub_schema = json.loads(sub_schema.read_text(encoding="UTF-8"))

        # It doesn't make sense for the root of the inlined sub-schema to immediately be referencing something else
        assert "$ref" not in inlined_sub_schema
        # We're only inlining objects or arrays for now to keep this easy to reason about
        assert inlined_sub_schema["type"] in ["object", "array"]

        return inlined_sub_schema

    return schema_part


# We don't want people setting values by mistake that don't do anything.
# https://json-schema.org/understanding-json-schema/reference/object#additionalproperties:
# "By default any additional properties are allowed."
def default_additionalProperties_to_off(_: Path, schema_part: dict[Any]) -> dict[Any]:
    if schema_part["type"] == "object" and "additionalProperties" not in schema_part:
        schema_part["additionalProperties"] = False

    return schema_part


def construct_helm_schema(source_schema: Path, destination_schema: Path):
    schema_manipulators = [
        lambda schema_part: inline_sub_schemas(source_schema, schema_part),
        lambda schema_part: default_additionalProperties_to_off(source_schema, schema_part),
    ]
    schema_contents = json.loads(source_schema.read_text(encoding="UTF-8"))
    for schema_manipulator in schema_manipulators:
        schema_contents = schema_walker(schema_contents, schema_manipulator)

    destination_schema.write_text(json.dumps(schema_contents, indent=2) + "\n")


def main():
    typer.run(construct_helm_schema)


if __name__ == "__main__":
    main()
