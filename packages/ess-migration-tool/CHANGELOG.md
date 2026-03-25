<!--
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

<!-- towncrier release notes start -->

# ESS Migration Tool 0.1.0 (2026-03-25)

## Misc

- Prepare `ess-migration-tool` for pypi publishing. (#1131, #1147, #1149, #1150, #1152, #1178)
- Fail the migration process if running in quiet mode and secrets or extra files could not be discovered automatically. (#1153)
- Display the next manual steps to conclude the migration tool script. (#1154)
- Display the config keys which are being passed as `additional` settings, and warn the user when ESS will override them. (#1160)
- Display the secret path for the user to use a privileged session to access them. (#1161)
- The migration tool sets up the chart without Element Web, Matrix RTC and Element Admin by default. (#1162)
- Automatically migrate Synapse listeners to ensure they are consistent with what the helm chart expects. (#1165)
- Automatically migrate Matrix Authentication Service listeners to ensure they are consistent with what the helm chart expects. (#1168)
- Drop `.python-version` file. (#1169)


# ESS Migration Tool - Prerelease

## Added

- Add support automatically discovering extra files referenced by Synapse configuration and output them to Kubernetes ConfigMaps manifests. (#1067, #1085, #1117)
- Add support for Synapse workers discovery in migration script. (#1080, #1106)
- Add support for Matrix Authentication Service to migration scripts. (#1083)
- Add generation of valid ESS Values file based on an existing Synapse configuration. (#1052, #1056, #1058)
- Add automatic discovery of secrets and output them to Kubernetes Secrets manifests. (#1052, #1056, #1058)
