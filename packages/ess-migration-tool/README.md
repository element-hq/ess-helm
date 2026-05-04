<!--
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

# ESS Migration Tool

The ESS Migration Tool helps you migrate your existing Synapse and Matrix Authentication Service (MAS) configurations to Element Server Suite (ESS) Helm values format. This tool automates the conversion process, making it easier to transition to ESS while preserving your existing configuration settings.

<!-- cSpell:disable -->
<p align="center">
<picture>
  <source srcset="./assets/ess-migration-tool.gif">
  <img alt="ESS Migration Tool" width="680">
</picture>
</p>
<!-- cSpell:enable -->

## Installation

Install the migration tool, ideally using pipx:

```bash
pipx install ess-migration-tool
```
or by using uv:
```bash
uv tool install ess-migration-tool
```

## Prerequisites

Before running the migration tool, ensure you have:

1. **A Synapse configuration file**: Access to `homeserver.yaml` file from your current Synapse installation
2. **A Matrix Authentication Service configuration file (optional)**: Access to `config.yaml` file if you're already using MAS
3. **Well-Known delegation files (optional)**: Access to `.well-known/matrix/client`, `.well-known/matrix/server`, and `.well-known/matrix/support` files if you want to migrate Matrix delegation configuration
4. **Python 3.11+**: The tool requires Python 3.11 or higher
5. **Access to configuration files**: Make sure your configuration files are accessible and readable

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

### Migration with Well-Known Delegation Files

```bash
# From a directory containing client.json, server.json, support.json
ess-migration-tool --synapse-config /path/to/synapse/homeserver.yaml --well-known-dir /path/to/well-known/

# Or specify individual files
ess-migration-tool --synapse-config /path/to/synapse/homeserver.yaml \
  --well-known-client /path/to/client.json \
  --well-known-server /path/to/server.json \
  --well-known-support /path/to/support.json
```

### Advanced Options

```bash
usage: ess-migration-tool [-h] --synapse-config SYNAPSE_CONFIG [--mas-config MAS_CONFIG]
                          [--well-known-dir WELL_KNOWN_DIR] [--well-known-client WELL_KNOWN_CLIENT]
                          [--well-known-server WELL_KNOWN_SERVER] [--well-known-support WELL_KNOWN_SUPPORT]
                          [--output-dir OUTPUT_DIR] [--verbose] [--debug] [--quiet]
                          [--database-mode {existing,ess-managed}]

Migrate Matrix Stack configurations to Element Server Suite Helm values

options:
  -h, --help            show this help message and exit
  --synapse-config SYNAPSE_CONFIG
                        Path to Synapse homeserver.yaml configuration file. This is the main Synapse
                        configuration that contains server_name, database, listeners, etc.
  --mas-config MAS_CONFIG
                        Path to Matrix Authentication Service config.yaml configuration file.
  --well-known-dir WELL_KNOWN_DIR
                        Path to directory containing well-known delegation files (client.json, server.json,
                        support.json). These files configure Matrix delegation for your domain.
  --well-known-client WELL_KNOWN_CLIENT
                        Path to a well-known client delegation file (client or client.json). Takes precedence
                        over --well-known-dir if both are specified.
  --well-known-server WELL_KNOWN_SERVER
                        Path to a well-known server delegation file (server or server.json). Takes precedence
                        over --well-known-dir if both are specified.
  --well-known-support WELL_KNOWN_SUPPORT
                        Path to a well-known support delegation file (support or support.json). Takes precedence
                        over --well-known-dir if both are specified.
  --output-dir OUTPUT_DIR
                        Output directory for generated files (default: output). The migration will create Helm
                        values.yaml and any ConfigMap files in this directory.
  --verbose             Enable verbose logging. Shows detailed information about the migration process.
  --debug               Enable debug logging. Shows debug information about the migration process.
  --quiet               Disable migration summary output.
  --database-mode {existing,ess-managed}
                        Database migration mode. 'existing' to use existing database, 'ess-managed' to use ESS-
                        managed Postgres. If not specified, user will be prompted.
```

## Migration Process

The migration tool follows these steps:

1. **Loading and validating input files**: Reads and validates your Synapse, MAS, and well-known delegation configuration files
2. **Discovering secrets and extra files**: Automatically discovers secrets and extra files referenced in the configuration
3. **Migrating configuration to ESS values**: Converts your existing configuration to ESS Helm values format.
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
3. **Follow the instructions provided by the tool**: The tool will explain the next steps adjusted to your environment. You many need to adjust some steps according to your environment
4. **Verify the setup**: Follow the [ESS verification steps](https://github.com/element-hq/ess-helm#verifying-the-setup)

### Enabling Matrix Authentication Service

If your existing deployment does not support Matrix Authentication Service (MAS), after migrating to ESS,
you can use the ESS `syn2mas` feature:

See the [syn2mas documentation](https://github.com/element-hq/ess-helm/blob/main/docs/syn2mas.md) for the complete process.

## Support

For issues or questions about the migration tool:

- Create an issue in the [ESS Helm repository](https://github.com/element-hq/ess-helm/issues)
- Join the [ESS Community Matrix room](https://matrix.to/#/#ess-community:element.io)
