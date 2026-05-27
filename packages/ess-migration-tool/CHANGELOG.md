<!--
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

<!-- towncrier release notes start -->

# ESS Migration Tool 0.2.0 (2026-05-27)

## Bugfixes

- Fix an issue where dynamically discovered secrets would still be logged as initialized by ESS. (#1296)
- Fix an issue where underrides would be logged as overrides. (#1297)
- Fix `database` not being removed from Synapse & MAS `additional` discovered configuration when selecting ESS-managed database. (#1307)
- Fix an issue where Matrix Authentication Service might be using the wrong password when using an existing database. (#1350, #1352)
- Add some missing configuration keys to override detection. (#1351)

## Features

- Handle configuration sources conflicts when generating ESS values. (#1266, #1276, #1294)
- Add support for migrating Element Web `config.json` to ESS Community. (#1268, #1275)
- Display settings that the chart tries to set as `underrides`. (#1269)
- Add support for migrating Well Known delegation configuration files (client.json, server.json, support.json) to ESS. Users can now specify well-known files via `--well-known-dir` for a directory containing the files, or individual files via `--well-known-client`, `--well-known-server`, and `--well-known-support`. Files can be with or without the `.json` extension. (#1274)
- Add support for migrating Hookshot `config.yaml` to ESS Community. (#1275)
- Lazy load extra files instead of loading them in memory before dumping them into our output directory. (#1298)
- Trigger a values conflict resolution if Synapse `homeserver.yaml` does not have `matrix_authentication_service` configured despite a MAS `config.yaml` being passed. (#1306)
- Allow the migration process to discover MAS <-> Synapse shared secret from Synapse configuration, and resolve any conflicting configuration. (#1311, #1313)
- Use Rich library to display formatted tables for migration mappings, workers, secrets, and warnings in the CLI output. (#1340, #1341, #1343, #1344, #1345, #1346, #1348, #1349)
- Use Rich library to display formatted commands in the CLI output. (#1342)
- Log all migration process to a summary log file. (#1353)

## Misc

- Refactor `additional` handling to rely on a generic transformer. (#1246)
- Refactor strategies to allow them to manage any component configuration. (#1248, #1250, #1299)
- Drop delays in tests. (#1251)
- Support wildcard in secrets handling. (#1256)
- Adjust handling of failures in dynamically discovered secrets. (#1257, #1260)
- Refactor internal prompting logic. (#1261)
- Handle nested keys with dots when parsing configuration files. (#1264)
- Adjust build system to support uv 0.11. (#1277)
- Tests: Fix the tests validating the helm validator fixture. (#1280)
- Refactor internal handling of secrets to allow multiple secrets discovery implementations. (#1286, #1288, #1295)
- Change artifical delays in logs to "press enter to continue" interaction. (#1293)
- Verify that all our transformation specs target an existing key in the schema. (#1300)
- Remove some dead code from the strategies. (#1318)
- Add support for importing appservices as high level values in `synapse.appservices`. (#1327, #1328)
- Fix empty extra file logs when no extra files was discovered. (#1333)
- Adjust the wording of the migration process. (#1339)
- CI: Fix version bumps after release. (#1355)


# ESS Migration Tool 0.1.2 (2026-03-26)

## Misc

- Add readme and license informations. (#1188)


# ESS Migration Tool 0.1.1 (2026-03-26)

## Bugfixes

- Fix an issue with invalid values schema when importing Matrix Authentication Service private keys. (#1184)

## Features

- Allow the user to migrate its data to ESS-managed databases and describe the migration steps to take. (#1155, #1166)
- Prompt the user for Synapse ingress host if `public_baseurl` is not set. (#1159)

## Misc

- Prepare `ess-migration-tool` for pypi publishing. (#1178)
- CI: Fix publishing to pypi. (#1186)


# ESS Migration Tool 0.1.0 (2026-03-25)

## Features

- Fail the migration process if running in quiet mode and secrets or extra files could not be discovered automatically. (#1153)
- Display the next manual steps to conclude the migration tool script. (#1154)
- Display the config keys which are being passed as `additional` settings, and warn the user when ESS will override them. (#1160)
- Display the secret path for the user to use a privileged session to access them. (#1161)
- The migration tool sets up the chart without Element Web, Matrix RTC and Element Admin by default. (#1162)
- Automatically migrate Synapse listeners to ensure they are consistent with what the helm chart expects. (#1165)
- Automatically migrate Matrix Authentication Service listeners to ensure they are consistent with what the helm chart expects. (#1168)

## Misc

- Prepare `ess-migration-tool` for pypi publishing. (#1131, #1147, #1149, #1150, #1152, #1178)
- Drop `.python-version` file. (#1169)


# ESS Migration Tool - Prerelease

## Features

- Add support automatically discovering extra files referenced by Synapse configuration and output them to Kubernetes ConfigMaps manifests. (#1067, #1085, #1117)
- Add support for Synapse workers discovery in migration script. (#1080, #1106)
- Add support for Matrix Authentication Service to migration scripts. (#1083)
- Add generation of valid ESS Values file based on an existing Synapse configuration. (#1052, #1056, #1058)
- Add automatic discovery of secrets and output them to Kubernetes Secrets manifests. (#1052, #1056, #1058)
