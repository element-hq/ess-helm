# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import logging
import os
import random
import time
import urllib.parse
from collections import defaultdict
from typing import Any

import yaml
from cryptography.hazmat.backends import default_backend

# Key detection imports (moved to module level as requested)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from .models import MigrationError


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
    Properly handles numeric indices to create/set values in arrays.

    Args:
        config: Configuration dictionary to modify
        path: Dot-separated path where to set the value
        value: Value to set
    """
    if "." not in path:
        config[path] = value
        return

    parts = path.split(".")
    current: dict[str, Any] | list[Any] = config

    for i, part in enumerate(parts[:-1]):
        next_part = parts[i + 1] if i + 1 < len(parts) else None

        if isinstance(current, list):
            # Current is a list, treat part as integer index
            try:
                idx = int(part)
            except ValueError:
                return  # Invalid index
            # Extend list if needed
            while idx >= len(current):
                current.append(None)
            if current[idx] is None:
                # Create appropriate type for next level
                current[idx] = [] if (next_part and next_part.isdigit()) else {}
            current = current[idx]

        elif isinstance(current, dict):
            if part in current:
                # Already exists, navigate to it
                current = current[part]
            else:
                # Create new structure
                # If next part is numeric, create a list here (for array indices)
                # Otherwise create a dict
                if next_part and next_part.isdigit():
                    current[part] = []
                else:
                    current[part] = {}
                current = current[part]
        else:
            # Can't navigate further, start over
            current = {}
            config[parts[0]] = current

    # Set final value
    final_part = parts[-1]
    if isinstance(current, list):
        try:
            idx = int(final_part)
        except ValueError:
            return
        while idx >= len(current):
            current.append(None)
        current[idx] = value
    else:
        current[final_part] = value


def is_wildcard_pattern(pattern: str) -> bool:
    """Check if a path pattern contains a wildcard."""
    return "*" in pattern


def path_matches_pattern(path: str, pattern: str) -> bool:
    """
    Check if a concrete path matches a wildcard pattern.

    The wildcard `*` in the pattern matches exactly one path component.
    All other components must match exactly.

    Args:
        path: Concrete path like "certificates.0.value"
        pattern: Pattern like "certificates.*.value"

    Returns:
        True if path matches pattern
    """
    path_parts = path.split(".")
    pattern_parts = pattern.split(".")

    if len(path_parts) != len(pattern_parts):
        return False

    for path_part, pattern_part in zip(path_parts, pattern_parts, strict=True):
        if pattern_part == "*":
            continue
        elif path_part != pattern_part:
            return False

    return True


def find_matching_schema_key(path: str, schema: dict[str, Any]) -> str | None:
    """
    Find a schema key that matches the given concrete path.

    Checks for exact match first, then wildcard pattern match.

    Args:
        path: Concrete path like "matrixAuthenticationService.certificates.0.value"
        schema: Dict of {schema_key: SecretConfig}

    Returns:
        The matching schema key (exact or wildcard pattern), or None
    """
    if path in schema:
        return path

    for schema_key in schema:
        if is_wildcard_pattern(schema_key) and path_matches_pattern(path, schema_key):
            return schema_key

    return None


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


def extract_hostname_from_url(_, url: str, **kwargs: Any) -> str:
    """
    Extract hostname from a URL string.

    Args:
        url: URL string to parse
        **kwargs: Optional context parameters (unused)

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


def detect_key_type(content: bytes) -> str:
    """
    Detect the type of a cryptographic key from its content.

    Args:
        content: Binary content of the key file

    Returns:
        String indicating key type: "rsa", "ecdsaPrime256v1", "ecdsaSecp256k1", "ecdsaSecp384r1", or "unknown"
    """
    try:
        # Try to load as PEM first (check for PEM headers)
        if b"-----BEGIN" in content:
            key = serialization.load_pem_private_key(content, password=None, backend=default_backend())
        else:
            # Try as DER format
            key = serialization.load_der_private_key(content, password=None, backend=default_backend())

        # Determine key type
        if isinstance(key, rsa.RSAPrivateKey):
            return "rsa"
        elif isinstance(key, ec.EllipticCurvePrivateKey):
            # Check curve type
            if key.curve.name == "secp256r1":
                return "ecdsaPrime256v1"
            elif key.curve.name == "secp256k1":
                return "ecdsaSecp256k1"
            elif key.curve.name == "secp384r1":
                return "ecdsaSecp384r1"

        # Unknown key type
        return "unknown"

    except ImportError:
        # cryptography library not available
        return "unknown"
    except Exception:
        # Any other error (invalid format, corrupted data, etc.)
        return "unknown"


def is_quiet_mode(pretty_logger: logging.Logger) -> bool:
    """
    Check if quiet mode is enabled by examining the logger level.

    In the migration tool, quiet mode is indicated by setting the pretty_logger
    level to logging.CRITICAL, which suppresses all summary output.

    Args:
        pretty_logger: The pretty logger instance to check

    Returns:
        True if quiet mode is enabled (logger level is CRITICAL), False otherwise
    """
    return pretty_logger.level == logging.CRITICAL


def sort_tracked_values_for_filtering(tracked_values: list[str]) -> list[str]:
    """
    Sort tracked values so that list indices are processed in descending order.
    This prevents the list shifting problem when removing indices sequentially.

    For example: ['secrets.keys.0', 'secrets.keys.1', 'secrets.keys.2'] ->
    ['secrets.keys.2', 'secrets.keys.1', 'secrets.keys.0']

    Args:
        tracked_values: List of dot-separated config paths

    Returns:
        Sorted list of paths with list indices in descending order within each parent
    """
    # Separate paths: regular paths and paths ending with numeric indices
    regular_paths = []
    indexed_paths_by_parent: dict[str, list] = defaultdict(list)

    for path in tracked_values:
        parts = path.rsplit(".", 1)
        if len(parts) == 2 and parts[1].isdigit():
            # This is a list index path like 'secrets.keys.2'
            parent, index = parts
            indexed_paths_by_parent[parent].append((int(index), path))
        else:
            regular_paths.append(path)

    # Sort indexed paths by parent (sorted for determinism), then by index descending
    sorted_indexed: list[str] = []
    for parent in sorted(indexed_paths_by_parent.keys()):
        sorted_indexed.extend(
            path for _, path in sorted(indexed_paths_by_parent[parent], key=lambda x: x[0], reverse=True)
        )

    return regular_paths + sorted_indexed


def prompt_for_database_choice(pretty_logger) -> bool:
    """
    Prompt user to choose between using existing database or ESS-managed Postgres.

    Returns:
        True if user wants to use existing database, False for ESS-managed Postgres
    """
    pretty_logger.info("\n" + "=" * 60)
    pretty_logger.info("🗃️  DATABASE CONFIGURATION CHOICE")
    pretty_logger.info("=" * 60)
    pretty_logger.info("How would you like to handle the database for your ESS deployment?")
    pretty_logger.info("")
    pretty_logger.info("1. 🔗 Connect to existing database (recommended for production)")
    pretty_logger.info("   - Import your current database settings into ESS")
    pretty_logger.info("   - Continue using your existing PostgreSQL instance")
    pretty_logger.info("")
    pretty_logger.info("2. 🆕 Install Postgres with ESS and import database later")
    pretty_logger.info("   - Let ESS deploy and manage PostgreSQL")
    pretty_logger.info("   - Import your Synapse and MAS database schemas after deployment")
    pretty_logger.info("   - Recommended for testing/new installations")
    pretty_logger.info("")

    while True:
        try:
            choice = input("   Please select an option [1/2] (default: 1): ").strip()
            if choice == "" or choice == "1":
                pretty_logger.info("   ✅ Using existing database configuration")
                return True
            elif choice == "2":
                pretty_logger.info("   ✅ Using ESS-managed Postgres (import database later)")
                return False
            else:
                pretty_logger.info("   ❌ Invalid choice. Please enter 1 or 2.")
        except KeyboardInterrupt as err:
            pretty_logger.info("\n   ❌ Operation cancelled by user")
            raise MigrationError("User cancelled database choice") from err
        except EOFError as err:
            pretty_logger.info("\n   ❌ End of input reached")
            raise MigrationError("End of input during database choice") from err


def delay_next_steps(pretty_logger: logging.Logger) -> None:
    if not is_quiet_mode(pretty_logger) and not os.environ.get("PYTEST_CURRENT_TEST"):
        time.sleep(random.uniform(0.2, 1.5))
        pretty_logger.info("")
