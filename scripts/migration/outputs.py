# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Output generation module for the migration script.
Handles creation of Helm values and Kubernetes resources.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

from .models import Secret
from .utils import yaml_dump_with_pipe_for_multiline

logger = logging.getLogger("migration")


def generate_secrets(secrets: list[Secret]) -> list[dict[str, Any]]:
    """
    Generate Kubernetes Secret manifests.

    Args:
        secrets: List of Secret dataclass instances

    Returns:
        List of Secret manifests in dictionary format
    """
    return [secret.to_manifest() for secret in secrets]


def generate_helm_values(ess_values: dict[str, Any]) -> str:
    """
    Generate Helm values.yaml content from ESS values dictionary.

    Args:
        ess_values: ESS values dictionary

    Returns:
        YAML string suitable for values.yaml
    """
    # Use the same YAML dumping logic as yaml_dump_with_pipe_for_multiline
    # for consistency across the codebase
    return yaml_dump_with_pipe_for_multiline(ess_values)


def write_outputs(
    helm_values: str,
    secrets: list[Secret],
    output_dir: str = "output",
) -> None:
    """
    Write migration outputs to files.

    Args:
        helm_values: Helm values YAML content
        output_dir: Directory to write outputs to
    """
    # Validate and create output directory
    _create_output_dir(output_dir)

    # Write Helm values with error handling
    values_path = _write_helm_values(helm_values, output_dir)

    # Write Secrets with error handling
    written_secrets = _write_secrets(secrets, output_dir)

    logger.info(f"Migration outputs written successfully to {output_dir}")
    logger.info(f"- Helm values: {values_path}")
    for secret_path in written_secrets:
        logging.info(f"- Secret: {secret_path}")


def _create_output_dir(output_dir: str) -> None:
    """
    Validate and create output directory.

    Args:
        output_dir: Directory path to validate and create
    """
    dir_path = Path(output_dir)

    # Create directory with parents
    dir_path.mkdir(parents=True, exist_ok=True)
    logger.info(f"Created output directory: {output_dir}")


def _write_secrets(secrets: list[Secret], output_dir: str) -> list[str]:
    """
    Write Secret manifests to files with error handling.

    Args:
        secrets: List of Secret manifests
        output_dir: Output directory path

    Returns:
        List of paths to written Secret files

    Raises:
        OutputError: If file writing fails
    """
    written_files: list[str] = []

    if not secrets:
        logging.info("No Secrets to write")
        return written_files

    for i, secret in enumerate(secrets):
        try:
            secret_name = secret.name
            secret_path = Path(output_dir) / f"{secret_name}-secret.yaml"

            # Write Secret file
            with open(secret_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(secret.to_manifest(), f, sort_keys=False)

            written_files.append(str(secret_path))
            logging.info(f"Secret written to {secret_path}")

        except Exception as e:
            logging.error(f"Failed to write Secret {i}: {e}")
            # Continue with other Secrets even if one fails
            continue

    return written_files


def _write_helm_values(helm_values: str, output_dir: str) -> str:
    """
    Write Helm values to file with error handling.

    Args:
        helm_values: Helm values YAML content
        output_dir: Output directory path

    Returns:
        Path to the written values file
    """
    values_path = Path(output_dir) / "values.yaml"

    # Write file with error handling
    with open(values_path, "w", encoding="utf-8") as f:
        f.write(helm_values)

    logger.info(f"Helm values written to {values_path}")
    return str(values_path)
