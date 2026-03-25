# Copyright 2026 Element Creations Ltd
#
# SPDX-License-Identifier: AGPL-3.0-only


"""
Helm validation utilities for ess-migration-tool tests.
Provides functions to validate generated values files against Helm templates.
"""

import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("migration")


def validate_helm_template(values: dict[str, Any]) -> tuple[bool, str]:
    """
    Validate that generated values produce valid Helm templates.

    Args:
        values: ESS values dictionary to validate

    Returns:
        Tuple of (success: bool, message: str)
        - success: True if validation passed, False if errors found
        - message: Error message if validation failed, empty string if success
    """
    try:
        # Write values to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(values, f)
            values_file = f.name

        try:
            # Run helm template command using subprocess
            # This avoids async complexity while still validating templates
            result = subprocess.run(
                [
                    "helm",
                    "template",
                    "test-validation",
                    "charts/matrix-stack",
                    "--namespace",
                    "test-validation",
                    "--values",
                    values_file,
                    "--api-versions",
                    "monitoring.coreos.com/v1/ServiceMonitor",
                    "--api-versions",
                    "cert-manager.io/v1/Certificate",
                ],
                capture_output=True,
                text=True,
                cwd="/home/arch/ess-helm",
            )

            # Check if command succeeded
            if result.returncode != 0:
                error_msg = f"Helm template failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr}"
                return False, error_msg

            # Parse the output to check for basic template structure
            templates = list(yaml.load_all(result.stdout, Loader=yaml.SafeLoader))

            # Basic validation - check that we got some templates
            if not templates:
                return False, "No templates generated - values may be invalid"

            # Check for common error patterns in templates
            error_messages = []
            for template in templates:
                if template is None:
                    continue

                if not isinstance(template, dict):
                    error_messages.append(f"Invalid template structure: {template}")
                    continue

                # Basic structure validation
                if "kind" not in template:
                    error_messages.append("Template missing 'kind' field")
                if "metadata" not in template:
                    error_messages.append("Template missing 'metadata' field")

            if error_messages:
                return False, "\n".join(error_messages)

            return True, "Helm template validation passed"

        finally:
            # Clean up temporary file
            Path(values_file).unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Helm template validation failed: {e}")
        return False, f"Helm template validation error: {e}"


def validate_helm_template_with_chart(
    values: dict[str, Any], chart_path: str = "charts/matrix-stack"
) -> tuple[bool, str]:
    """
    Validate Helm templates using a specific chart path.

    Args:
        values: ESS values dictionary to validate
        chart_path: Path to Helm chart

    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        # Write values to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.safe_dump(values, f)
            values_file = f.name

        try:
            # Run helm template command
            result = subprocess.run(
                [
                    "helm",
                    "template",
                    "test-validation",
                    chart_path,
                    "--namespace",
                    "test-validation",
                    "--values",
                    values_file,
                    "--api-versions",
                    "monitoring.coreos.com/v1/ServiceMonitor",
                    "--api-versions",
                    "cert-manager.io/v1/Certificate",
                ],
                capture_output=True,
                text=True,
                cwd="/home/arch/ess-helm",
            )

            # Check if command succeeded
            if result.returncode != 0:
                error_msg = f"Helm template failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr}"
                return False, error_msg

            return True, "Helm template generation successful"

        finally:
            # Clean up temporary file
            Path(values_file).unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Helm template validation with chart failed: {e}")
        return False, f"Helm template validation error: {e}"
