<!--
Copyright 2025 New Vector Ltd
Copyright 2025 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

<!-- towncrier release notes start -->

# ESS Community Helm Chart 26.2.0 (2026-02-05)

## Changed

- Set default permissions on Hookshot so that local users only have permissions to manage integrations and connections.

  Permissions should be adjusted to give specific users the ability to administer integrations, e.g.
  ```yaml
  hookshot:
    additional:
      permissions.yaml:
        config: |
          permissions:
          - actor: {{ $.Values.serverName | quote }}
            services:
            - service: "*"
              level: manageConnections
          - action: "@an-admin-user:{{ $.Values.serverName }}"
            services:
            - service: "*"
              level: admin
  ``` (#1010, #1014)
- Update the test cluster values so that Hookshot can make requests to cluster-internal IP addresses. (#1010, #1018, #1023)

## Fixed

- Fix Hookshot widgets not being available when using the Synapse `Ingress` / not having a dedicated Hookshot `Ingress`. (#1010)

## Internal

- CI: Export logs of all k3d namespaces. (#1015)
- CI: Remove code duplication that existed between `pytest` integration test suite and `setup_test_cluster.sh` script. (#1016, #1017)
- CI: Use OCI repository to install `cert-manager` and `prometheus-operator-crds`. (#1020)
- CI: Support `--rollback-on-failure` helm 4 parameter. (#1022)


# ESS Community Helm Chart 26.1.3 (2026-01-28)

## Changed

- Upgrade Element Web to v1.12.9.

  Highlights:
  - Allow local log downloads instead of a bug report endpoint URL.
  - Support for stable [MSC4191](https://github.com/matrix-org/matrix-spec-proposals/pull/4191) account management action parameter
  - Support for stable m.oauth UIA stage from [MSC4312](https://github.com/matrix-org/matrix-spec-proposals/pull/4312)

  Full Changelogs:
  - [v1.12.9](https://github.com/element-hq/element-web/releases/tag/v1.12.9)

  (#981)
- Upgrade Matrix Authentication Service to v1.10.0.

  Highlights:
  - Support for stable [MSC3824](https://github.com/matrix-org/matrix-spec-proposals/pull/3824) (OAuth 2.0 API aware clients) values
  - Support for stable [MSC4191](https://github.com/matrix-org/matrix-spec-proposals/pull/4191) account management actions
  - Cleanup various old, soft-deleted entities from the database.

  Full Changelogs:
  - [v1.10.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v1.10.0)

  (#990)
- Upgrade Synapse to v1.146.0.

  Highlights:
  - Stabilise support for [MSC4312](https://github.com/matrix-org/matrix-spec-proposals/pull/4312)'s `m.oauth` User-Interactive Auth stage for resetting cross-signing identity with the OAuth 2.0 API.
  - Fix joining a restricted v12 room locally when no local room creator is present but local users with sufficient power levels are.
  - Fixed parallel calls to `/_matrix/media/v1/create` being rate-limited for appservices even if `rate_limited: false` was set in the registration.

  Full Changelogs:
  - [v1.146.0](https://github.com/element-hq/synapse/releases/tag/v1.146.0)

  (#992)


# ESS Community Helm Chart 26.1.2 (2026-01-27)

## Added

- Add support for configuring `internalTrafficPolicy` for services behind ingresses. (#999)
- Add support for configuring `externalTrafficPolicy` for `NodePort` and `LoadBalancer` services behind ingresses. (#1000)
- Add support for configuring `externalTrafficPolicy` to `exposedServices`. (#1001)
- Add support for configuring `internalTrafficPolicy` to `exposedServices`. (#1001)
- Add support to customize `nodePort` of exposed services.

  `nodePort` property of `exposedServices.*` is now a string template taking two parameters:
  - `context`: The exposed service values context `*.exposedServices.<svc>`
  - `root` : The helm $ root values context

  On Matrix RTC values, the `nodePort` template defaults to `{{ .context.port }}` so that the `nodePort`
  is the same as `port`. Setting the template to an empty string will skip setting `nodePort`
  on the service.

  (#1002)
- Add support for configuring `externalIPs` of exposed services. (#1006)
- Add support for configuring annotations of Ingress services. (#1007)
- Add support for configuring `externalIPs` of Ingress services. (#1007)

## Changed

- Hookshot: Disable encryption by default as it is still experimental. (#995)
- Hookshot: Use appservice fully qualified domain name in the registration file. (#996)
- Hookshot: Publish service unready address. (#996)
- Hookshot: Enable adding widgets in rooms where it is invited by default. (#997)
- Change default `externalTrafficPolicy` for the SFU exposed services from `Local` to Kubernetes defaults `Cluster`. (#1001)
- Update Hookshot to 7.3.1.

  Highlights :
  - Add generic webhook transformation JS snippet which can handle GitLab Pipeline payloads under `contrib/jsTransformationFunctions/gitlab-pipeline.js`
  - Add generic webhook transformation JS snippet to format text as code block under `contrib/jsTransformationFunctions/format-as-code.js`
  - Fix the `!hookshot help` command not working

  Full Changelogs:
  - [7.3.1](https://github.com/matrix-org/matrix-hookshot/releases/tag/7.3.1)

  (#1008)

## Fixed

- Matrix RTC: Fix a templating issue when turn was enabled with  a cert-manager issuer to generate the tls secret. (#989)
- Hookshot: Fix a templating issue when Matrix Authentication Service is enabled if Hookshot was enabled without an Ingress. (#993)

## Documentation

- Document how to setup and configure Hookshot. (#988)

## Internal

- CI: pin Helm to 3.19.4 in the manifest tests to avoid a bug with merging null values. (#994)
- CI: Add test running Hookshot with Matrix Authentication Service enabled. (#995)
- Build services schema using a common service.json file. (#1003)


# ESS Community Helm Chart 26.1.1 (2026-01-22)

## Removed / Breaking Changes

- Move Synapse's Redis to a top-level shared component that can be used by multiple components of the chart.

  There is no impact when using the default values, but if you have customised values under the `synapse.redis` key, you will need to update them to be under the new top-level `redis` redis. (#972)

## Added

- Add `extraInitContainers` support to all workloads. (#971)
- Matrix RTC: Add support for configuring Turn TLS to help RTC traffic go through corporate Wifi networks and firewalls. (#976)
- Add support for generating appservice registration files with `matrix-tools`. (#979)
- Add support for Hookshot installation in ESS Community.

  [Hookshot](https://matrix-org.github.io/matrix-hookshot/latest/hookshot.html) is a Matrix Bot for connecting to external services.
  It is not enabled by default, but can be enabled by setting `hookshot.enabled: true`. (#979, #986)
- Matrix RTC: Add support for configuring UDP Turn. (#982)

## Changed

- Support generator arguments in `matrix-tools` secret generation. (#973)
- Support configuring the RSA key size generated by `matrix-tools`. (#973)
- Support exporting RSA key as DER and PEM `matrix-tools`. (#973)
- `matrixRTC.sfu.exposedServices.*.portType` are now an enum, and only accepts `NodePort`, `HostPort` and `LoadBalancer`. (#976)
- Few corrections to the README. (#980)
- Specify service type `ClusterIP` for internal services of Matrix RTC and Synapse. (#985)

## Documentation

- Make documentation clearer that some configuration options can't be changed by the additional configuration mechanism. (#975)


# ESS Community Helm Chart 26.1.0 (2026-01-14)

## Added

- Add support for `extraVolumes` and `extraVolumeMounts` in components values. (#957, #965)

## Changed

- Upgrade Element Web to v1.12.8.

  Highlights:
  - Update polls UX to match EX Mobile and improve accessibility.
  - [MSC4380](https://github.com/matrix-org/matrix-spec-proposals/pull/4380) Invite blocking support
  - Update history visibility UX


  Full Changelogs:
  - [v1.12.7](https://github.com/element-hq/element-web/releases/tag/v1.12.7)
  - [v1.12.8](https://github.com/element-hq/element-web/releases/tag/v1.12.8)

  (#931, #960)
- Adjust generated file copyright headers for 2026. (#943)
- Revert change of Matrix Authentication Service deployment's `maxSurge` to 0. (#961)
- Upgrade Matrix Authentication Service to v1.9.0.

  Highlights:
  - Fix running multiple migration process in parallel

  Full Changelogs:
  - [v1.9.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v1.9.0)

  (#961)
- Upgrade Synapse to v1.145.0.

  Highlights:
  - Add memberships endpoint to the admin API. This is useful for forensics and T&S purpose
  - Add worker support to GET `/_synapse/admin/v2/users/<user_id>`

  Full Changelogs:
  - [v1.145.0](https://github.com/element-hq/synapse/releases/tag/v1.145.0)

  (#962)
- Separate post-deployment hints and domains in NOTES. (#968)

## Internal

- CI: set timeouts for curl so it doesn't attempt to connect for longer than `Pod` startup time. (#935)
- CI: wait a bit longer for the `Ingress` controller to be available. (#942)
- CI: run most jobs on maintenance branches too. (#945)
- CI: Adjust Go version used to test matrix-tools to 1.25. (#952)
- CI: Set a maximum number of cooperative asyncio tasks. (#966)


# ESS Community Helm Chart 25.12.2 (2025-12-19)

## Security

- Fix critical security issue tracked as `ELEMENTSEC-2025-1670`.

  This release is a critical security update to address an issue affecting all versions of ESS Community and ESS Pro. ESS Classic and other Synapse-based deployments are not affected.

  The issue only has an impact when federation APIs are exposed to an untrusted network. Deployments that are not currently federating, or that only federate in a closed, trusted federation, are not impacted. These deployments should not enable public federation without first applying this update.

  We advise you to apply the update as quickly as possible. (#943)


# ESS Community Helm Chart 25.12.1 (2025-12-12)

## Removed / Breaking Changes

- The MatrixRTC SFU now restricts creation of calls to users on the local homeserver.

  This can be changed back to allowing anyone to create calls on the SFU by by setting `matrixRTC.restrictRoomCreationToLocalUsers: false`. (#926)

## Changed

- Upgrade Synapse to v1.144.0.

  Highlights:
  - Add experimental implementation of [MSC4380](https://github.com/matrix-org/matrix-spec-proposals/pull/4380) (invite blocking).
  - Allow the restarting delayed events endpoint for MatrixRTC to be served by workers.

  Full Changelogs:
  - [v1.144.0](https://github.com/element-hq/synapse/releases/tag/v1.144.0)

  (#915)
- Upgrade Matrix Authentication Service to v1.8.0.

  Highlights:
  - Add more options to deal with localpart conflicts on upstream OAuth 2.0 login.
  - Option to skip confirmation when registering through an upstream OAuth provider.

  Full Changelogs:
  - [v1.8.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v1.8.0)

  (#916)
- Support configuring IPv4-only, IPv6-only or Dual-Stack component binds by configuring `networking.ipFamily`.

  Defaults to `dual-stack` but if you are in a cluster where IPv6 support is either disabled at boot or compiled out you may need to set this to `ipv4` (#921)
- Allow Synapse and Matrix Authentication Service to receive traffic over IPv6. (#921)
- Removed some unused code from the `initSecrets` generation container.

  Also complete the docs on the secret types it supports. (#927)
- Upgrade Element Admin to v0.1.10.

  Highlights :
  - Fixed a crash in the moderation tab when the Adminbot endpoint is unavailable
  - Added the ability to delete rooms
  - Made the language switcher keyboard navigable
  - Updated translations for better user experience

  Full Changelogs:
  - [v0.1.10](https://github.com/element-hq/element-admin/releases/tag/v0.1.10)

  (#932)


# ESS Community Helm Chart 25.12.0 (2025-12-04)

## Removed / Breaking Changes

- Remove `imagePullSecrets` in favour of `image.pullSecrets`.

  As of 25.10.1 `imagePullSecrets` was deprecated in favour of `image.pullSecrets`.
  It has now been removed and attempting to use `imagePullSecrets` will trigger a schema
  validation error. (#901)
- Remove the ability to set `rtc.{use_external_ip,node_ip}` via `matrixRTC.sfu.additional` in favour of `matrixRTC.sfu.{useStunToDiscoverPublicIP,manualIP}`.

  As of 25.9.1 `matrixRTC.sfu.{useStunToDiscoverPublicIP,manualIP}` were introduced to provide direct values for these settings. Attempting to set
  these via `matrixRTC.sfu.additional` will result in your values being ignored. (#901)

## Changed

- Upgrade Element Web to v1.12.6.

  Highlights:
  - Remove mentions from forwarded messages.
  - Improve aria attributes on the emoji picker.
  - Support using Element Call for voice calls in DMs.

  Full Changelogs:
  - [v1.12.4](https://github.com/element-hq/element-web/releases/tag/v1.12.4)
  - [v1.12.5](https://github.com/element-hq/element-web/releases/tag/v1.12.5)
  - [v1.12.6](https://github.com/element-hq/element-web/releases/tag/v1.12.6)

  (#865, #903, #918)
- Remove hard-coded `podAntiAffinity` for `Deployments` that had set `replicas > 2`. (#867)
- Support `topologySpreadConstraints` on all workloads, not just select ones. (#867)
- Set a soft, default `topologySpreadConstraints` for all workloads.

  The can be removed by setting `topologySpreadConstraints` to `[]` at the top-level or
  overridden on a per-component basis by setting that component's `topologySpreadConstraints`. (#867)
- Unify management of `StatefulSet.spec` along with `Deployment.spec`. (#872)
- Upgrade Synapse to v1.143.0.

  Highlights:
  - Update MSC4140 delayed event support, for separate endpoints.

  Full Changelogs:
  - [v1.143.0](https://github.com/element-hq/synapse/releases/tag/v1.143.0)

  (#876)
- Upgrade Matrix Authentication Service to v1.7.0.

  Highlights:
  - Interactively help users choosing a username.

  Full Changelogs:
  - [v1.7.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v1.7.0)

  (#878)
- Change Element Web and MatrixRTC SFU `Ingresses` to target `Service` port names rather than numbers. (#879)
- Harmonise the hook weights and reduce the number of distinct hook weight values.

  This should speed up installs and upgrades as now there are only 2 distinct pre-install/pre-upgrade hook weights. (#880)
- Better handle the only worker-capable delayed-events endpoint. (#889)
- Remove explicit configuration of HAProxy `maxconn` at the global and backend level.

  This improves the compatibility with microk8s clusters that don't raise `ulimits` by default. (#890)
- Upgrade Element Admin to v0.1.9.

  Highlights:
  - Integration with the ESS Pro Adminbot

  Full Changelogs:
  - [v0.1.9](https://github.com/element-hq/element-admin/releases/tag/v0.1.9)

  (#900)
- Listen for HAProxy traffic over IPv6. (#905)
- Change `ipFamilyPolicy` to `PreferDualStack` for all services to expose them over dual-stack where possible. (#907)
- Change Matrix Authentication Service deployment `maxSurge` to 0.

  We have seen migrations race conditions happening during Matrix Authentication Service pods
  rollout. This sets `maxSurge` to 0 to try to make sure only 1 pod at a time runs the
  migration process. (#910, #914)

## Fixed

- Change Postgres `emptyDirs` to be memory backed. (#894)
- Ensure Postgres is fully setup before marking as available or live. (#897)
- Fix Matrix Authentication Service secrets config generation so private keys coming from an external secret are correctly referenced. (#908)

## Internal

- CI: switch from kind to k3d for integration tests. (#871)
- CI: simplify manifest test setup now that we care less about which deployables are in-use for a given values file. (#877)
- CI: add tests covering the weights and phases of Helm hooks. (#880, #884)
- Document why we don't use `passfile` for Synapse & MAS' Postgres configuration. (#881)
- CI: Don't add New Vector Ltd copyright to new ci values files. (#882)
- CI: add concurrency limit per branch to prevent too many concurrent jobs. (#883)
- CI: validate that all `emptyDirs` are memory backed. (#894)
- CI: Make sure `init-secrets` job is not created when no secrets needs to be generated. (#896)
- CI: Enhance manifests caching in manifests pytest runs. (#899)
- CI: Make cached manifests immutable to avoid issues where they might be mutated during test runs, causing races. (#899)
- CI: stop flakes in `test_pods_monitored`. (#902)
- CI: fix image verifications step failing on PRs on forks. (#909)
- CI: adjust expected status codes to retry on the upgrade integration tests. (#913)


# ESS Community Helm Chart 25.11.1 (2025-11-14)

## Changed

- Upgrade Matrix Authentication Service to v1.6.0.

  Highlights:
  - Be strict about undefined variables in templates

  Full Changelogs:
  - [v1.6.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v1.6.0)

  (#852)
- Upgrade Synapse to v1.142.0.

  Highlights:
  - Add an Admin API to allow an admin to fetch the space/room hierarchy for a given space.

  Full Changelogs:
  - [v1.142.0](https://github.com/element-hq/synapse/releases/tag/v1.142.0)

  (#853)

## Internal

- CI: validate that images are AMD64 & ARM64. (#859)
- CI: unify manifest tests around `Pod` replicas. (#866)


# ESS Community Helm Chart 25.11.0 (2025-11-06)

## Changed

- Upgrade Element Web to v1.12.3.

  Highlights:
  - Fix sort order in space hierarchy.
  - New Room list: don't display message preview of thread.

  Full Changelogs:
  - [v1.12.3](https://github.com/element-hq/element-web/releases/tag/v1.12.3)

  (#842)
- Re-add the chart's icon. (#848)
- Update README. (#854)
- Configure experimental MSC4143 advertisement in Synapse when MatrixRTC is enabled.

  This is in addition to the MSC4143 advertisement on the client well-known endpoint for now, but it is expected to replace it in time. (#855)
- Update Element Web's default bug report URL to use the dedicated subdomain for bug reporting. (#856)

## Fixed

- Fix an issue where the chart could not be deployed against clusters returning an experimental build. (#850)

## Documentation

- Document setting alternative STUN servers for MatrixRTC. (#851)

## Internal

- CI: Use Element customised `pyhelm3` dependency for running tests. (#848)


# ESS Community Helm Chart 25.10.3 (2025-10-31)

## Changed

- Update `example-default-enabled-components-values.yaml` to include MatrixRTC as it is enabled by default. (#516)
- Upgrade Element Web to v1.12.2.

  Highlights:
  - Improve handling of animated images.
  - Fix duration of voice message in timeline.
  - Improve keyboard navigation on invite dialog.

  Full Changelogs:
  - [v1.12.2](https://github.com/element-hq/element-web/releases/tag/v1.12.2)

  (#809)
- Update Element Admin to v0.1.8.

  Highlights:
  * Allow admins to generate personal access tokens for users
  * Fix the ESS version not loading after a refresh

  Full Changelogs:
  * [v0.1.5](https://github.com/element-hq/element-admin/releases/tag/v0.1.5)
  * [v0.1.6](https://github.com/element-hq/element-admin/releases/tag/v0.1.6)
  * [v0.1.7](https://github.com/element-hq/element-admin/releases/tag/v0.1.7)
  * [v0.1.8](https://github.com/element-hq/element-admin/releases/tag/v0.1.8)

  (#816, #843, #844)
- Update Chart metadata to enhance tooling like `renovate` and `artifacthub.io`. (#818)
- Update Synapse to v1.141.0.

  Highlights:
  * Update docker image to use Debian trixie as the base and thus Python 3.13
  * Allow using [MSC4190](https://github.com/matrix-org/matrix-spec-proposals/pull/4190) behaviour without the opt-in registration flag
  * Stabilize support for [MSC4326](https://github.com/matrix-org/matrix-spec-proposals/pull/4326): Device masquerading for appservices

  Full Changelogs:
  * [v1.141.0](https://github.com/element-hq/synapse/releases/tag/v1.141.0)

  (#826)
- Ensure there's at least 2 newlines at the end of the `haproxy.cfg` file. (#829)
- Upgrade Matrix Authentication Service to v1.5.0.

  Highlights:
  - Initial support for admins managing Personal Access Tokens for users using the Admin APIs.

  Full Changelogs:
  - [v1.5.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v1.5.0)

  (#830)
- Add 'Element Creations Ltd' copyright to every file. (#835)

## Fixed

- Postgres: Fix the ess-updater container do not have access to the local data directory. (#817)
- Prioritize `wellKnownDelegation.baseDomainRedirect.url` over `elementWeb.ingress.host`.

  Previously, whenever elementWeb was enabled, the url property was silently ignored instead of, as expected, taking precedence. (#819)
- Fix a Matrix compatible JSON response not being correctly sent when a Synapse backend is down. (#829)

## Documentation

- Values Fragments: Make `serverName` unique to 1 fragment. (#806)
- Matrix RTC: Document the SFU `CrashLoopBackOff` issue. (#825)

## Internal

- CI: New implementation of the configuration consistency checks. (#817, #831, #832, #833)
- CI: check that `matrix-tools` containers only ever set `args` and not `command`. (#820)
- CI: check that all changed files have copyright notices for the new Element legal entity. (#822)
- Update SPDX check script to handle multiple Copyright headers. (#822, #835)
- Allow cloning of the source repository on Windows. (#827)
- Rename `Removed` changelog sections to `Removed / Breaking Changes` and make more prominent. (#828)
- CI: test that all multi-line config files end up in cluster with a trailing newline. (#829)
- CI: adapt integration test cluster creation for latest pytest-kubernetes. (#841)


# ESS Community Helm Chart 25.10.2 (2025-10-16)

## Security

- Update Matrix Authentication Service to v1.4.1.

  This is a security release which includes a fix for [CVE-2025-62425](https://nvd.nist.gov/vuln/detail/CVE-2025-62425) / [GHSA-6wfp-jq3r-j9xh](https://github.com/element-hq/matrix-authentication-service/security/advisories/GHSA-6wfp-jq3r-j9xh), which affects servers using the local password database, starting MAS 0.20.0 and later. See the advisory for details.

  Full Changelogs:
  * [v1.4.1](https://github.com/element-hq/matrix-authentication-service/releases/tag/v1.4.1)

  (#813)

## Changed

- Upgrade Postgres Exporter to 0.18.1.

  Full Changelogs:
  - [0.18.0](https://github.com/prometheus-community/postgres_exporter/releases/tag/v0.18.0)
  - [0.18.1](https://github.com/prometheus-community/postgres_exporter/releases/tag/v0.18.1)

  (#812)


# ESS Community Helm Chart 25.10.1 (2025-10-15)

## Added

- List deprecations in `NOTES.txt` when running `helm install`/`helm upgrade`. (#796)
- Support overriding the default `imagePullPolicy` for every component by setting `image.pullPolicy`.

  Per-image overrides can be set by setting `<path.to>.image.pullPolicy` as before.

  If `image.pullPolicy` or per-image overrides aren't set `IfNotPresent` is used by default for images
  referenced by digest and `Always` is used by default images referenced by tag as previously. (#798)

## Changed

- Update Matrix Authentication Service to v1.4.0.

  Highlights:
  * Make it possible to allow password registration without email verification.
  * Add Admin API to finish individual sessions.

  Full Changelogs:
  * [v1.4.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v1.4.0)

  (#787)
- Ensure consistent captured headers in HAProxy log lines, between all HTTP request processing HAProxy frontends. (#788)
- Correct the handling of multiple X-Forwarded-For headers to Synapse.

  This may have exhibit itself as requests being incorrectly rate-limited by Synapse.

  The source IP logged by HAProxy is now always the IP connecting to HAProxy rather than
  a value extracted from the X-Forwarded-For header (if present). This is usually an IP
  for the ingress controller. (#788)
- Log the X-Forwarded-For header and stop logging the Referer header in HAProxy. (#788)
- Upgrade HAProxy to 3.2.

  Release notes:
  - [3.2](https://www.haproxy.com/blog/announcing-haproxy-3-2)

  (#790)
- Upgrade Element Admin to v0.1.4.

  Highlights:
  - Use authenticated media endpoints for thumbnails
  - Keep selected item when changing filters

  Full Changelogs:
  - [v0.1.4](https://github.com/element-hq/element-admin/releases/tag/v0.1.4)

  (#793)
- Inform chart users of the deprecations around `rtc.{use_external_ip,node_ip}` that happened in 25.9.1. (#796)
- Move the top-level `imagePullSecrets` list to `image.pullSecrets`.

  Anyone setting `imagePullSecrets` in their values files will see
  schema errors if they don't restructure this setting. (#798)
- Upgrade Synapse to v1.140.0.

  Highlights:
  - Add a new [Media Query by ID Admin API](https://element-hq.github.io/synapse/v1.140/admin_api/media_admin_api.html#query-a-piece-of-media-by-id) that allows server admins to query and investigate the metadata of local or cached remote media via the origin/media_id identifier found in a Matrix Content URI
  - Add experimental implementation of the `GET /_matrix/client/v1/rtc/transports` endpoint for the latest draft of [MSC4143: MatrixRTC](https://github.com/matrix-org/matrix-spec-proposals/pull/4143)

  Full Changelogs:
  - [v1.140.0](https://github.com/element-hq/synapse/releases/tag/v1.140.0)

  (#799)

## Fixed

- Fix templated `<component>.ingress.host` values not being rendered correctly in `NOTES.txt`. (#791)
- Fix the Matrix RTC SFU not restarting when user-provided configuration is set via `matrixRTC.sfu.additional.<name>.config`. (#805)

## Internal

- CI: simplify MatrixRTC PyTest with Synapse + Well-Knowns. (#785)
- Ensure all `kubectl` commands in `scripts/setup_test_cluster.sh` specify the context. (#789)
- CI: add a test that we don't have anything that looks like a template string in the rendered files. (#791)
- CI: check that all go files are formatted correctly as per `gofmt`. (#792)
- Run `gofmt` over `matrix-tools`. (#792)
- CI: Use poetry 2.x. (#794)
- CI: handle a user already existing in MAS across subsequent test runs. (#795)
- CI: recreate cached user access tokens when they're not valid (from a previous test run). (#795)
- CI: don't attempt to manage MAS user passwords if password login is disabled. (#795)
- CI: check that user-provided inline configuration changes a hash label on some workloads and thus restarts `Pods`. (#805)


# ESS Community Helm Chart 25.10.0 (2025-10-08)

## Added

- Add a validation check to make sure no component is sharing any postgres database. (#778)

## Changed

- Update Element Web to v1.12.1.

  Highlights:

  * Update Message Sound for Element
  * New Room List: Don't clear filters on space change
  * Rich Text Editor: Add emoji suggestion support

  Full Changelogs:
  * [v1.12.1](https://github.com/element-hq/element-web/releases/tag/v1.12.1)

  (#779)
- Upgrade Synapse to v1.139.2.

  Highlights:
  * Fix [`CVE-2025-61672`](https://www.cve.org/CVERecord?id=CVE-2025-61672) / [`GHSA-fh66-fcv5-jjfr`](https://github.com/element-hq/synapse/security/advisories/GHSA-fh66-fcv5-jjfr). Lack of validation for device keys in Synapse before 1.139.1 allows an attacker registered on the victim homeserver to degrade federation functionality, unpredictably breaking outbound federation to other homeservers.

  Full Changelogs:
  * [v1.139.1](https://github.com/element-hq/synapse/releases/tag/v1.139.1)
  * [v1.139.2](https://github.com/element-hq/synapse/releases/tag/v1.139.2)

  (#780, #783)

## Fixed

- Fix an issue where matrix-tools would fail to render configuration on containers restarts not causing a new pod cycle. (#771, #782)

## Documentation

- Add initial troubleshooting guide around `MISSING_MATRIX_RTC_FOCUS`. (#768)

## Internal

- CI: remove test exclusions relating to versions 25.9.1 or older. (#767)
- Add a documentation type to the changelog. (#768, #781)


# ESS Community Helm Chart 25.9.3 (2025-10-02)

## Fixed

- Fix Matrix RTC SFU manualIP setting so that it correctly propagates through. (#765)

## Internal

- CI: update Matrix RTC values files to cover STUN, Manual IP, and Node IP cases correctly. (#765)


# ESS Community Helm Chart 25.9.2 (2025-09-30)

## Added

- Introducing Element Admin, a user-friendly interface to manage your ESS deployment. This is default enabled, and you need to configure `elementAdmin.ingress.host` on upgrade, as well as create its DNS and TLS.

  ![Element Admin Screenshot](https://github.com/user-attachments/assets/ee37deb6-d7e4-422d-8026-af948fcb251d) (#743, #759, #762)

## Changed

- Define "matrix-tools" containers with "args" set instead of "command". (#738)
- Update Element Web to v1.12.0.

  Highlights:

  * Use the new room list by default
  * Automatically adjust history visibility when making a room private
  * Stop ringing and remove toast if another device answers a RTC call.

  Full Changelogs:
  * [v1.12.0](https://github.com/element-hq/element-web/releases/tag/v1.12.0)

  (#744)
- Allow overriding of the Matrix Authentication Service policy configuration via additional configuration. (#745)
- Remove `experimental.access_token_ttl` from the Matrix Authentication Service config as the need for it has gone. (#745)
- Upgrade Synapse to v1.139.0.

  Highlights:
  * Fix a performance regression related to the experimental Delayed Events ([MSC4140](https://github.com/matrix-org/matrix-spec-proposals/pull/4140)) feature.
  * Add experimental support for [MSC4308: Thread Subscriptions extension to Sliding Sync](https://github.com/matrix-org/matrix-spec-proposals/pull/4308) when [MSC4306: Thread Subscriptions](https://github.com/matrix-org/matrix-spec-proposals/pull/4306) and [MSC4186: Simplified Sliding Sync](https://github.com/matrix-org/matrix-spec-proposals/pull/4186) are enabled.
  * Update [MSC4190](https://github.com/matrix-org/matrix-spec-proposals/pull/4190) support to return correct errors and allow appservices to reset cross-signing keys without user-interactive authentication.
  * Fix bug where we did not send invite revocations over federation.

  Full Changelogs:
  * [v1.138.2](https://github.com/element-hq/synapse/releases/tag/v1.138.2)
  * [v1.139.0](https://github.com/element-hq/synapse/releases/tag/v1.139.0)

  (#752, #755)
- Update Matrix Authentication Service to v1.3.0.

  Highlights:
  * Add Admin API filter to search users by username.
  * Add Admin API to list upstream OAuth 2.0 providers.

  Full Changelogs:
  * [v1.3.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v1.3.0)

  (#753)
- Upgrade Matrix RTC SFU (LiveKit) to v1.9.1.

  Full Changelogs:
  * [v1.9.1](https://github.com/livekit/livekit/releases/tag/v1.9.1)

  (#758)

## Internal

- CI: disable initSecrets for test values files that are to use secrets defined in Helm or external secrets. (#748)
- CI: cover testing in-Helm secrets for MAS. (#751)
- CI: Add go cache while building matrix-tools. (#754)
- CI: use stable URL for auth_metadata check. (#756)


# ESS Community Helm Chart 25.9.1 (2025-09-17)

## Added

- MatrixRTC: Add `sfu.useStunToDiscoverPublicIP` and `sfu.manualIP` values to simplify networking configuration.

  **Warning:** In version 25.10, these values will override any manually set `rtc.external_ip` and `rtc.node_ip`
  configured through `sfu.additional` additional configuration. (#733)

## Changed

- Update Element Web to v1.11.112.

  Highlights:

  * Fix [CVE-2025-59161](https://www.cve.org/CVERecord?id=CVE-2025-59161) / [GHSA-m6c8-98f4-75rr](https://github.com/element-hq/element-web/security/advisories/GHSA-m6c8-98f4-75rr)

  Full Changelogs:
  * [v1.11.112](https://github.com/element-hq/element-web/releases/tag/v1.11.112)

  (#739)

## Internal

- Update the `matrix-stack` chart's `.helmignore` file to ignore Vim swap files. (#724)
- Update tests to grant MAS users with access to the Synapse admin API when requested. (#728)
- CI: Make sure tests fixtures errors are not silenced. (#729)
- CI: Raise an error if the pod is not ready when we want to run it. (#730)
- CI: Do not delete failed curl pods during metrics endpoints tests. (#732)
- Restart curl pods on failure when fetching metrics. (#737)


# ESS Community Helm Chart 25.9.0 (2025-09-10)

## Added

- Add `/_synapse/ess/version` to the Synapse ingress exposing the chart version and edition. (#715)

## Changed

- Turn on push notifications for encrypted messages (MSC4028) support by default. (#712)
- Update Element Web to v1.11.111.

  Highlights:

  * Remember whether sidebar is shown for calls when switching rooms
  * Fix room joining over federation not specifying `via`'s or using aliases

  Full Changelogs:
  * [v1.11.111](https://github.com/element-hq/element-web/releases/tag/v1.11.111)

  (#716)
- Upgrade Synapse to v1.138.0.

  Highlights:
  * Support for the stable endpoint and scopes of [MSC3861](https://github.com/matrix-org/matrix-spec-proposals/pull/3861) & co.

  Full Changelogs:
  * [v1.138.0](https://github.com/element-hq/synapse/releases/tag/v1.138.0)

  (#717)
- Update Matrix Authentication Service to v1.2.0.

  Highlights:
  * Translation updates

  Full Changelogs:
  * [v1.2.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v1.2.0)

  (#718)
- Use unique names for component configuration files, to prevent them from clashing against identically-named files in pods that deploy those components. (#723)

## Internal

- CI: Check labels values against validation regex. (#705)
- CI: Check PVC presence only for existing workloads. (#705)
- Fix typo in "jitter_delay" config keys used in CI tests. (#722)


# ESS Community Helm Chart 25.8.3 (2025-08-27)

### Changed

- Improvements to the ESS Community README. (#678)
- Improved the documentation around the values file required for external vs internal PostgreSQL servers. (#688)
- Update Matrix Authentication Service to v1.1.0.

  Highlights:

  * Support for stable Matrix native OIDC scopes

  Full Changelogs:
  * [v1.0.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v1.0.0)
  * [v1.1.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v1.1.0)

  (#689)
- Switch to stabilised Matrix Authentication Service <-> Synapse configuration.

  `matrixAuthenticationService.synapseOIDCClientSecret` has been removed from the values
  schema and must be removed from your values files if set. (#689)
- Upgrade Synapse to v1.137.0.

  Highlights:
  * Stabilise support for delegating authentication to Matrix Authentication Service
  * Add support for [MSC4293](https://github.com/matrix-org/matrix-spec-proposals/pull/4293) - Redact on Kick/Ban

  Full Changelogs:
  * [v1.136.0](https://github.com/element-hq/synapse/releases/tag/v1.136.0)
  * [v1.137.0](https://github.com/element-hq/synapse/releases/tag/v1.137.0)

  (#689)
- Update Element Web to v1.11.110.

  Highlights:

  * Show a blue lock for unencrypted rooms and hide the grey shield for encrypted rooms
  * Fix matrix.to links not being handled in the app

  Full Changelogs:
  * [v1.11.110](https://github.com/element-hq/element-web/releases/tag/v1.11.110)

  (#690)
- Support configuring a different cluster domain for internal Service references. (#692)
- Documentation: Email is not required any more to set up Let's Encrypt. (#704)

### Fixed

- Fix incorrectly routing unsupported room admin API requests to workers. (#685)
- Ensure Matrix RTC authoriser can contact itself in the test cluster. (#687)

### Internal

- Add dockerhub secrets to curl pods used in pytest. (#669)
- CI: Add Spell Checks in markdown documentation. (#696)


# ESS Community Helm Chart 25.8.2 (2025-08-21)

### Fixed

- Fix Helm >= 3.18.5 considering our schema invalid due to a repeated $id. (#682)


# ESS Community Helm Chart 25.8.1 (2025-08-11)

### Changed

- Update Element Web to v1.11.109.

  Highlights :
  - Add support for the new room version 12
  - Allow /upgraderoom command without developer mode enabled
  - Support for creator/owner power level
  - Various icons and visual changes

  (#663)
- Update Synapse to v1.135.2.

  Highlights :
  - This is the Synapse portion of the [Matrix coordinated security release](https://matrix.org/blog/2025/07/security-predisclosure/). This release includes support for [room version](https://spec.matrix.org/v1.15/rooms/) 12 which fixes a number of security vulnerabilities, including [CVE-2025-49090](https://www.cve.org/CVERecord?id=CVE-2025-49090).
  - The default room version is not changed. Not all clients will support room version 12 immediately, and not all users will be using the latest version of their clients. Large, public rooms are advised to wait a few weeks before upgrading to room version 12 to allow users throughout the Matrix ecosystem to update their clients.

  (#664)

### Internal

- CI: remove flakes in `test_routes_to_synapse_workers_correctly` by streaming logs from all HAProxy `Pods`, not just the current ones. (#654, #655)
- Speed-up the tests asserting the possibility not to create service accounts per components. (#659)
- CI: Fix external contributors CI runs not running properly. (#661)
- Add a helper to build synapse internal hostport in helm templates. (#662)


# ESS Community Helm Chart 25.8.0 (2025-08-06)

### Added

- Document how to configure k3s traefik timeouts. (#617)

### Changed

- Default Synapse to requiring TLS 1.2 or later.

  This can be overridden in additional configuration. (#609)
- Set Element X as app to be pointed to when accessing Element Web from a mobile browser. (#610)
- Document in CI values example that `deploymentMarkers` is default enabled. (#620)
- Upgrade Matrix Authentication Service to v0.20.0.

  Highlights:
  * Support receiving OpenID Connect Back-Channel Logout notifications
  * Support linking of upstream accounts to existing users when the localpart matches
  * Make email address lookups case-insensitive
  * Improve spec compliance of upstream OAuth 2.0 client auth methods

  Full Changelog:
  * [v0.19.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v0.19.0)
  * [v0.20.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v0.20.0)

  (#634)
- Upgrade `lk-jwt-service` to 0.3.0.

  Highlights:
  * Support restricting Matrix room creation to local homeserver only.
    Configure this through `matrixRTC.restrictRoomCreationToLocalUsers`. Default to false for now until clients support this new feature.

  Full Changelog:
  * [0.3.0](https://github.com/element-hq/lk-jwt-service/releases/tag/v0.3.0)

  (#635)
- Upgrade Element Web to v1.11.108.

  Highlights:
  * Allow Element Call to learn the room name
  * Save image on Ctrl/Cmd + S

  Full Changelog:
  * [v1.11.106](https://github.com/element-hq/element-web/releases/tag/v1.11.106)
  * [v1.11.107](https://github.com/element-hq/element-web/releases/tag/v1.11.107)
  * [v1.11.108](https://github.com/element-hq/element-web/releases/tag/v1.11.108)

  (#638)
- Introduce a `device-lists` worker for Synapse. (#639)
- Update worker capable paths for Synapse v1.135.0. (#639)
- Upgrade Synapse to v1.135.0.

  Highlights:
  * [MSC4267](https://github.com/matrix-org/matrix-spec-proposals/pull/4267) support - automatically forgetting rooms on leave
  * Advertise support for Matrix v1.12
  * Add ability to limit amount of media uploaded by a user in a given time period
  * Support arbitrary profile fields

  Full Changelog:
  * [v1.134.0](https://github.com/element-hq/synapse/releases/tag/v1.134.0)
  * [v1.135.0](https://github.com/element-hq/synapse/releases/tag/v1.135.0)

  (#639)
- Split the `receipts-account` worker type into `account-data` and `receipts` workers.

  If you've configured `synapse.workers.receipts-account` this is no longer valid and your configuration should be updated to
  setup `synapse.workers.account-data` and/or `synapse-workers.receipts` as appropriate. (#640)
- Remove support for `/.well-known/element/element.json`.

  It isn't used by clients of ESS Community.

  If you've set it, please remove `wellKnownDelegation.additional.element` from your values files. (#641)
- Source whether Synapse workers are single or scalable from the values rather than maintaining a list of single vs scalable workers. (#644)
- Source whether Synapse workers serve HTTP endpoints or have replication from other configuration to improve consistency of configuration. (#645)
- Update matrix-tools to 0.5.5. (#652)

### Fixed

- Synapse: fix requests being routed to initial-synchrotron incorrectly. (#632, #642, #643, #646)
- Fix incorrect routing for Matrix Authentication Service related Synapse Admin API paths during migration. (#639)

### Internal

- Refactor matrix-tools handling of subcommand. (#592)
- CI: change the comparision branch for the dyff job after the change to the source branch. (#602)
- Add the ability to regenerate a single file in `charts/matrix-stack/ci`. (#603)
- Add the ability to generate values files in `charts/matrix-stack/user_values` from `charts/matrix-stack/ci/fragments`. (#605)
- CI: just list manifests in that dyff that are added/deleted rather than any metadata about them. (#606)
- CI: improve testing of TLS certificates with intermediates. (#612)
- CI: handle `deploymentMarkers` not being enabled in various some PyTests. (#621)
- CI: remove `deploymentMarkers` from `{synapse,matrix-authentication-service}(-checkov)-values.yaml` as no extra values are required if deployment markers aren't enabled. (#621)
- CI: add `checkov` values file that covers all default enabled components. (#621)
- CI: sort list of `source_fragments` in CI values files. (#622, #623)
- CI: check automount service account policy against Job in tests. (#625)
- CI: refactor test users in integration tests. (#626)
- CI: fix flaking tests when checking upgrades. (#627)
- CI: in tests, wait for all replicasets to be ready before checking service endpoints and monitored pods. (#629)
- CI: in tests for pods to services labels match, skip pods part of a previous-generation replicaset. (#630)
- CI: fix warnings about wrong checkout action parameters. (#636)


# ESS Community Helm Chart 25.7.0 (2025-07-02)

### Changed

- Don't set `hostAliases` on the Synapse config job as it just operates on the config files. (#574)
- Upgrade Element Web to v1.11.105.

  Highlights:
  * Improvements to the new room list (in labs)
  * Support for custom message components via Module API

  Full Changelog:
  * [v1.11.105](https://github.com/element-hq/element-web/releases/tag/v1.11.105)

  (#575)
- Upgrade Synapse to v1.133.0.

  Highlights:
  * Add support for the [MSC4260 user report API](https://github.com/matrix-org/matrix-spec-proposals/pull/4260)

  Full Changelog:
  * [v1.133.0](https://github.com/element-hq/synapse/releases/tag/v1.133.0)

  (#577)
- Upgrade Matrix Authentication Service to v0.18.0.

  Full Changelog:
  * [v0.18.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v0.18.0)

  (#578)
- Document how to re-run integration tests from scratch. (#579)
- Better document uninstallation of, and the stores of state managed by the chart. (#585)
- Don't push chart OCI images for every PR. (#589, #591)
- Tweak changelog sections ordering. (#600)

### Fixed

- Fix Matrix RTC SFU `ServiceMonitor` not working. (#569)
- Fix Matrix Authentication Service not using the `hostAliases` set in the values. (#573)
- Fix Matrix RTC Authoriser not having default `hostAliases` values. (#573)
- Fix Postgres and Synapse Media `storageClassName` configuration not being respected.

  **Warning** Previously `synapse.media.storage.storageClass` and `postgres.storage.storageClass`
  were in the values file and associated schema. These values were accidentally silently ignored
  and all chart-managed `PersistentVolumeClaims` were constructed without `spec.storageClassName`
  set, using the cluster default `StorageClass`.

  The values file and associated schema have been updated so that the values are now
  `synapse.media.storage.storageClassName` and `postgres.storage.storageClassName`. The previous
  values are disallowed by the schema. Setting these values after the initial install could 
  cause the `PersistentVolumeClaims` to be recreated, with associated data-loss. Only set
  `synapse.media.storage.storageClassName` or `postgres.storage.storageClassName` on initial
  installation. (#582, #583)

### Removed

- Remove Matrix RTC Authoriser `ServiceMonitor` as the Authoriser has no metrics endpoint. (#569)
- Remove `hostAliases` support from Matrix RTC SFU as it doesn't make outbound requests. (#574)

### Internal

- CI: test that the default values includes stub settings (and thus comments) for various properties. (#573)
- CI: test that `hostAliases` are correctly set for all workloads that make outbound requests. (#573, #574)
- CI: improve the test cluster setup for Matrix RTC. (#579)
- CI: improve testing of chart managed `PersistentVolumeClaims`. (#582)
- CI: test nodeSelectors are appropriately configured. (#583)
- CI: simplify which commit we checkout. (#586)
- CI: switch to using `pull_request` triggers. (#586)
- CI: don't push artifacthub metadata on PRs. (#589)
- CI: be explicit about what permissions are workflow/job requires. (#589)
- CI: allow dyff job to work on forks. (#589, #594)
- Tests: don't check services matching labels against terminating pods. (#595, #598)
- Add `yamllint` ct dependency to poetry.toml. (#596)
- Prepare for 25.7.0 release. (#597)
- CI: run the preview-changelog job on main and manually as well as PRs. (#599)


# ESS Community Helm Chart 25.6.2 (2025-06-19)

### Fixed

- matrix-tools: Skip any completed pods when scaling down synapse pods in syn2mas migration. (#546)
- Fix Matrix RTC's SFU constructing an invalid Service if given too wide a nodePort range. (#549)
- Fix comments around the image tag and digest in the values file. (#553)
- Fix certificate name inconsistencies between setup docs and values file fragments. (#555)
- Fix MatrixRTC RTCSession Error if a `push-rules` Synapse worker is enabled. (#557)
- Fix `extraEnv` with duplicate keys not being correctly merged. (#559)
- Document the need for removal of generated secrets & deployment marker configmap when uninstalling. (#567)

### Changed

- Omit the UDP port range metadata for Matrix RTC's SFU if the range is larger than 100 ports. (#549)
- Remove warning about deprecated `prometheus_port` config value in Matrix RTC SFU. (#550)
- Upgrade Matrix RTC SFU to v1.9.0.

  Full changelogs:
  * [v1.8.0](https://github.com/livekit/livekit/releases/tag/v1.8.0)
  * v1.8.1 - no changelog
  * v1.8.2 - no changelog
  * [v1.8.3](https://github.com/livekit/livekit/releases/tag/v1.8.3)
  * [v1.8.4](https://github.com/livekit/livekit/releases/tag/v1.8.4)
  * [v1.9.0](https://github.com/livekit/livekit/releases/tag/v1.9.0)

  (#552)
- Document `extraEnv` in `values.yaml` for every workload. (#559)
- Consistently handle user provided `extraEnv` versus chart configured `env`.

  Chart configured `env` should win. (#559)
- Upgrade Matrix Authentication Service to v0.17.1.

  Highlights:
  * Support Registration Tokens

  Full changelog:
  * [v0.17.0](https://github.com/element-hq/matrix-authentication-service/releases/tag/v0.17.0)
  * [v0.17.1](https://github.com/element-hq/matrix-authentication-service/releases/tag/v0.17.1)

  (#564)
- Upgrade Element Web to v1.11.104.

  Highlights:
  * Implement [MSC4155](https://github.com/matrix-org/matrix-spec-proposals/pull/4155) invite filtering
  * Add `/share?msg=` endpoint using the forward message dialogue

  Full changelog:
  * [v1.11.104](https://github.com/element-hq/element-web/releases/tag/v1.11.104)

  (#565)
- Upgrade Synapse to v1.132.0.

  Highlights:
  * Implement [MSC4155](https://github.com/matrix-org/matrix-spec-proposals/pull/4155) invite filtering
  * Successful requests to `/_matrix/app/v1/ping` will now force Synapse to reattempt delivering transactions to appservices.

  Full changelog:
  * [v1.132.0](https://github.com/element-hq/synapse/releases/tag/v1.132.0)

  (#566)

### Internal

- CI: Test upgrades against the nearest reachable tag and not the most recently created. (#547)
- CI: Enhance dyff jobs output to print yaml manifests in a single block code. (#548)
- Ensure example `NodePort` values use ports within `kind`'s `NodePort` range. (#551)
- Run integration tests with `kind` 0.29.0. (#563)


# ESS Community Helm Chart 25.6.1 (2025-06-10)

### Security

- Upgrade Element Web to v1.11.103 for GHSA-x958-rvg6-956w.

  Resolves GHSA-x958-rvg6-956w
  * Check the sender of an event matches owner of session, preventing sender spoofing by homeserver owners.

  (#541)

### Added

- Add support for Syn2Mas migration. See `matrixAuthenticationService.syn2mas` documentation in values file for more information. (#454, #527)

### Changed

- Name secrets mounted based on a hash of their names instead of an index. (#519)
- `matrixRTC.sfu.additional` now uses the same `additional` properties schema as Matrix Authentication Service and Synapse.

  Values can be specified inline:
  ```yaml
  matrixRTC:
    sfu:
      additional:
        your-config.yaml: |
          example: value
  ```

  Or referencing an existing `Secret` in-cluster:
  ```yaml
  matrixRTC:
    sfu:
      additional:
        another-config.yaml:
          configSecret: "{{ $.Release.Name }}-mrtc-external"
          configSecretKey: config
  ```

  Setting `matrixRTC.sfu.additional` to a string value is no longer supported or allowed. (#529, #535)
- matrix-tools: Update to 0.5.2 to support syn2mas migration command. (#532, #534)

### Internal

- CI: Dont pass `go-version` to golanglint-ci action. (#521)
- CI: Truncate added files in dyff comment. (#523)
- CI: Test chart upgrades. (#524)
- CI: Run mypy against integration tests. (#525)
- CI: Add a test to assert labels key length. (#528)
- CI: Expect 429s to happen on chart version upgrade tests. (#530)
- CI: Fix an internal issue where aiohttp expected errors were not retried. (#531)
- Rename the templates for Matrix RTC Authorisation Service for clarity. (#533)
- CI: Test that podAntiAffinity for Deployments is not strict anti-affinity. (#536, #537)
- CI: Verify podAntiAffinity against kubeconform. (#540)
- Don't send set changelog entries in the artifacthub metadata. (#542)
- Reorder changelog sections. (#544)


# ESS Community Helm Chart 25.6.0 (2025-06-05)

### Added

- Add a new `deploymentMarkers` job which prevent users from accidentally breaking their setup by choosing incompatible values. (#487)
- Add a `NOTES.txt` for some post-setup messages. (#491, #509)
- Add support for Matrix Authentication Service replicas. (#515)
- Add support for configuring replicas of the `matrix-rtc-authorization-service`. (#515)

### Changed

- Improve the validation that for every image the tag and/or the digest is set. (#484)
- Improve the validation on set properties for external Postgreses. (#485)
- Add example config for Nginx reverse proxy. (#486)
- Restrict some Synapse worker names such that release_names can be 29 characters long. (#494)
- Improve validation messages for values that are templated. (#497)
- Rename `synapse-check-config-hook` to `synapse-check-config` for consistency with `init-secrets` and `deployment-markers`. (#501)
- Upgrade Synapse to v1.131.0.

  Highlights:
  - Add msc4263_limit_key_queries_to_users_who_share_rooms config option as per MSC4263.
  - Add option to allow registrations that begin with `_`.
  - Add support for calling Policy Servers (MSC4284) to mark events as spam.

  (#511)
- Upgrade Element Web to v1.11.102.

  Highlights:
  - Modernize the recovery key input modal.
  - General enhancements of the new room list (sorting, filtering, etc.).
  - Prompt the user when key storage is unexpectedly off.

  (#512)
- Configure Synapse appropriately for Element Call when matrixRTC is enabled. (#513)
- Set deployments `maxUnavailable` to 0 if it has only one replicas. (#515)
- Pull Synapse from ghcr.io/element-hq/synapse rather than the legacy repository on Docker Hub. (#517)
- Pull Element Web from ghcr.io/element-hq/element-web rather than the legacy repository on Docker Hub. (#518)

### Fixed

- Fix routing to the initial-synchrotron worker in HAProxy. (#494)
- Ensure the names of Secrets in volume/volumeMounts don't have names that are too long. (#495)
- Fix initial-synchrotron paths not falling back to main if the worker is unavailable. (#508)
- Matrix RTC: Set proxy timeout and enforce disabled buffering `nginx-ingress` `controllerType` annotations if SFU is enabled. (#514)

### Internal

- Add tests to verify that `additional.config/configSecret/configSecretKey` is properly being used. (#483)
- Make it easier to write manifest tests where sub-components and sidecars read values from their parent component. (#484)
- Refactor to use a common helper for `render-config` additional mechanism. (#488)
- Improve error messages in pod images manifest test. (#492)
- Simplify manifest tests by making template_to_deployable_details an import not a fixture. (#492)
- Use internal render-config helper for the SFU keys.yaml generation. (#493)
- Validate manifest name lengths in tests. (#494)
- Validate that workload selectors match the labels in the template. (#496)
- Validate that covering manifests are named consistently with what they cover. (#496)
- Validate manifests set the namespace correctly. (#496)
- Consistently use template_id helper for identifying manifests. (#500)
- Unpin from Helm 3.17.3 after https://github.com/helm/helm/issues/30878 / https://github.com/helm/helm/issues/30880 are fixed. (#502)
- CI: Enhance dyff comment formatting. (#510)


# ESS Community Helm Chart 25.5.1 (2025-05-23)

### Changed

- Make probe defaults explicit. (#433)
- Replace the use of initialDelaySeconds in default probes with adjustments to the startupProbes. (#434)
- Document Synapse's Redis extraEnv property in values.yaml. (#458)
- Remove wellKnownDelegation.ingress.host from values.yaml as serverName is used for the well-known Ingress. (#467)
- Synapse: Upgrade from v1.129.0 to v1.130.0.

  Highlights :
  - Add an Admin API endpoint GET /_synapse/admin/v1/scheduled_tasks to fetch scheduled tasks.
  - Add config option user_directory.exclude_remote_users which, when enabled, excludes remote users from user directory search results.
  - Add support for handling GET /devices/ on workers.
  - Fix a longstanding bug where Synapse would immediately retry a failing push endpoint when a new event is received, ignoring any backoff timers.
  - Fix to pass leave from remote invite rejection down Sliding Sync.

  Full Changelog: https://github.com/element-hq/synapse/releases/tag/v1.130.0

  (#472, #479)
- Element Web: upgrade from v1.11.100 to v1.11.101.

  Highlights:
  * Improve identity reset UI

  Full Changelog: https://github.com/element-hq/element-web/releases/tag/v1.11.101

  (#475)
- Postgres: Pretty print internal postgres env variables. (#476)

### Fixed

- CI: Make sure that released versions follow the semver semantics. (#469, #474)

### Internal

- Fix some values files being accidentally skip in the manifest tests. (#465)
- Update manifest tests so that the components under test don't need to be enumerated. (#465)
- Move job validating copyright date header into distinct workflow job. (#466)
- Pin to Helm 3.17.3 in the integration tests. (#468)
- Rename exemple values files named `*-test-postgres-*` to `*-postgres-*`. (#470)
- Add an internal test to check that the kubernetes volume name is not too long. (#471)
- Add a CI job to preview the changelog for the next release. (#473)
- Correctly manage the copyright date header line for Chart.yaml. (#474)
- Add manifest test to ensure YAML/JSON written to `ConfigMaps` and `Secrets` is valid. (#480)


# ESS Community Helm Chart 25.04.01 (2025-05-16)

### Changed

- The ESS Community Helm Chart now uses a new versioning scheme, time-based : `YY.MM.XX`. (#455)

### Fixed

- Fix built-in Element Web not being allowed to be overridden. (#456)

### Internal

- Improve the reliability of the ServiceMonitor tests. (#452)
- Add manifest test to confirm that all Pods have configurable resources. (#453)
- Make it easier to test manifests for Synapse workers. (#453)


# ESS Community Helm Chart 0.12.0 (2025-05-16)

### Changed

- Allow configuration of thresholds and frequencies for all startupProbes. (#430)
- Allow configuration of thresholds and frequencies for all readinessProbes. (#430)
- Ensure Synapse's Redis has a startupProbe. (#435)
- Ensure all Postgres containers have a startupProbe. (#435)
- Ensure HAProxy has a startupProbe when Synapse isn't enabled. (#437)
- Allow configuration of thresholds and frequencies for all livenessProbes. (#445)
- Matrix RTC Authorizer is now named Matrix RTC Authorisation Service. (#446)
- Minor quick setup docs fixes and improvements. (#448)

### Fixed

- Fix Synapse per-worker resource overrides not being respected. (#438)
- Fix required message when matrix-tools image tag is missing in MAS templates. (#441)

### Internal

- Add a job to compare the generated templates between source and target branches in PRs. (#431, #436, #443, #444, #447, #450)
- MAS: Fix schema schema method calls do not need to respecify default keys values. (#432)
- Fix pytest CA was re-generated on every pytest run, preventing tests in local browsers. (#442)
- Check files copyright dates in CI. (#449)


# ESS Community Helm Chart 0.11.3 (2025-05-08)

### Changed

- Upgrade to Synapse v1.129.0. (#427)
- Upgrade to Matrix Authentication Service 0.16.0. (#427)
- Update Element Web to v1.11.100. (#428)


# ESS Community Helm Chart 0.11.2 (2025-05-06)

### Changed

- matrix-tools: Update Go to 1.24. (#405)
- matrix-tools: Update to 0.3.5. (#407)
- Update Architecture diagram. (#408)
- Upgrade to Matrix Authentication Service 0.15.0. (#412)
- Matrix Authentication Service: perform database migration with an init container, instead of on the startup of the main container. (#416)
- HAProxy: Use ACLs instead of `backup` for synapse main worker fallback. (#417)
- Add extraEnv support to HAProxy, Synapse Redis, Postgres Exporter and Init Secrets so that all components support it. (#421)

### Fixed

- Fix typo in Matrix Authentication Service additional comment docs. (#422)

### Internal

- Type check manifest tests. (#409)
- Use released version of pytest-asyncio-cooperative. (#411)
- Make scripts executable. (#415)
- Fix ServiceAccount manifest being unreliable. (#418)
- Fix typo in integration test utility function. (#419)
- All varying of values for sidecars in manifest tests. (#420)


# ESS Community Helm Chart 0.11.1 (2025-04-29)

### Changed

- HAProxy: Return 405 on POST, PUT and DELETE requests on well-known files. (#398)
- Make it possible to configure the Helm keep/delete resource-policy for PersistentVolumeClaims and default to keeping them. (#399)

### Fixed

- Fix merging of boolean in configurations. (#395)
- Synapse: Fix missing `federation-inbound` worker from values schema. (#404)

### Internal

- Add a test for running Matrix RTC on its own. (#396)


# ESS Community Helm Chart 0.11.0 (2025-04-25)

### Changed

- Ensure that all managed Pods have the same labels as their parent Deployment/StatefulSet/Job (apart from the helm.sh/chart label). (#379)
- Move Postgres config/secret hashes to labels for consistency with all other components. (#380)
- Enforce a common format for k8s.element.io labels across components. (#380)
- Extract Synapse config into template files like other config. (#381)
- Ensure app.kubernetes.io/version labels are properly escaped & restricted. (#386)
- Update matrix-tools dependencies and release 0.3.4. (#393)

### Fixed

- Fix chart upgrade causing a restart of the whole stack. (#373)
- Fix `helm.sh/chart` label size with dev builds. (#385)

### Internal

- Make sure `serverName` can be templatized in Synapse and ElementWeb config. (#387)
- Run manifest tests in parallel. (#388)
- Dynamically find integration tests to run. (#388)
- Synapse: Make sure postgres host can be templatized. (#390)
- Add tests to check that containers env values is a string. (#391)


# ESS Community Helm Chart 0.10.1 (2025-04-16)

### Added

- Matrix Authentication Service: Allow to setup without enabling auth delegation in Synapse using `matrixAuthenticationService.preMigrationSynapseHandlesAuth`. (#371)

### Changed

- Upgrade Element Web to 1.11.97. (#363)
- Add caching headers for Element Web as per upstream. (#363)
- Upgrade Synapse to 1.128.0. (#365)
- Synapse: Longer startup probes for single workers. (#366)
- Correct docs as `setup_test_cluster.sh` no longer manages a Postgres directly, the chart installs it. (#369)
- Synapse: Make health listener resource name explicit. (#374)
- Synapse: Add trailing slash to public_baseurl. (#375)

### Fixed

- Fix `topologySpreadConstraints` `selectorLabel.matchLabels` keys could not be nuked. (#367)
- Fix Synapse default topologySpreadConstraints not matching pod labels. (#367)

### Internal

- Add tests to verify that template rendering is idempotent. (#372)


# ESS Community Helm Chart 0.10.0 (2025-04-09)

### Added

- Add matrixRTC backend deployment. (#343)

### Fixed

- matrix-tools: Fix rendered file permissions, from 664 to 440. (#343, #350)
- Fix Matrix Authentication Service Deployment missing resources. (#359)


# ESS Community Helm Chart 0.9.0 (2025-04-04)

### Added

- Synapse: Allow to inject appservices registration from secrets. (#331)
- Document how to migrate from existing installations. (#333)
- Add an example for Apache2 to the reverse proxy documentation in the README. (#344)

### Changed

- Improved README.md structure and content. (#303)
- Enable TLS by default on all ingresses. This can be disabled using `tlsEnabled: false` globally or per ingress. (#348)

### Deprecated

- `synapse.appservices[].registrationFileConfigMap` is now `synapse.appservices[].configMap`. (#331)

### Fixed

- Synapse/Matrix Authentication Service: Fix shared OIDC secret when init secret is disabled. (#336)
- Postgres password: Generate only required passwords. (#342)
- Synapse: Use consistenly the hostname of the pod as worker names. (#346)

### Internal

- Fix artifacthub chart versions list. (#334)
- Enhance secrets path detection consistency with render-config containers. (#338)


# ESS Community Helm Chart 0.8.0 (2025-03-27)

### Changed

- Upgrade Element Web to 1.11.96. (#329)

### Fixed

- Fixed Helm template for Synapse deployment not properly configuring appservice registration file path. (#326)

### Security

- Synapse: Update to v1.127.1 for CVE-2025-30355 fix. (#328)


# ESS Community Helm Chart 0.7.3 (2025-03-25)

### Added

- Configure well-known to use Element LiveKit by default. (#306)

### Changed

- Upgrade to Synapse 1.126.0. (#302)
- Update file licenses to prepare for public release. (#304)
- Matrix Authentication Service does not need to prune database anymore, OIDC providers are being disabled instead. (#307)
- Make it possible to provide additional command line arguments to Synapse. (#309)
- Have Synapse load Matrix Authentication Service shared secrets from files. (#309)
- Update matrix-tools to 0.3.2. (#322)

### Fixed

- matrix-tools: Various internal fixes after upgrading linter. (#323)

### Internal

- Don't automatically trust matrix-org or element-hq GitHub actions. (#308)
- Validate the chart uses path options in Synapse where possible. (#309)
- Group minor version and patch version dependabot updates. (#319)


# ESS Community Helm Chart 0.7.2 (2025-03-18)

### Added

- Added documentation for a quick bootstrap setup. (#210)
- Add `ingress.controllerType` field to apply automatic behaviours depending on ingress controller. Supports `ingress-nginx` only for now. (#281)

### Changed

- Disable immediate redirect to Matrix Authentication Service in Element Web. (#266)
- matrix-tools is now a public image. (#267)
- Update the init-secrets job to use the common Pod spec helper so that its behaviour is consistent with all other components. (#283)
- Bump matrix-tools to 0.3.1. (#300)

### Fixed

- Avoid to mount unused generated secrets in internal postgres container. (#260)
- Fix the wrong labels being applied to the Synapse Config Check Hook Job. (#270)
- Fixing missing type from the Postgres Secret. (#271)
- README: Fix broken internal links and missing `ess` namespace argument. (#286)

### Internal

- Support running manifest tests with multiple components. (#272)
- Speed up the manifest test runs. (#273)
- Manifests tests: handle noqa at the mount key level. (#274)
- CI: Update kind to 0.27.0. (#275)
- Enhance helm helper for ingress tls section. (#280)
- Test that ServiceMonitors aren't created when the ServiceMonitor CRD isn't present in cluster. (#282)
- CI: Use hash-pinning for third-parties github actions. (#284)
- Make kubeconform aware of ServiceMonitor CRDs. (#285)
- Run kubeconform in strict mode to catch additional unexpected properties. (#285)
- Add linting of our GitHub actions. (#288)
- Remove orphan GitHub actions runner image. (#289)


# ESS Community Helm Chart 0.7.1 (2025-03-07)

### Fixed

- Docs: Fix Architecture diagram wrong link between HAProxy & MAS. (#259)
- Fix secret names when using in-helm values. (#262)

### Internal

- ct-lint.sh : Run the check about $ forbidden in .tpl files. (#261)


# ESS Community Helm Chart 0.7.0 (2025-03-07)

### Added

- Redirect on the serverName domain to the chat app unless it is a well-known path. (#231)
- Support QR code login when MAS is enabled. (#232)
- Synapse: Add a config check as Helm hook. (#238)
- Document deployment Architecture in `docs/ARCHITECTURE.md`. (#239)
- Support passing extra environment variables to Element Web. (#247)
- Allow configuration of Synapse's `max_upload_size` via Helm values. (#251)

### Changed

- Upgrade to Postgres Exporter 0.17.0 for better Postgres 17 compatibility. (#230)
- Be consistent about replicas for components. (#241)
- Rename instances to replicas for Synapse workers to be consistent with other components. (#242)
- Ensure all managed `Secrets` set their `type`. (#243)
- Ensure all ports have names. (#244)
- Update CI values files so they can be used as examples for the new users. (#245)
- Don't gate enabling presence in Synapse on having a presence writer worker, use the Synapse defaults and allow easy configuration. (#252)
- ElementWeb additional config now expect multiple subproperties. (#254)
- Improve credential validation. (#255)

### Fixed

- Fix an issue where postgres port could be missing when waiting for db. (#233)
- Fixed recent Element Web versions failing to start when running with GID of 0. (#247)
- Fix Secret name in the config check job for the Postgres password when provided in the Helm values file. (#248)
- Fix incorrect missing context error messages from some configuration files. (#250)

### Internal

- Allow to call tpl in well-known .ingress.host elementWeb redirect. (#240)
- Run integration pytests with GID 0 to detect some read-only filesystem issues. (#247)
- Add test to verify that hook-weights are properly configured. (#249)
- Extract Matrix Authentication Service env vars for rendering into a helper. (#253)


# ESS Community Helm Chart 0.6.1 (2025-02-21)

### Added

- Support the push-rules stream writer worker in Synapse. (#228)

### Changed

- Update Synapse worker paths support for 1.124.0. (#228)

### Fixed

- Fix HAProxy not starting with some combinations of Synapse workers. Regression in 0.6.0. (#228)


# ESS Community Helm Chart 0.6.0 (2025-02-21)

### Added

- Add support to deploy Matrix Authentication Service. (#132)
- Add an init-secrets job that will prepare internal secrets automatically if they are not provided by the user. (#142)
- Synapse: if SigningKey is not provided, it is now automatically generated. (#146)
- Added the ability to generate the registration shared secret if no value or external Secret is configured. (#163)
- Add internal PostgreSQL database. (#172)
- Config ElementWeb automatically for best Matrix Authentication Service integration. (#194)
- Publish the chart on artifact-hub.io. (#213)
- Add a value to automatically configure CertManager on all ingresses. (#217)

### Changed

- Project name is now ESS Community Helm Chart instead of Element Community Helm Chart. (#141)
- Update READMEs to improve the user on-boarding experience. (#167)
- Support arm64 in matrix-tools image. (#170)
- Update Synapse to v1.124.0. (#179)
- Update Element Web to v1.11.92. (#180)
- Refactor synapse pod to be compatible with minimal container images. (#207)
- Upgrade to Matrix Authentication Service 0.14.0. (#209)
- Configure Element Web for location sharing. (#215)
- Configure Element Web to submit RageShakes. (#215)
- Set the LD_PRELOAD environment variable only in containers that run Synapse. (#218)
- ElementWeb "additional" value now expect a json string. (#219)
- HAProxy: Return 429 error code as Matrix Json format. (#220)
- Improve Synapse HTTP request handling when Synapse processes are restarting. (#225)

### Fixed

- Fixed version label on well-known delegation templates. (#143)
- Fixed the HAProxy Service being headless rather than ClusterIP. (#144)
- Fix missing labels on the Pod created by the initSecret Job. (#156)
- Hard-code the org.opencontainers.image.licenses label be accurate. (#168)
- Fix Matrix Authentication Service render-config container was lacking extraEnv. (#199)
- Fix typo in postgresql values documentation. (#206)
- Postgres: Fixed duplicated ports in statefulset. (#208)
- Postgres: Fix an issue where initialization would fail to happen properly. (#221)
- Fix an issue where HAProxy would be ready despite not having any backend ready to answer. (#224)

### Internal

- Add tests that all manifests have expected labels. (#143)
- Add test that all StatefulSets have headless Services associated with them. (#144)
- Dev dependency updates, include Jinja security. (#145)
- Add gotestfmt in golang CI tests. (#147)
- Pytest: Build matrix-tools in test fixtures. (#148)
- Disable initSecrets in pytests which do not need it. (#149)
- Simplify checkov and kubeconform checks in CI. (#150)
- Use a dynamic Helm release name in the manifest tests. (#151)
- Fix manifest tests issues with shared components, specifically initSecrets. (#152)
- Only build matrix-tools image when necessary. (#153)
- MAS: Make sure legacy auth paths point to MAS service. (#154)
- Add a manifest tests to check pullSecrets list content. (#155)
- Support synthesising Secrets for external and generated Secrets. (#156)
- Use a helper to generate synapse matrix-tools env var. (#157)
- For components with Secrets, always test generated, Helm inlined and external Secrets. (#159)
- Assemble the CI values files from fragments to reduce c/p'ing and make it easy to see the purpose of some values. (#159)
- Reduce retries on HTTP Post/Get in integration tests. (#161)
- Fix local builds of matrix-tools not being available to pytest. (#162)
- Dont print failed yaml with matrix-tools without `DEBUG_RENDERING` enabled. (#164)
- Minor fix in secrets consistency manifest test when a list contains strings. (#165)
- Integration tests: Enhance handling of ingresses readiness. (#166)
- Setup dependabot to manage GHA, go.mod and Poetry deps. (#169)
- matrix-tools: Internal commands handling refactoring. (#171)
- Fix GitHub Actions dependabot config. (#178)
- Sort the keys in values files assembled from fragments. (#186)
- CI values: Do not define `initSecrets` `postgres` in tests, their behaviour depends on other components presence. (#188)
- CI values files: Dont nullify secret/secretKey. (#189)
- Tests: verify mounts and & configs consistency. (#192)
- Better handling of chart values inconsistencies and test it in CI. (#193)
- Matrix-Tools CI: Move Write permissions to push job. (#202)
- Move CI to public github runners. (#204)
- CI: Fix potential security injection. (#205)
- Improve Synapse values files fragments. (#211)
- Fix CI not detecting issues introduced by PRs. (#212)
- Tests: Improve endpoints status verifications. (#226)


# ESS Community Helm Chart 0.5.0 (2025-01-30)

### Added

- Add a matrix-tools image to handle dynamic config build and other chart features. (#131)
- Add support for .well-known/matrix/support in Well Known Delegation. (#133)
- Add the possibility to quote substituted env variable from synapse config. (#137)

### Internal

- Remove towncrier newsfragments after release. (#130)
- Correct SHA used in dev builds to match the commit sha. (#134)
- Make sure matrix-tools is part of ess-helm namespace. (#135)


# ESS Community Helm Chart 0.4.1 (2025-01-23)

### Added

- Add changelog to releases. (#118)
- Document the behaviour common sections of the values file in the README. (#126)

### Fixed

- Fix an issue where the secret key was wrong when using synapse.postgres.value. (#119)
- Fixed an issue with changelogs generation. (#121)

### Internal

- Enhance tests to ensure that secrets mounted in configmaps point to existing mounted secret keys. (#120)
- Tests: Ensure volumes mounts point to existing volumes names. (#122)
- CI: improve licensing checks. (#123)
- Tests: Verify that we can find secrets in env variables. (#124)
- Add internal towncrier change category. (#127)
