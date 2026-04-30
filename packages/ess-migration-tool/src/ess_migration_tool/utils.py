# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import logging
import os
import random
import time
import urllib.parse
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import yaml
from cryptography.hazmat.backends import default_backend

# Key detection imports (moved to module level as requested)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from .models import MigrationError, ValueSourceTracking


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


def parse_path(path: str) -> list[str]:
    """
    Parse a path string that may contain single-quoted keys with dots.

    Single-quoted keys are treated as single path components even if they contain dots.
    This allows keys containing dots to be used in paths by wrapping them in single quotes.

    Examples:
        'a.b.c' -> ['a', 'b', 'c']
        "a.'my.key'.b" -> ['a', 'my.key', 'b']
        "a.'foo.bar'.'baz.mux'" -> ['a', 'foo.bar', 'baz.mux']
        'a.b.' → ['a', 'b', '']

    Args:
        path: Path string, potentially containing single-quoted components

    Returns:
        List of path components, with quoted parts preserving their dots
    """
    if not path:
        return []

    parts: list[str] = []
    current_part: list[str] = []
    in_quotes = False

    for char in path:
        if char == "'":
            # Toggle quotes
            in_quotes = not in_quotes
        elif char == "." and not in_quotes:
            # End of current part (only split on dots outside quotes)
            parts.append("".join(current_part))
            current_part = []
            continue
        else:
            current_part.append(char)

    # Add the last part
    parts.append("".join(current_part))

    return parts


def set_nested_value(config: dict[str, Any], path: str, value: Any) -> None:
    """
    Set a value in a nested configuration at the specified path.
    Properly handles numeric indices to create/set values in arrays.
    Supports single-quoted keys containing dots (e.g., "a.'my.key'.b").

    Args:
        config: Configuration dictionary to modify
        path: Dot-separated path where to set the value. Use single quotes
              to wrap keys containing dots (e.g., "a.'my.key'.b")
        value: Value to set
    """
    parts = parse_path(path)
    if not parts:
        return

    # Handle single-part path (no nesting)
    if len(parts) == 1:
        config[parts[0]] = value
        return

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
    Supports single-quoted keys containing dots (e.g., "a.'my.key'.b").

    Args:
        path: Concrete path like "certificates.0.value" or "a.'my.key'.b"
        pattern: Pattern like "certificates.*.value" or "a.'*'.b"

    Returns:
        True if path matches pattern
    """
    path_parts = parse_path(path)
    pattern_parts = parse_path(pattern)

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
    Supports single-quoted keys containing dots (e.g., "a.'my.key'.b").

    Args:
        config: Configuration dictionary
        path: Dot-separated path to the value. Use single quotes to wrap
              keys containing dots (e.g., "a.'my.key'.b")

    Returns:
        The value at the specified path, or None if not found
    """
    parts = parse_path(path)
    if not parts:
        return None

    # Direct key (no nesting)
    if len(parts) == 1:
        return config.get(parts[0])

    # Nested path
    current = config

    # Navigate to the value
    for i, part in enumerate(parts):
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        elif isinstance(current, list):
            try:
                current = current[int(part)]
            except (IndexError, ValueError):
                return None
        elif i != len(parts) - 1:
            return None  # Can't navigate further

    return current


def remove_nested_value(config: dict[str, Any], path: str) -> None:
    """
    Remove a config value by its dot-separated path.
    Supports single-quoted keys containing dots (e.g., "a.'my.key'.b").

    Args:
        config: Configuration dictionary
        path: Dot-separated path to the value to remove. Use single quotes
              to wrap keys containing dots (e.g., "a.'my.key'.b")
    """
    parts = parse_path(path)
    if not parts:
        return

    # Direct key (no nesting)
    if len(parts) == 1:
        if parts[0] in config:
            del config[parts[0]]
        return

    # Nested path
    current = config

    # Navigate to the parent (all parts except the last)
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
    elif isinstance(current, list):
        try:
            idx = int(final_key)
            if idx < len(current):
                del current[idx]
        except ValueError:
            pass


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
    Supports single-quoted keys containing dots (e.g., "a.'my.key'.0").

    For example: ['secrets.keys.0', 'secrets.keys.1', 'secrets.keys.2'] ->
    ['secrets.keys.2', 'secrets.keys.1', 'secrets.keys.0']

    Args:
        tracked_values: List of dot-separated config paths. Use single quotes
              to wrap keys containing dots (e.g., "a.'my.key'.0")

    Returns:
        Sorted list of paths with list indices in descending order within each parent
    """
    # Separate paths: regular paths and paths ending with numeric indices
    regular_paths = []
    indexed_paths_by_parent: dict[str, list] = defaultdict(list)

    for path in tracked_values:
        parsed_parts = parse_path(path)
        if len(parsed_parts) >= 1 and parsed_parts[-1].isdigit():
            # This is a list index path like 'secrets.keys.2' or 'secrets.'my.key'.2'
            # Reconstruct parent path from all parts except the last
            parent_parts = parsed_parts[:-1]
            parent = ".".join(parent_parts)
            index = parsed_parts[-1]
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


def prompt_for_database_choice(pretty_logger: logging.Logger) -> bool:
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
    pretty_logger.info("")

    choice = prompt_choice(
        pretty_logger,
        "Please select an option [1/2] (default: 1):",
        ["Use existing database", "Install Postgres with ESS"],
        default="Use existing database",
    )

    if choice == "Use existing database":
        pretty_logger.info("   ✅ Using existing database configuration")
        return True
    else:
        pretty_logger.info("   ✅ Using ESS-managed Postgres (import database later)")
        return False


def delay_next_steps(pretty_logger: logging.Logger) -> None:
    if not is_quiet_mode(pretty_logger) and not os.environ.get("PYTEST_CURRENT_TEST"):
        time.sleep(random.uniform(0.2, 1.5))
        pretty_logger.info("")


def prompt_value(
    pretty_logger: logging.Logger,
    prompt: str,
    validator: Callable[[str], tuple[bool, str]] | None = None,
    default: str | None = None,
) -> str:
    """
    Generic function to prompt user for a text value.

    Args:
        pretty_logger: Logger for displaying prompts and messages
        prompt: The prompt message to display
        validator: Optional function that takes input string and returns (is_valid, error_message)
        default: Optional default value if user presses Enter

    Returns:
        The user's input value (stripped)

    Raises:
        MigrationError: If user cancels the operation (Ctrl+C or EOF)
    """
    while True:
        try:
            user_input = input(f"   {prompt}").strip()

            # Handle default value
            if user_input == "" and default is not None:
                return default

            # Handle empty input
            if user_input == "":
                pretty_logger.info("   ❌ Value cannot be empty. Please try again.")
                continue

            # Validate if validator is provided
            if validator is not None:
                is_valid, error_message = validator(user_input)
                if not is_valid:
                    pretty_logger.info(f"   ❌ {error_message}")
                    continue

            return user_input

        except KeyboardInterrupt as err:
            pretty_logger.info("\n   ❌ Operation cancelled by user")
            raise MigrationError("User cancelled input") from err
        except EOFError as err:
            pretty_logger.info("\n   ❌ End of input reached")
            raise MigrationError("End of input reached during prompt") from err


def prompt_choice(
    pretty_logger: logging.Logger,
    prompt: str,
    options: list[str],
    default: str | None = None,
) -> str:
    """
    Prompt user to select from a numbered list of options.

    Args:
        pretty_logger: Logger for displaying prompts and messages
        prompt: The prompt message to display
        options: List of option strings to choose from
        default: Optional default choice (value, not index). If provided and user
                 presses Enter, returns this value.

    Returns:
        The selected option string (not the index)

    Raises:
        MigrationError: If user cancels the operation (Ctrl+C or EOF)
    """
    while True:
        try:
            user_input = input(f"   {prompt}").strip()

            # Handle default
            if user_input == "" and default is not None:
                return default

            # Handle empty input without default
            if user_input == "":
                pretty_logger.info("   ❌ Please select a valid option.")
                continue

            # Try to parse as number
            try:
                choice_index = int(user_input) - 1
                if 0 <= choice_index < len(options):
                    return options[choice_index]
                else:
                    pretty_logger.info(f"   ❌ Invalid choice. Please enter a number between 1 and {len(options)}.")
            except ValueError:
                pretty_logger.info(f"   ❌ Please enter a number between 1 and {len(options)}.")

        except KeyboardInterrupt as err:
            pretty_logger.info("\n   ❌ Operation cancelled by user")
            raise MigrationError("User cancelled input") from err
        except EOFError as err:
            pretty_logger.info("\n   ❌ End of input reached")
            raise MigrationError("End of input reached during prompt") from err


def prompt_yes_no(
    pretty_logger: logging.Logger,
    prompt: str,
    default: bool | None = None,
) -> bool:
    """
    Prompt user for a yes/no answer.

    Args:
        pretty_logger: Logger for displaying prompts and messages
        prompt: The prompt message to display
        default: Optional default value if user presses Enter

    Returns:
        True for yes, False for no

    Raises:
        MigrationError: If user cancels the operation (Ctrl+C or EOF)
    """
    while True:
        try:
            user_input = input(f"   {prompt}").strip().lower()

            # Handle default
            if user_input == "" and default is not None:
                return default

            # Handle empty input without default
            if user_input == "":
                pretty_logger.info("   ❌ Please enter 'yes' or 'no'.")
                continue

            # Check for yes variations
            if user_input in ("yes", "y", "true", "t", "1"):
                return True
            # Check for no variations
            elif user_input in ("no", "n", "false", "f", "0"):
                return False
            else:
                pretty_logger.info("   ❌ Please enter 'yes' or 'no'.")

        except KeyboardInterrupt as err:
            pretty_logger.info("\n   ❌ Operation cancelled by user")
            raise MigrationError("User cancelled input") from err
        except EOFError as err:
            pretty_logger.info("\n   ❌ End of input reached")
            raise MigrationError("End of input reached during prompt") from err


def resolve_value_conflicts(
    pretty_logger: logging.Logger,
    value_source_tracking: ValueSourceTracking,
    ess_config: dict[str, Any],
) -> None:
    """Resolve conflicts where multiple strategies provide different values for same ESS path."""
    conflicts = value_source_tracking.get_conflicts()
    if not conflicts:
        return

    for ess_path, sources in sorted(conflicts.items()):
        first_value = sources[0].value
        all_same = all(str(v.value) == str(first_value) for v in sources)

        if all_same:
            logging.debug(f"Consistent values for {ess_path}: {first_value}")
            continue

        if is_quiet_mode(pretty_logger):
            logging.info(f"Conflict detected for {ess_path}, using first value: {first_value}")
            continue

        pretty_logger.info(f"\n⚠️  CONFLICT for '{ess_path}'")
        pretty_logger.info("   Multiple configurations provide different values:")
        for source in sources:
            pretty_logger.info(f"   • {source.strategy_name} ({source.source_path}): {source.value}")

        value_to_strategies: dict[str, list[str]] = {}
        for source in sources:
            value_str = str(source.value)
            value_to_strategies.setdefault(value_str, []).append(source.strategy_name)

        options = [f"{v} (from: {', '.join(ss)})" for v, ss in value_to_strategies.items()]
        options.append("Enter custom value")

        choice = prompt_choice(pretty_logger, f"Select value for '{ess_path}':", options)

        if choice == "Enter custom value":
            new_value = prompt_value(pretty_logger, "Enter custom value:")
            set_nested_value(ess_config, ess_path, new_value)
        else:
            value_str = choice.split(" (")[0]
            final_value = next((s.value for s in sources if str(s.value) == value_str), first_value)
            set_nested_value(ess_config, ess_path, final_value)

        logging.info(f"Resolved {ess_path} = {final_value}")
