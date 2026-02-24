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
            if isinstance(current, dict):
                if part not in current:
                    current[part] = {}
                current = current[part]
            elif isinstance(current, list):
                if int(part) > len(current):
                    # Create missing list items
                    current.extend([None] * (int(part) - len(current) + 1))
                current = current[int(part)]
            else:
                # Can't navigate further, overwrite with dict
                current = {}
                config[parts[0]] = current

        if isinstance(current, list):
            current[int(parts[-1])] = value
        else:
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
            if isinstance(current, dict):
                if part not in current:
                    return None
                current = current[part]
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (IndexError, ValueError):
                    return None
            elif part != parts[-1]:
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
            if isinstance(current, dict):
                if part not in current:
                    return
                current = current[part]
            elif isinstance(current, list):
                try:
                    current = current[int(part)]
                except (IndexError, ValueError):
                    return

        # Remove the final key
        final_key = parts[-1]

        if isinstance(current, dict) and final_key in current:
            del current[final_key]
        elif isinstance(current, list) and int(final_key) < len(current):
            del current[int(final_key)]
    else:
        # Direct key
        if path in config:
            del config[path]


def extract_hostname_from_url(_, url: str) -> str:
    """
    Extract hostname from a URL string.

    Args:
        url: URL string to parse

    Returns:
        Hostname as string if successful, None otherwise
    """
    parsed_url = urllib.parse.urlparse(url)
    return parsed_url.hostname if parsed_url.hostname else ""


def to_kebab_case(name: str) -> str:
    """
    Convert a resource name to a Kubernetes resource name.

    Args:
        name: Resource name

    Returns:
        Kubernetes resource name
    """
    return "".join(["-" + c.lower() if c.isupper() else c for c in name]).lstrip("-")
