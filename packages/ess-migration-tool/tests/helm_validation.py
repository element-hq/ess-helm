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
            )

            # Check if command succeeded
            if result.returncode != 0:
                error_msg = f"Helm template failed with return code {result.returncode}"
                if result.stderr:
                    error_msg += f": {result.stderr}"
            for res_line in result.stdout.split("\n"):
                if "\[INFO\] Fail:" in result.stdout:
                    error_msg += res_line + "\n"
                if "\[INFO\] Missing required value" in result.stdout:
                    error_msg += res_line + "\n"
            if error_msg:
                return False, f"Helm template validation failed: {error_msg}"

            # Parse the output to check for basic template structure
            try:
                list(yaml.load_all(result.stdout, Loader=yaml.SafeLoader))
                return True, "Helm template validation passed"
            except yaml.YAMLError as e:
                return False, f"YAML error in Helm template output: {e}"
        finally:
            # Clean up temporary file
            Path(values_file).unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Helm template validation failed: {e}")
        return False, f"Helm template validation error: {e}"
