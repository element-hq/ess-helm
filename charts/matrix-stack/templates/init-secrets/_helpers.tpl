{{- /*
Copyright 2024-2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.init-secrets.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.init-secrets.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-tools
app.kubernetes.io/name: init-secrets
app.kubernetes.io/instance: {{ $root.Release.Name }}-init-secrets
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" $root.Values.matrixTools.image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.init-secrets.postgres-generated-secrets" -}}
{{- $root := .root -}}
{{- with $root.Values.postgres }}
{{- if (include "element-io.postgres.enabled" (dict "root" $root)) -}}
{{- if and $root.Values.synapse.enabled
          (not $root.Values.synapse.postgres)
          (not $root.Values.postgres.essPasswords.synapse) }}
- {{ (printf "%s-generated" $root.Release.Name) }}:POSTGRES_SYNAPSE_PASSWORD:rand32
{{- end }}
{{- if and $root.Values.matrixAuthenticationService.enabled
          (not $root.Values.matrixAuthenticationService.postgres)
          (not $root.Values.postgres.essPasswords.matrixAuthenticationService) }}
- {{ (printf "%s-generated" $root.Release.Name) }}:POSTGRES_MATRIX_AUTHENTICATION_SERVICE_PASSWORD:rand32
{{- end }}
{{- if not .adminPassword }}
- {{ (printf "%s-generated" $root.Release.Name) }}:POSTGRES_ADMIN_PASSWORD:rand32
{{- end }}
{{- end }}
{{- end }}
{{- end }}


{{- define "element-io.init-secrets.generated-secrets" -}}
{{- $root := .root -}}
{{- include "element-io.init-secrets.postgres-generated-secrets" (dict "root" $root) -}}
{{- with $root.Values.matrixRTC }}
{{- if .enabled -}}
{{- if and (not (.livekitAuth).keysYaml) (not (.livekitAuth).secret) }}
- {{ (printf "%s-generated" $root.Release.Name) }}:ELEMENT_CALL_LIVEKIT_SECRET:rand32
{{- end }}
{{- end }}
{{- end }}
{{- with $root.Values.synapse }}
{{- if .enabled -}}
{{- if not .macaroon }}
- {{ (printf "%s-generated" $root.Release.Name) }}:SYNAPSE_MACAROON:rand32
{{- end }}
{{- if not .registrationSharedSecret }}
- {{ (printf "%s-generated" $root.Release.Name) }}:SYNAPSE_REGISTRATION_SHARED_SECRET:rand32
{{- end }}
{{- if not .signingKey }}
- {{ (printf "%s-generated" $root.Release.Name) }}:SYNAPSE_SIGNING_KEY:signingkey
{{- end }}
{{- end }}
{{- end }}
{{- with $root.Values.matrixAuthenticationService }}
{{- if .enabled }}
{{- if $root.Values.synapse.enabled }}
{{- if not .synapseSharedSecret }}
- {{ (printf "%s-generated" $root.Release.Name) }}:MAS_SYNAPSE_SHARED_SECRET:rand32
{{- end -}}
{{- end -}}
{{- if not .encryptionSecret }}
- {{ (printf "%s-generated" $root.Release.Name) }}:MAS_ENCRYPTION_SECRET:hex32
{{- end -}}
{{- with .privateKeys }}
{{- if not .rsa }}
- {{ (printf "%s-generated" $root.Release.Name) }}:MAS_RSA_PRIVATE_KEY:rsa
{{- end }}
{{- if not .ecdsaPrime256v1 }}
- {{ (printf "%s-generated" $root.Release.Name) }}:MAS_ECDSA_PRIME256V1_PRIVATE_KEY:ecdsaprime256v1
{{- end }}
{{- end }}
{{- end }}
{{- end }}
{{- end }}

{{- define "element-io.init-secrets.overrideEnv" }}
{{- $root := .root -}}
{{- with required "element-io.init-secrets.overrideEnv missing context" .context -}}
env:
- name: "NAMESPACE"
  value: {{ $root.Release.Namespace | quote }}
{{- end -}}
{{- end -}}
