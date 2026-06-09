# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import logging
import os
import urllib.parse
from collections import defaultdict
from collections.abc import Callable
from typing import Any

import yaml
from cryptography.hazmat.backends import default_backend

# Key detection imports (moved to module level as requested)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from .models import GlobalOptions, MigrationError
from .rich_output import get_console, is_rich_enabled, print_prompt, print_section


def parse_postgres_uri(uri: str) -> dict[str, Any]:
    """
    Parse a PostgreSQL connection URI and extract database configuration.

    Args:
        uri: PostgreSQL connection URI (e.g., "postgresql://user:pass@host:port/db?sslmode=prefer")

    Returns:
        Dictionary with database configuration fields (port is returned as int)
    """
    if not uri or not uri.startswith("postgresql://"):
        return {}

    try:
        # Parse the URI
        parsed = urllib.parse.urlparse(uri)

        # Build result dictionary only with fields that are actually present
        result: dict[str, str | int | None] = {}

        if parsed.hostname:
            result["host"] = parsed.hostname

        if parsed.port:
            result["port"] = int(parsed.port)

        if parsed.username:
            result["user"] = parsed.username

        if parsed.password:
            result["password"] = parsed.password

        if parsed.path:
            result["name"] = parsed.path.lstrip("/")

        # Extract SSL mode from query parameters (only if present)
        if parsed.query:
            query_params = urllib.parse.parse_qs(parsed.query)
            if "sslmode" in query_params:
                result["ssl"] = query_params["sslmode"][0]

        return result
    except Exception as e:
        logging.warning(f"Failed to parse PostgreSQL URI '{uri}': {e}")
        return {}


def extract_port_from_uri(_, uri: str, **kwargs: Any) -> int | None:
    """
    Extract port from PostgreSQL URI, returning None if not present.

    Args:
        uri: PostgreSQL connection URI
        **kwargs: Optional context parameters (unused)

    Returns:
        Port as integer if present, None otherwise
    """
    parsed = parse_postgres_uri(uri)
    port = parsed.get("port")
    return int(port) if port is not None else None


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
        def ignore_aliases(self, data: Any) -> bool:
            return True

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


def remove_nested_value(config: dict[str, Any], path: str, remove_empty_parent: bool = False) -> None:
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

    if remove_empty_parent and not current:
        formatted_parts = [f"'{part}'" if "." in part else part for part in parts[:-1]]
        remove_nested_value(config, ".".join(formatted_parts), remove_empty_parent)


def extract_hostname_from_url(_, url: str, **kwargs: Any) -> str:
    """
    Extract hostname from a URL string or host:port string.

    Args:
        url: URL string or host:port string to parse
        **kwargs: Optional context parameters (unused)

    Returns:
        Hostname as string if successful, empty string otherwise
    """
    if not url:
        return ""
    # Prepend // if no scheme and contains : (host:port format e.g., "example.com:443")
    # or if no :// at all (bare hostname e.g., "example.com")
    if "://" not in url:
        url = f"//{url}"
    parsed = urllib.parse.urlparse(url)
    return parsed.hostname or ""


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


def prompt_for_database_choice(summary_logger: logging.Logger, global_options: GlobalOptions) -> bool:
    """
    Prompt user to choose between using existing database or ESS-managed PostgreSQL.

    Returns:
        True if user wants to use existing database, False for ESS-managed PostgreSQL
    """
    if global_options.quiet_mode:
        raise MigrationError("Quiet mode is enabled. Cannot prompt for database choice.")

    print_section("🗃️  DATABASE CONFIGURATION CHOICE", logger=summary_logger)
    print_prompt(
        "How would you like to handle the database for your ESS deployment?",
        style="bold white",
        logger=summary_logger,
        prefix="",
    )
    print_prompt("", logger=summary_logger)

    print_prompt(
        "1. 🔗 Connect to existing database (recommended for production)",
        style="bold cyan",
        logger=summary_logger,
        prefix="",
    )
    print_prompt("- Import your current database settings into ESS", style="dim", logger=summary_logger, prefix="   ")
    print_prompt("- Continue using your existing PostgreSQL instance", style="dim", logger=summary_logger, prefix="   ")
    print_prompt("", logger=summary_logger)
    print_prompt(
        "2. 🆕 Install PostgreSQL with ESS and import database later", style="white", logger=summary_logger, prefix=""
    )
    print_prompt("- Let ESS deploy and manage PostgreSQL", style="dim", logger=summary_logger, prefix="   ")
    print_prompt(
        "- Import your Synapse and MAS database schemas after deployment",
        style="dim",
        logger=summary_logger,
        prefix="   ",
    )
    print_prompt("", logger=summary_logger)

    choice = prompt_choice(
        summary_logger,
        "Please select an option [1/2] (default: 1):",
        ["Use existing database", "Install PostgreSQL with ESS"],
        default="Use existing database",
        global_options=global_options,
    )

    if choice == "Use existing database":
        print_prompt("✅ Using existing database configuration", style="bold green", logger=summary_logger)
        return True
    else:
        print_prompt(
            "✅ Using ESS-managed PostgreSQL (import database later)", style="bold green", logger=summary_logger
        )
        return False


def press_enter_to_continue(summary_logger: logging.Logger, global_options: GlobalOptions) -> None:
    if not global_options.quiet_mode and not os.environ.get("PYTEST_CURRENT_TEST"):
        print_prompt("Press Enter to continue...", logger=summary_logger)
        if is_rich_enabled():
            get_console().input()
        else:
            input()


def prompt_value(
    summary_logger: logging.Logger,
    prompt: str,
    global_options: GlobalOptions,
    validator: Callable[[str], tuple[bool, str]] | None = None,
    default: str | None = None,
) -> str:
    """
    Generic function to prompt user for a text value.

    Args:
        summary_logger: Logger for displaying prompts and messages
        prompt: The prompt message to display
        validator: Optional function that takes input string and returns (is_valid, error_message)
        default: Optional default value if user presses Enter

    Returns:
        The user's input value (stripped)

    Raises:
        MigrationError: If user cancels the operation (Ctrl+C or EOF)
    """
    if global_options.quiet_mode:
        raise MigrationError("Quiet mode is enabled. Cannot prompt for value.")

    while True:
        try:
            # Display prompt with Rich if available
            user_input = get_console().input(prompt).strip() if is_rich_enabled() else input(f"   {prompt}").strip()

            # Handle default value
            if user_input == "" and default is not None:
                return default

            # Handle empty input
            if user_input == "":
                print_prompt("❌ Value cannot be empty. Please try again.", style="bold red", logger=summary_logger)
                continue

            # Validate if validator is provided
            if validator is not None:
                is_valid, error_message = validator(user_input)
                if not is_valid:
                    print_prompt(f"❌ {error_message}", style="bold red", logger=summary_logger)
                    continue

            return user_input

        except KeyboardInterrupt as err:
            print_prompt("\n❌ Operation cancelled by user", style="bold red", logger=summary_logger, prefix="")
            raise MigrationError("User cancelled input") from err
        except EOFError as err:
            print_prompt("\n❌ End of input reached", style="bold red", logger=summary_logger, prefix="")
            raise MigrationError("End of input reached during prompt") from err


def prompt_choice(
    summary_logger: logging.Logger,
    prompt: str,
    options: list[str],
    global_options: GlobalOptions,
    default: str | None = None,
) -> str:
    """
    Prompt user to select from a numbered list of options.

    Args:
        summary_logger: Logger for displaying prompts and messages
        prompt: The prompt message to display
        options: List of option strings to choose from
        default: Optional default choice (value, not index). If provided and user
                 presses Enter, returns this value.

    Returns:
        The selected option string (not the index)

    Raises:
        MigrationError: If user cancels the operation (Ctrl+C or EOF)
    """
    if global_options.quiet_mode:
        raise MigrationError("Quiet mode is enabled. Cannot prompt for choice.")

    while True:
        try:
            # Display prompt with Rich if available
            user_input = get_console().input(prompt) if is_rich_enabled() else input(f"   {prompt}").strip()

            # Handle default
            if user_input == "" and default is not None:
                return default

            # Handle empty input without default
            if user_input == "":
                print_prompt("❌ Please select a valid option.", style="bold red", logger=summary_logger)
                continue

            # Try to parse as number
            try:
                choice_index = int(user_input) - 1
                if 0 <= choice_index < len(options):
                    return options[choice_index]
                else:
                    print_prompt(
                        f"❌ Invalid choice. Please enter a number between 1 and {len(options)}.",
                        style="bold red",
                        logger=summary_logger,
                    )
            except ValueError:
                print_prompt(
                    f"❌ Please enter a number between 1 and {len(options)}.",
                    style="bold red",
                    logger=summary_logger,
                )

        except KeyboardInterrupt as err:
            print_prompt("\n❌ Operation cancelled by user", style="bold red", logger=summary_logger, prefix="")
            raise MigrationError("User cancelled input") from err
        except EOFError as err:
            print_prompt("\n❌ End of input reached", style="bold red", logger=summary_logger, prefix="")
            raise MigrationError("End of input reached during prompt") from err


def prompt_yes_no(
    summary_logger: logging.Logger,
    prompt: str,
    global_options: GlobalOptions,
    default: bool | None = None,
) -> bool:
    """
    Prompt user for a yes/no answer.

    Args:
        summary_logger: Logger for displaying prompts and messages
        prompt: The prompt message to display
        default: Optional default value if user presses Enter

    Returns:
        True for yes, False for no

    Raises:
        MigrationError: If user cancels the operation (Ctrl+C or EOF)
    """
    if global_options.quiet_mode:
        raise MigrationError("Quiet mode is enabled. Cannot prompt for input.")

    while True:
        try:
            # Display prompt with Rich if available
            if is_rich_enabled():
                user_input = get_console().input(prompt).strip().lower()
            else:
                user_input = input(f"   {prompt}").strip().lower()

            # Handle default
            if user_input == "" and default is not None:
                return default

            # Handle empty input without default
            if user_input == "":
                print_prompt("❌ Please enter 'yes' or 'no'.", style="bold red", logger=summary_logger)
                continue

            # Check for yes variations
            if user_input in ("yes", "y", "true", "t", "1"):
                return True
            # Check for no variations
            elif user_input in ("no", "n", "false", "f", "0"):
                return False
            else:
                print_prompt("❌ Please enter 'yes' or 'no'.", style="bold red", logger=summary_logger)

        except KeyboardInterrupt as err:
            print_prompt("\n❌ Operation cancelled by user", style="bold red", logger=summary_logger, prefix="")
            raise MigrationError("User cancelled input") from err
        except EOFError as err:
            print_prompt("\n❌ End of input reached", style="bold red", logger=summary_logger, prefix="")
            raise MigrationError("End of input reached during prompt") from err
