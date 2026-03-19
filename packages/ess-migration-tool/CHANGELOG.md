<!--
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

<!-- towncrier release notes start -->

# ESS Migration Tool - Prerelease

## Added

- Add support automatically discovering extra files referenced by Synapse configuration and output them to Kubernetes ConfigMaps manifests. (#1067, #1085, #1117)
- Add support for Synapse workers discovery in migration script. (#1080, #1106)
- Add support for Matrix Authentication Service to migration scripts. (#1083)
- Add generation of valid ESS Values file based on an existing Synapse configuration. (#1052, #1056, #1058)
- Add automatic discovery of secrets and output them to Kubernetes Secrets manifests. (#1052, #1056, #1058)
