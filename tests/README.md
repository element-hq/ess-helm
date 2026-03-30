<!--
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

# ESS Community Integration Tests

## Overview
The ESS Community Integration Tests project is designed to facilitate the testing of components against Element Server Suite. It provides a command-line interface (CLI) to run ESS integration tests.

## Features
- Set up a Kubernetes cluster for testing.
- Run integration tests for ESS using predefined test suites.
- Customize test runs with additional values files.

## Prerequisites
- Python 3.11 or higher
- Docker
- [k3d](https://k3d.io/stable/)
- [Helm](https://helm.sh/docs/intro/install)
- Optional: [uv](https://docs.astral.sh/uv/getting-started/installation/) to install from git

## Installation


```sh
pipx install ess-community-integration-tests
uvx ess-community-integration-tests
```

You can also install it from the git repository :

```sh
# You can also use any ESS Community version
VERSION=main
uv tool install git+https://github.com/element-hq/ess-helm.git@$VERSION#subdirectory=tests
```

Example:

```sh
VERSION=main
uv tool install git+https://github.com/element-hq/ess-helm.git@$VERSION#subdirectory=tests
    Updated https://github.com/element-hq/ess-helm.git (d6d33a7f7051a0b6bbdcc609a059ae328feee269)
      Built ess-community-integration-tests @ git+https://github.com/element-hq/ess-helm.git@d6d33a7f7051a0b6bbdcc609a059ae328feee269#subdirectory=tests
...
Installed 3 executables: collect-ess-logs, pytest-ess, setup-ess-cluster
```

## Usage

### Setting Up a Cluster
To set up a Kubernetes cluster for testing, use the `setup-ess-cluster` command:

```bash
setup-ess-cluster
```

### Running Tests
To run tests, use the `run-tests` command:

```bash
pytest-ess --test-suite <test-suite-name> [options]
```

#### Options
- `--test-suite`: Name of the test suite to run. Available test suites are defined in the `env` directory as `.rc` files.
- `--pull-chart`: Pull the Helm chart for testing.
- `--chart-version`: Specify the chart version to pull. If not provided, the version is inferred from the package version.
- `--keep`: Keep the Kubernetes cluster after tests complete.
- `--additional-test-values-file`: Path to an additional values file for custom test configurations.

## Test Suites
Test suites are defined in the `env` directory as `.rc` files. Each file corresponds to a different test environment configuration.
