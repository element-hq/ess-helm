{{- /*
Copyright 2024-2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}
{{- define "element-io.ess-library.labels.makeSafe" -}}
{{- if . -}}
{{- /* Trim edge punctuation before truncation to retain the full 63 valid characters, then trim again if truncation exposes punctuation at the end. */ -}}
{{ regexReplaceAll "[^A-Za-z0-9_.-]" . "_" | trimAll "-_." | trunc 63 | trimAll "-_." | quote }}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.labels.common" -}}
{{- $root := .root }}
{{- if not (hasKey . "context") -}}
{{- fail "element-io.ess-library.labels.common missing context" -}}
{{- end }}
{{- $userLabels := dict }}
{{- $userLabels = mustMergeOverwrite $userLabels ($root.Values.labels | deepCopy) }}
{{- $userLabels = mustMergeOverwrite $userLabels ((.context.labels | default dict) | deepCopy) }}
{{- /* These labels are owned by the chart, don't allow overriding */}}
{{- /* They must be skipped from pod templates to avoid restarting when unnecessary */}}
{{- $userLabels = unset $userLabels "helm.sh/chart.sh" }}
{{- $userLabels = unset $userLabels "app.kubernetes.io/managed-by" }}
{{- $userLabels = unset $userLabels "app.kubernetes.io/part-of" }}
{{- $userLabels = unset $userLabels "app.kubernetes.io/component" }}
{{- $userLabels = unset $userLabels "app.kubernetes.io/name" }}
{{- $userLabels = unset $userLabels "app.kubernetes.io/instance" }}
{{- $userLabels = unset $userLabels "app.kubernetes.io/version" }}
{{- if $userLabels }}
{{- toYaml $userLabels }}
{{- end }}
{{- if ne .context.withChartVersion false }}
helm.sh/chart: {{ include "element-io.ess-library.labels.makeSafe" (printf "%v-%v" $root.Chart.Name $root.Chart.Version) }}
{{- end }}
app.kubernetes.io/managed-by: {{ $root.Release.Service }}
app.kubernetes.io/part-of: matrix-stack
{{- end }}

{{- define "element-io.ess-library.postgres-label" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.postgres-label requires context" .context -}}
{{- $essPassword := required "element-io.ess-library.postgres-label context missing essPassword" .essPassword -}}
{{- $postgresProperty := .postgresProperty -}}
k8s.element.io/postgres-password-{{ ($essPassword | lower) | trunc 24 }}-hash: {{ if $postgresProperty -}}
    {{- if $postgresProperty.password.value -}}
    {{- $postgresProperty.password.value | sha1sum -}}
    {{- else -}}
    {{- (printf "%s-%s" (tpl $postgresProperty.password.secret $root) $postgresProperty.password.secretKey) | sha1sum -}}
    {{- end -}}
{{- else if (index $root.Values.postgres.essPasswords $essPassword) -}}
    {{- if (index $root.Values.postgres.essPasswords $essPassword).value -}}
    {{- (index $root.Values.postgres.essPasswords $essPassword).value | sha1sum -}}
    {{- else -}}
    {{- (printf "%s-%s" (tpl (index $root.Values.postgres.essPasswords $essPassword).secret $root) (index $root.Values.postgres.essPasswords $essPassword).secretKey) | sha1sum -}}
    {{- end -}}
{{- else -}}
  {{- if $root.Values.initSecrets.enabled -}}
  {{- (printf "%s-generated" $root.Release.Name) | sha1sum -}}
  {{- else -}}
  {{- fail "No postgres password set and initSecrets not set" -}}
  {{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "element-io.ess-library.appservice-hash-label" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.appservice-hash-label requires context" .context -}}
    {{- $componentValues := required "element-io.ess-library.appservice-hash-label context missing componentValues" .componentValues -}}
    {{- $templatePath := required "element-io.ess-library.appservice-hash-label context missing templatePath" .templatePath -}}
    {{- $label := "" -}}
    {{- $value := "" -}}
    {{- if eq (required "element-io.ess-library.appservice-hash-label context missing destination" .destination) "synapse" -}}
        {{- $label = printf "k8s.element.io/as-registration-%s-hash" (required "element-io.ess-library.appservice-hash-label context missing componentName" .componentName) -}}
    {{- else -}}
        {{- $label = "k8s.element.io/as-registration-self-hash" -}}
    {{- end -}}
    {{- with $componentValues -}}
        {{- if .enabled -}}
            {{- with .appserviceRegistration -}}
                {{- with .value -}}
                    {{- $value = tpl . $root -}}
                {{- else -}}
                    {{- /* This is best effort as lookup might not work (return nothing) or will return more than just the key in question */ -}}
                    {{- $value = (lookup "v1" "Secret" $root.Release.Namespace (tpl .secret $root)) | toJson -}}
                {{- end -}}
            {{- else -}}
                {{- $value = tpl ($root.Files.Get $templatePath) (dict "root" $root) -}}
            {{- end -}}
            {{- $label }}: {{ $value | sha1sum -}}
        {{- end -}}
    {{- end -}}
{{- end -}}
{{- end -}}
