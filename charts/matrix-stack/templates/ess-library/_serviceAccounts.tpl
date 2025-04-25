{{- /*
Copyright 2024 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.ess-library.serviceAccountName" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.serviceAccountName missing context" .context -}}
{{ default (printf "%s-%s" $root.Release.Name (required "element-io.ess-library.serviceAccountName missing context.nameSuffix" .nameSuffix)) .serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "element-io.ess-library.serviceAccount" -}}
{{- $root := .root -}}
{{- with required "element-io.ess-library.serviceAccount missing context" .context -}}
{{- $nameSuffix := required "element-io.ess-library.serviceAccount missing context.nameSuffix" .nameSuffix -}}
{{- $extraAnnotations := .extraAnnotations | default dict -}}
{{- with required "element-io.ess-library.serviceAccount missing context.componentValues" .componentValues -}}
{{- if .serviceAccount.create }}
apiVersion: v1
kind: ServiceAccount
metadata:
  {{- with (mustMergeOverwrite $extraAnnotations .serviceAccount.annotations) }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  labels:
    {{- include (printf "element-io.%s.labels" $nameSuffix) (dict "root" $root "context" .) | nindent 4 }}
  name: {{ include "element-io.ess-library.serviceAccountName" (dict "root" $root "context" (dict "serviceAccount" .serviceAccount "nameSuffix" $nameSuffix)) }}
  namespace: {{ $root.Release.Namespace }}
automountServiceAccountToken: false
{{- end }}
{{- end }}
{{- end }}
{{- end }}
