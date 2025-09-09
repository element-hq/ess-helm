{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.matrix-authentication-service.validations" }}
{{- $root := .root -}}
{{- with required "element-io.matrix-authentication-service.validations missing context" .context -}}
{{ $messages := list }}
{{- if not .ingress.host -}}
{{ $messages = append $messages "matrixAuthenticationService.ingress.host is required when matrixAuthenticationService.enabled=true" }}
{{- end }}
{{- if and (not $root.Values.postgres.enabled) (not .postgres) -}}
{{ $messages = append $messages "matrixAuthenticationService.postgres is required when matrixAuthenticationService.enabled=true but postgres.enabled=false" }}
{{- end }}
{{ $messages | toJson }}
{{- end }}
{{- end }}

{{- define "element-io.matrix-authentication-service.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-authentication-service.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-authentication
app.kubernetes.io/name: matrix-authentication-service
app.kubernetes.io/instance: {{ $root.Release.Name }}-matrix-authentication-service
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.syn2mas.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-authentication-service.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-authentication
app.kubernetes.io/name: syn2mas
app.kubernetes.io/instance: {{ $root.Release.Name }}-syn2mas
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}


{{- define "element-io.matrix-authentication-service.config" }}
{{- $root := .root -}}
{{- with required "element-io.matrix-authentication-service.config missing context" .context -}}
{{- (tpl ($root.Files.Get "configs/matrix-authentication-service/config.yaml.tpl") (dict "root" $root "context" .)) }}
{{- end }}
{{- end }}

{{- define "element-io.matrix-authentication-service.configSecrets" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-authentication-service.configSecrets missing context" .context -}}
{{ $configSecrets := list (include "element-io.matrix-authentication-service.secret-name" (dict "root" $root "context" .)) }}
{{- if and $root.Values.initSecrets.enabled (include "element-io.init-secrets.generated-secrets" (dict "root" $root)) }}
{{ $configSecrets = append $configSecrets (printf "%s-generated" $root.Release.Name) }}
{{- end }}
{{- $configSecrets = append $configSecrets (include "element-io.ess-library.postgres-secret-name"
                                            (dict "root" $root "context" (dict
                                                                "essPassword" "matrixAuthenticationService"
                                                                "componentPasswordPath" "matrixAuthenticationService.postgres.password"
                                                                "defaultSecretName" (include "element-io.matrix-authentication-service.secret-name" (dict "root" $root "context" .))
                                                                "isHook" false
                                                                )
                                            )
                                        ) -}}
{{- range $privateKey, $value := .privateKeys -}}
{{- if $value.secret }}
{{ $configSecrets = append $configSecrets (tpl $value.secret $root) }}
{{- end -}}
{{- end -}}
{{- with $root.Values.matrixAuthenticationService }}
{{- with .synapseSharedSecret.secret -}}
{{ $configSecrets = append $configSecrets (tpl . $root) }}
{{- end -}}
{{- with .encryptionSecret.secret -}}
{{ $configSecrets = append $configSecrets (tpl . $root) }}
{{- end -}}
{{- with .additional -}}
{{- range $key := (. | keys | uniq | sortAlpha) -}}
{{- $prop := index $root.Values.matrixAuthenticationService.additional $key }}
{{- if $prop.configSecret }}
{{ $configSecrets = append $configSecrets (tpl $prop.configSecret $root) }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{ $configSecrets | uniq | toJson }}
{{- end }}
{{- end }}


{{- define "element-io.matrix-authentication-service.overrideEnv" }}
{{- $root := .root -}}
env:
- name: "MAS_CONFIG"
  value: "/conf/mas-config.yaml"
{{- end -}}

{{- /* The filesystem structure is `/secrets`/<< secret name>>/<< secret key >>.
        The non-defaulted values are handling the case where the credential is provided by an existing Secret
        The default values are handling the case where the credential is provided plain in the Helm chart and we add it to our Secret with a well-known key.

        These could be done as env vars with valueFrom.secretKeyRef, but that triggers CKV_K8S_35.
        Environment variables values found in the config file as ${VARNAME} are parsed through go template engine before being replaced in the target file.
*/}}
{{- define "element-io.matrix-authentication-service.renderConfigOverrideEnv" }}
{{- $root := .root -}}
{{- with required "element-io.matrix-authentication-service.renderConfigOverrideEnv missing context" .context -}}
env:
- name: POSTGRES_PASSWORD
  value: >-
    {{
      printf "{{ readfile \"/secrets/%s\" | urlencode }}" (
          include "element-io.ess-library.postgres-secret-path" (
              dict "root" $root
              "context" (dict
                "essPassword" "matrixAuthenticationService"
                "initSecretKey" "POSTGRES_MATRIX_AUTHENTICATION_SERVICE_PASSWORD"
                "componentPasswordPath" "matrixAuthenticationService.postgres.password"
                "defaultSecretName" (include "element-io.matrix-authentication-service.secret-name" (dict "root" $root "context" .))
                "defaultSecretKey" "POSTGRES_PASSWORD"
                "isHook" false
              )
          )
        )
    }}
{{- end }}
{{- end }}


{{- define "element-io.matrix-authentication-service.secret-name" }}
{{- $root := .root }}
{{- with required "element-io.matrix-authentication-service.secret-name requires context" .context }}
{{- $isHook := .isHook }}
{{- if $isHook }}
{{- $root.Release.Name }}-matrix-authentication-service-pre
{{- else }}
{{- $root.Release.Name }}-matrix-authentication-service
{{- end }}
{{- end }}
{{- end }}


{{- define "element-io.matrix-authentication-service.configmap-name" }}
{{- $root := .root }}
{{- with required "element-io.matrix-authentication-service.configmap-name requires context" .context }}
{{- $isHook := required "element-io.matrix-authentication-service.configmap-name requires context.isHook" .isHook }}
{{- if $isHook }}
{{- $root.Release.Name }}-matrix-authentication-service-pre
{{- else }}
{{- $root.Release.Name }}-matrix-authentication-service
{{- end }}
{{- end }}
{{- end }}


{{- define "element-io.matrix-authentication-service.synapse-secret-data" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-authentication-service.synapse-secret-data" .context -}}
{{- if $root.Values.synapse.enabled }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "matrixAuthenticationService.synapseSharedSecret" "initIfAbsent" true)) }}
{{- with .synapseSharedSecret.value }}
SYNAPSE_SHARED_SECRET: {{ . | b64enc }}
{{- end }}
{{- end -}}
{{- end -}}
{{- end -}}


{{- define "element-io.matrix-authentication-service.configmap-data" }}
{{- $root := .root -}}
{{- with required "element-io.matrix-authentication-service.configmap-data" .context -}}
mas-config.yaml: |
  {{- include "element-io.matrix-authentication-service.config" (dict "root" $root "context" .) | nindent 2 }}
{{- end -}}
{{- end -}}


{{- define "element-io.matrix-authentication-service.secret-data" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-authentication-service.secret-data" .context -}}
{{- with (include "element-io.matrix-authentication-service.synapse-secret-data" (dict "root" $root "context" .)) }}
{{- . | nindent 2 }}
{{- end }}
{{- with .additional }}
{{- range $key := (. | keys | uniq | sortAlpha) }}
{{- $prop := index $root.Values.matrixAuthenticationService.additional $key }}
{{- if $prop.config }}
  user-{{ $key }}: {{ $prop.config | b64enc }}
{{- end }}
{{- end }}
{{- end }}
{{- with (.postgres).password }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "matrixAuthenticationService.postgres.password" "initIfAbsent" false)) }}
{{- with .value }}
  POSTGRES_PASSWORD: {{ . | b64enc }}
{{- end }}
{{- end }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "matrixAuthenticationService.encryptionSecret" "initIfAbsent" true)) }}
{{- with .encryptionSecret }}
{{- with .value }}
  ENCRYPTION_SECRET: {{ . | b64enc }}
{{- end }}
{{- end }}
{{- with required "privateKeys is required for Matrix Authentication Service" .privateKeys }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "matrixAuthenticationService.privateKeys.rsa" "initIfAbsent" true)) }}
{{- with .rsa }}
{{- with .value }}
  RSA_PRIVATE_KEY: {{ . | b64enc }}
{{- end }}
{{- end }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "matrixAuthenticationService.privateKeys.ecdsaPrime256v1" "initIfAbsent" true)) }}
{{- with .ecdsaPrime256v1 }}
{{- with .value }}
  ECDSA_PRIME256V1_PRIVATE_KEY: {{ . | b64enc }}
{{- end }}
{{- end }}
{{- with .ecdsaSecp256k1 }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "matrixAuthenticationService.privateKeys.ecdsaSecp256k1" "initIfAbsent" false)) }}
{{- with .value }}
  ECDSA_SECP256K1_PRIVATE_KEY: {{ . | b64enc }}
{{- end }}
{{- end }}
{{- with .ecdsaSecp384r1 }}
{{- include "element-io.ess-library.check-credential" (dict "root" $root "context" (dict "secretPath" "matrixAuthenticationService.privateKeys.ecdsaSecp384r1" "initIfAbsent" false)) }}
{{- with .value }}
  ECDSA_SECP384R1_PRIVATE_KEY: {{ . | b64enc}}
{{- end }}
{{- end }}
{{- end -}}
{{- end }}
{{- end -}}


{{- define "element-io.matrix-authentication-service.render-config-container" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-authentication-service.render-config missing context" .context -}}
{{ include "element-io.ess-library.render-config-container" (dict "root" $root "context" (
        dict "additionalPath" "matrixAuthenticationService.additional"
              "nameSuffix" "matrix-authentication-service"
              "containerName" (.containerName | default "render-config")
              "templatesVolume" (.templatesVolume | default "plain-config")
              "overrides" (list "mas-config.yaml")
              "outputFile" "mas-config.yaml"
              "resources" .resources
              "containersSecurityContext" .containersSecurityContext
              "extraEnv" .extraEnv
              "isHook" .isHook)) }}
{{- end }}
{{- end }}


{{- define "element-io.matrix-authentication-service.syn2masConfigSecrets" -}}
{{- $root := .root -}}
{{- with required "element-io.matrix-authentication-service.syn2masConfigSecrets missing context" .context -}}
{{- $masSecrets := include "element-io.matrix-authentication-service.configSecrets" (dict "root" $root "context" .masContext) | fromJsonArray }}
{{- $synapseSecrets := include "element-io.synapse.configSecrets" (dict "root" $root "context" .synapseContext) | fromJsonArray }}
{{- $syn2masSecrets := concat $masSecrets $synapseSecrets | uniq | sortAlpha }}
{{- $syn2masSecrets | toJson -}}
{{- end -}}
{{- end -}}

{{- define "element-io.matrix-authentication-service.readyToHandleAuth" -}}
{{- $root := .root -}}
{{- /*
  If MAS is enabled, and the migration is disabled, it is ready to handle auth
  If MAS is enabled, and the migration is enabled, but not running in dryRun, once the migration is complete
        it will be ready to handle auth (after the pre-upgrade hooks)
*/}}
{{- if (and $root.Values.matrixAuthenticationService.enabled
  (or (not $root.Values.matrixAuthenticationService.syn2mas.enabled)
      (not $root.Values.matrixAuthenticationService.syn2mas.dryRun))) -}}
true
{{- end -}}
{{- end -}}



{{- define "element-io.syn2mas.configSecrets" -}}
{{- $root := .root -}}
{{- with required "element-io.syn2mas.configSecrets missing context" .context -}}
{{- $masSecrets := include "element-io.matrix-authentication-service.configSecrets" (dict "root" $root "context" .masContext) | fromJsonArray }}
{{- $synapseSecrets := include "element-io.synapse.configSecrets" (dict "root" $root "context" .synapseContext) | fromJsonArray }}
{{- $syn2masSecrets := concat $masSecrets $synapseSecrets | uniq | sortAlpha }}
{{- $syn2masSecrets | toJson -}}
{{- end -}}
{{- end -}}

{{- define "element-io.syn2mas.overrideEnv" -}}
{{- $root := .root -}}
{{- with required "element-io.syn2mas.overrideEnv missing context" .context -}}
env:
- name: "NAMESPACE"
  value: {{ $root.Release.Namespace | quote }}
{{- end -}}
{{- end -}}
