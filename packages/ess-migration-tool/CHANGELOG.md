<!--
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

<!-- towncrier release notes start -->

# ESS Migration Script ess-migration-tool 0.1.0.dev1 (2026-03-25)

## Features

- Allow the user to migrate its data to ESS-managed databases and describe the migration steps to take. (#1155, #1166)
- Prompt the user for Synapse ingress host if `public_baseurl` is not set. (#1159)

## Misc

- #1131, #1147, #1149, #1150, #1152, #1153, #1154, #1160, #1161, #1162, #1165, #1168, #1169, #1178


# ESS Migration Tool - Prerelease

## Added

- Add support automatically discovering extra files referenced by Synapse configuration and output them to Kubernetes ConfigMaps manifests. (#1067, #1085, #1117)
- Add support for Synapse workers discovery in migration script. (#1080, #1106)
- Add support for Matrix Authentication Service to migration scripts. (#1083)
- Add generation of valid ESS Values file based on an existing Synapse configuration. (#1052, #1056, #1058)
- Add automatic discovery of secrets and output them to Kubernetes Secrets manifests. (#1052, #1056, #1058)
