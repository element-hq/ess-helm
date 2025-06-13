{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.postgres.labels" -}}
{{- $root := .root -}}

{{- with required "element-io.postgres.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-stack-db
app.kubernetes.io/name: postgres
app.kubernetes.io/instance: {{ $root.Release.Name }}-postgres
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.postgres.enabled" }}
{{- $root := .root -}}
{{- if and $root.Values.postgres.enabled (or
 (and $root.Values.matrixAuthenticationService.enabled
      (not $root.Values.matrixAuthenticationService.postgres))
  (and $root.Values.synapse.enabled
      (not $root.Values.synapse.postgres))
) -}}
true
{{- end }}
{{- end }}

{{- define "element-io.postgres.anyEssPasswordHasValue" }}
{{- $root := .root -}}
{{- with required "element-io.postgres.anyEssPasswordHasValue missing context" .context -}}
{{- range .essPasswords -}}
{{- if .value -}}
true
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}


{{- define "element-io.postgres.configSecrets" -}}
{{- $root := .root -}}
{{- with required "element-io.postgres.configSecrets missing context" .context -}}
{{- $configSecrets := list }}
{{- if or .adminPassword.value (include "element-io.postgres.anyEssPasswordHasValue" (dict "root" $root "context" .)) }}
{{- $configSecrets = append $configSecrets  (printf "%s-postgres" $root.Release.Name) }}
{{- end }}
{{- with .adminPassword.secret -}}
{{ $configSecrets = append $configSecrets (tpl . $root) }}
{{- end -}}
{{- range $key := (.essPasswords | keys | uniq | sortAlpha) -}}
{{- $prop := index $root.Values.postgres.essPasswords $key }}
{{- with $prop.secret -}}
{{ $configSecrets = append $configSecrets (tpl . $root) }}
{{- end }}
{{- end }}
{{ $configSecrets | uniq | toJson }}
{{- end }}
{{- end }}


{{- define "element-io.postgres.memoryLimitsMB" -}}
{{- $root := .root -}}
{{- with required "element-io.postgres.memoryLimitsMB missing context" .context -}}
  {{- $value := .resources.limits.memory }}
  {{- if  $value | hasSuffix "Mi" }}
    {{- printf "%d" (trimSuffix "Mi" $value) | int64 -}}
  {{- else if  $value | hasSuffix "Gi" }}
    {{- printf "%d" (mul (int64 (trimSuffix "Gi" $value)) 1024) | int64 -}}
  {{- else if  $value | hasSuffix "Ti" }}
    {{- printf "%d" (mul (mul (int64 (trimSuffix "Ti" $value)) 1024) 1024) | int64 -}}
  {{- else -}}
    {{- fail (printf "Could not compute Postgres memory limits from %s" $value) -}}
  {{- end -}}
{{- end -}}
{{- end -}}


{{- define "element-io.postgres.args" -}}
{{- $root := .root -}}
{{- with required "element-io.postgres.args missing context" .context -}}
{{- $memoryLimitsMB := include "element-io.postgres.memoryLimitsMB" (dict "root" $root "context" .) }}
- "-c"
- "max_connections={{ printf "%d" (div $memoryLimitsMB 16) }}"
- "-c"
- "shared_buffers={{ printf "%s" (printf "%dMB" (div $memoryLimitsMB 4)) }}"
- "-c"
- "effective_cache_size={{ printf "%s" (printf "%dMB" (sub $memoryLimitsMB 256)) }}"
{{- end -}}
{{- end -}}

{{- define "element-io.postgres.overrideEnv" }}
{{- $root := .root -}}
{{- with required "element-io.postgres.overrideEnv missing context" .context -}}
env:
- name: "POSTGRES_PASSWORD_FILE"
  value: {{ printf "/secrets/%s" (
              include "element-io.ess-library.init-secret-path" (dict
                "root" $root
                "context" (dict
                  "secretPath" "postgres.adminPassword"
                  "initSecretKey" "POSTGRES_ADMIN_PASSWORD"
                  "defaultSecretName" (include "element-io.postgres.secret-name" (dict "root" $root "context"  (dict "isHook" false)))
                  "defaultSecretKey" "ADMIN_PASSWORD"
                  )
                )
              ) }}
- name: "PGDATA"
  value: "/var/lib/postgres/data/pgdata"
- name: "POSTGRES_INITDB_ARGS"
  value: "-E UTF8"
- name: "LC_COLLATE"
  value: "C"
- name: "LC_CTYPE"
  value: "C"
{{- end -}}
{{- end -}}

{{- define "element-io.postgres-exporter.overrideEnv" }}
{{- $root := .root -}}
{{- with required "element-io.postgres-exporter.overrideEnv missing context" .context -}}
env:
- name: "DATA_SOURCE_URI"
  value: "localhost?sslmode=disable"
- name: "DATA_SOURCE_USER"
  value: "postgres"
{{- end -}}
{{- end -}}


{{- define "element-io.postgres.configmap-data" -}}
{{- $root := .root -}}
{{- with required "element-io.postgres.configmap-data" .context -}}
configure-dbs.sh: |
{{- (tpl ($root.Files.Get "configs/postgres/configure-dbs.sh.tpl") (dict "root" $root "context" .)) | nindent 2 }}
{{- end }}
{{- end }}
