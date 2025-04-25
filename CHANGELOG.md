<!--
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

<!-- towncrier release notes start -->

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
