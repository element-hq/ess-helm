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

from .utils import yaml_dump_with_pipe_for_multiline

logger = logging.getLogger("migration")


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

    logger.info(f"Migration outputs written successfully to {output_dir}")
    logger.info(f"- Helm values: {values_path}")


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
