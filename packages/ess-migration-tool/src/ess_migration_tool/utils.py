# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


import logging
import random
import time
import urllib.parse
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
    if not is_quiet_mode(pretty_logger):
        time.sleep(random.uniform(0.2, 1.5))
        pretty_logger.info("")
