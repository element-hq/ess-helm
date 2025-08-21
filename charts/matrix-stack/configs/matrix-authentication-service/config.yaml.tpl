{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root }}
{{- with required "matrix-authentication-service/config.yaml.tpl missing context" .context }}
{{- $context := . -}}
http:
  public_base: "https://{{ tpl .ingress.host $root }}"
  listeners:
  - name: web
    binds:
    - host: 0.0.0.0
      port: 8080
    resources:
    - name: human
    - name: discovery
    - name: oauth
    - name: compat
    - name: assets
    - name: graphql
      # This lets us use the GraphQL API with an OAuth 2.0 access token,
      # which we currently use in the ansible modules and in synapse-admin
      undocumented_oauth2_access: true
    - name: adminapi
  - name: internal
    binds:
    - host: 0.0.0.0
      port: 8081
    resources:
    - name: health
    - name: prometheus
    - name: connection-info


database:
{{- if .postgres }}
{{- with .postgres }}
  uri: "postgresql://{{ .user }}:${POSTGRES_PASSWORD}@{{ tpl .host $root }}:{{ .port }}/{{ .database }}?{{ with .sslMode }}sslmode={{ . }}&{{ end }}application_name=matrix-authentication-service"
{{- end }}
{{- else if $root.Values.postgres.enabled }}
  uri: "postgresql://matrixauthenticationservice_user:${POSTGRES_PASSWORD}@{{ $root.Release.Name }}-postgres.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}:5432/matrixauthenticationservice?sslmode=prefer&application_name=matrix-authentication-service"
{{ end }}

telemetry:
  metrics:
    exporter: prometheus

{{- /*
  If Synapse is enabled the serverName is required by Synapse,
  and we can use internal Synapse shared secret.
  If Synapse is disabled, users should provide the whole matrix block,
  including the servername and the secret, as additional configuration.
*/ -}}
{{- if $root.Values.synapse.enabled }}
matrix:
  homeserver: "{{ tpl $root.Values.serverName $root }}"
  secret_file: /secrets/{{
                include "element-io.ess-library.init-secret-path" (
                      dict "root" $root
                      "context" (dict
                        "secretPath" "matrixAuthenticationService.synapseSharedSecret"
                        "initSecretKey" "MAS_SYNAPSE_SHARED_SECRET"
                        "defaultSecretName" (include "element-io.matrix-authentication-service.secret-name" (dict "root" $root "context" .))
                        "defaultSecretKey" "SYNAPSE_SHARED_SECRET"
                      )
                  ) }}
  endpoint: "http://{{ include "element-io.synapse.internal-hostport" (dict "root" $root "context" (dict "targetProcessType" "main")) }}"
{{- /* When in syn2mas dryRun mode, migration has not run yet
We don't want MAS to change data in Synapse
*/}}
{{- if and .syn2mas.enabled .syn2mas.dryRun }}
  kind: synapse_read_only
{{- else }}
  kind: synapse_modern
{{- end }}
{{- end }}

policy:
  data:
    admin_clients: []
    admin_users: []
    client_registration:
      allow_host_mismatch: false
      allow_insecure_uris: false

secrets:
  encryption_file: /secrets/{{
                include "element-io.ess-library.init-secret-path" (
                      dict "root" $root
                      "context" (dict
                        "secretPath" "matrixAuthenticationService.encryptionSecret"
                        "initSecretKey" "MAS_ENCRYPTION_SECRET"
                        "defaultSecretName" (include "element-io.matrix-authentication-service.secret-name" (dict "root" $root "context" .))
                        "defaultSecretKey" "ENCRYPTION_SECRET"
                      )
                    ) }}
  keys:
{{- with required "privateKeys is required for Matrix Authentication Service" .privateKeys }}
  - kid: rsa
    key_file: /secrets/{{
                include "element-io.ess-library.init-secret-path" (
                      dict "root" $root
                      "context" (dict
                        "secretPath" "matrixAuthenticationService.privateKeys.rsa"
                        "initSecretKey" "MAS_RSA_PRIVATE_KEY"
                        "defaultSecretName" (include "element-io.matrix-authentication-service.secret-name" (dict "root" $root "context" $context))
                        "defaultSecretKey" "RSA_PRIVATE_KEY"
                      )
                    ) }}
  - kid: prime256v1
    key_file: /secrets/{{
                include "element-io.ess-library.init-secret-path" (
                      dict "root" $root
                      "context" (dict
                        "secretPath" "matrixAuthenticationService.privateKeys.ecdsaPrime256v1"
                        "initSecretKey" "MAS_ECDSA_PRIME256V1_PRIVATE_KEY"
                        "defaultSecretName" (include "element-io.matrix-authentication-service.secret-name" (dict "root" $root "context" $context))
                        "defaultSecretKey" "ECDSA_PRIME256V1_PRIVATE_KEY"
                      )
                  ) }}
{{ with .ecdsaSecp256k1 }}
  - kid: secp256k1
    key_file: /secrets/{{
                include "element-io.ess-library.provided-secret-path" (
                        dict "root" $root
                        "context" (dict
                          "secretPath" "matrixAuthenticationService.privateKeys.ecdsaSecp256k1"
                          "defaultSecretName" (include "element-io.matrix-authentication-service.secret-name" (dict "root" $root "context" $context))
                          "defaultSecretKey" "ECDSA_SECP256K1_PRIVATE_KEY"
                        )
                    ) }}
{{- end }}
{{ with .ecdsaSecp384r1 }}
  - kid: secp384r1
    key_file: /secrets/{{
                include "element-io.ess-library.provided-secret-path" (
                        dict "root" $root
                        "context" (dict
                          "secretPath" "matrixAuthenticationService.privateKeys.ecdsaSecp384r1"
                          "defaultSecretName" (include "element-io.matrix-authentication-service.secret-name" (dict "root" $root "context" $context))
                          "defaultSecretKey" "ECDSA_SECP384R1_PRIVATE_KEY"
                        )
                    ) }}
{{- end }}
{{- end }}
experimental:
  access_token_ttl: 86400  # 1 day, up from 5 mins, until EX can better handle refresh tokens

{{- end -}}
