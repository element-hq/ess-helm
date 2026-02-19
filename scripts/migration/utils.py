# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import urllib.parse
from typing import Any

import yaml


def yaml_dump_with_pipe_for_multiline(data: Any) -> str:
    """
    Custom YAML dump that uses pipe (|) for multi-line strings.

    This function formats YAML output to use the pipe character (|) for
    multi-line string values, which is more readable and proper for Helm charts.

    Args:
        data: Data to serialize to YAML

    Returns:
        YAML string with pipe characters for multi-line strings
    """

    # Use a custom representer for strings with newlines
    def multiline_string_representer(dumper: yaml.Dumper, data: str) -> yaml.Node:
        if isinstance(data, str) and "\n" in data:
            # Use literal style (|) for multi-line strings
            return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
        else:
            # Use regular style for single-line strings
            return dumper.represent_scalar("tag:yaml.org,2002:str", data)

    # Create a custom YAML dumper
    class CustomYAMLDumper(yaml.SafeDumper):
        pass

    CustomYAMLDumper.add_representer(str, multiline_string_representer)  # type: ignore[arg-type]

    return yaml.dump(data, Dumper=CustomYAMLDumper, default_flow_style=False, sort_keys=False, width=float("inf"))


def set_nested_value(config: dict[str, Any], path: str, value: Any) -> None:
    """
    Set a value in a nested configuration at the specified path.

    Args:
        config: Configuration dictionary to modify
        path: Dot-separated path where to set the value
        value: Value to set
    """
    if "." in path:
        # Nested path
        parts = path.split(".")
        current = config

        # Navigate/create the path
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
            if not isinstance(current, dict):
                # Can't navigate further, overwrite with dict
                current = {}
                config[parts[0]] = current

        # Set the final value
        current[parts[-1]] = value
    else:
        # Direct key
        config[path] = value


def get_nested_value(config: dict[str, Any], path: str) -> Any:
    """
    Get a value from a nested configuration using dot notation.

    Args:
        config: Configuration dictionary
        path: Dot-separated path to the value

    Returns:
        The value at the specified path, or None if not found
    """
    if "." in path:
        # Nested path
        parts = path.split(".")
        current = config

        # Navigate to the value
        for part in parts:
            if part not in current:
                return None
            current = current[part]
            if not isinstance(current, dict) and part != parts[-1]:
                return None  # Can't navigate further

        return current
    else:
        # Direct key
        return config.get(path)


def remove_nested_value(config: dict[str, Any], path: str) -> None:
    """
    Remove a config value by its dot-separated path.

    Args:
        config: Configuration dictionary
        path: Dot-separated path to the value to remove
    """
    if "." in path:
        # Nested path
        parts = path.split(".")
        current = config

        # Navigate to the parent
        for part in parts[:-1]:
            if part not in current:
                return  # Path doesn't exist
            current = current[part]
            if not isinstance(current, dict):
                return  # Can't navigate further

        # Remove the final key
        final_key = parts[-1]
        if final_key in current:
            del current[final_key]
    else:
        # Direct key
        if path in config:
            del config[path]


def extract_hostname_from_url(url: str) -> str:
    """
    Extract hostname from a URL string.

    Args:
        url: URL string to parse

    Returns:
        Hostname as string if successful, None otherwise
    """
    parsed_url = urllib.parse.urlparse(url)
    return parsed_url.hostname if parsed_url.hostname else ""
