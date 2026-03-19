<!--
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

# ESS Migration Tool

The ESS Migration Tool helps you migrate your existing Synapse and Matrix Authentication Service (MAS) configurations to Element Server Suite (ESS) Helm values format. This tool automates the conversion process, making it easier to transition to ESS while preserving your existing configuration settings.

## Installation

Install the migration tool using pip:

```bash
pip install ess-migration-tool
```

## Prerequisites

Before running the migration tool, ensure you have:

1. **A Synapse configuration file**: A readable `homeserver.yaml` file from your current Synapse installation
2. **A Matrix Authentication Service configuration file (optional)**: A `config.yaml` file if you're already using MAS
3. **Python 3.11+**: The tool requires Python 3.11 or higher
4. **Access to configuration files**: Make sure your configuration files are accessible and readable

If the tool has access to the secrets referenced in the configuration files, the tool will automatically discover and use them in
the resulting output files. If it does not have access to the secrets, it will prompt you to provide them manually.

## Usage

### Basic Migration (Synapse only)

```bash
ess-migration-tool --synapse-config /path/to/synapse/homeserver.yaml
```

### Migration with Matrix Authentication Service

```bash
ess-migration-tool --synapse-config /path/to/synapse/homeserver.yaml --mas-config /path/to/mas/config.yaml
```

### Advanced Options

```bash
# Verbose output for debugging
ess-migration-tool --synapse-config synapse.yaml --verbose

# Custom output directory
ess-migration-tool --synapse-config synapse.yaml --output-dir my-migration-output

# Debug logging
ess-migration-tool --synapse-config synapse.yaml --debug

# Quiet mode (minimal output) - This will fail if secrets or extra files cannot be automatically discovered
ess-migration-tool --synapse-config synapse.yaml --quiet
```

## Migration Process

The migration tool follows these steps:

1. **Loading and validating input files**: Reads and validates your Synapse and MAS configuration files
2. **Discovering secrets and extra files**: Automatically discovers secrets and extra files referenced in the configuration
3. **Migrating configuration to ESS values**: Converts your existing configuration to ESS Helm values format
5. **Writing output files**: Write the `values.yaml`, ConfigMaps, and Secrets to the output directory

## Output Files

The tool generates the following files in the output directory:

- `values.yaml`: Main Helm values file for ESS deployment
- ConfigMap files: Additional Kubernetes ConfigMaps containing additional extra files (emails templates etc...)
- Secrets files: Kubernetes Secrets containing secrets discovered in the configuration files

## Post-Migration Steps

After running the migration tool:

1. **Review the generated files**: Check the output directory for the generated `values.yaml` and other files
2. **Customize as needed**: Modify the values to match your specific requirements
3. **Deploy ESS Helm Chart**: Use the generated values file with the ESS Helm chart:

```bash
kubectl create namespace ess
kubectl apply -f output/*-secret.yaml -n ess
kubectl apply -f output/*-configmap.yaml -n ess
helm upgrade --install --namespace "ess" ess oci://ghcr.io/element-hq/ess-helm/matrix-stack -f output/values.yaml
```

4. **Verify the setup**: Follow the [ESS verification steps](https://github.com/element-hq/ess-helm#verifying-the-setup)

### Enabling Matrix Authentication Service

If your existing deployment does not support Matrix Authentication Service (MAS), after migrating to ESS,
you can use the ESS `syn2mas` feature:

See the [syn2mas documentation](https://github.com/element-hq/ess-helm/blob/main/docs/syn2mas.md) for the complete process.

## Support

For issues or questions about the migration tool:

- Create an issue in the [ESS Helm repository](https://github.com/element-hq/ess-helm/issues)
- Join the [ESS Community Matrix room](https://matrix.to/#/#ess-community:element.io)
