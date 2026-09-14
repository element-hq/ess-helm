{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.deployment-markers.configmap-labels" -}}
{{- $root := .root -}}
{{- with required "element-io.deployment-markers.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-tools
app.kubernetes.io/name: deployment-markers
app.kubernetes.io/instance: {{ $root.Release.Name }}-deployment-markers
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" $root.Values.matrixTools.image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.deployment-markers.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.deployment-markers.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-tools
app.kubernetes.io/name: deployment-markers-{{ .step }}
app.kubernetes.io/instance: {{ $root.Release.Name }}-deployment-markers-{{ .step }}
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" $root.Values.matrixTools.image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.deployment-markers-pre.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.deployment-markers-pre.labels missing context" .context -}}
{{ include "element-io.deployment-markers.labels" (dict "root" $root "context" (mustMergeOverwrite (dict "step" "pre") .)) }}
{{- end -}}
{{- end -}}

{{- define "element-io.deployment-markers-post.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.deployment-markers-pro.labels missing context" .context -}}
{{ include "element-io.deployment-markers.labels" (dict "root" $root "context" (mustMergeOverwrite (dict "step" "post") .)) }}
{{- end -}}
{{- end -}}

{{- define "element-io.deployment-markers.markers" -}}
{{- $root := .root -}}
{{- /* We can't set any sensible marker if Synapse isn't enabled:
     * If a MAS suddenly appears here we have no way of knowing whether it was previously deployed externally or not
    */ -}}
{{- if $root.Values.synapse.enabled }}
  {{- if $root.Values.matrixAuthenticationService.enabled }}
    {{- if $root.Values.matrixAuthenticationService.syn2mas.enabled }}
      {{- if $root.Values.matrixAuthenticationService.syn2mas.dryRun }}
        {{- /* We're only dry-run migrating so we're still stuck in legacy auth */ -}}
- {{ (printf "%s-markers" $root.Release.Name) }}:MATRIX_STACK_MSC3861:legacy_auth:legacy_auth
      {{- else }}
        {{- /* We're running the migration for real so allow to go legacy auth -> migrated as well as allowing to stay in this state after another deploy (the migration process will no-op) */ -}}
- {{ (printf "%s-markers" $root.Release.Name) }}:MATRIX_STACK_MSC3861:syn2mas_migrated:legacy_auth;syn2mas_migrated
      {{- end }}
    {{- else }}
      {{- /* We've started with MAS or migrated to MAS, so allow to come from migrated -> MAS as well as staying with MAS */ -}}
- {{ (printf "%s-markers" $root.Release.Name) }}:MATRIX_STACK_MSC3861:delegated_auth:delegated_auth;syn2mas_migrated
    {{- end }}
  {{- else }}
    {{- /* MAS not enabled at all, we're using legacy auth */ -}}
- {{ (printf "%s-markers" $root.Release.Name) }}:MATRIX_STACK_MSC3861:legacy_auth:legacy_auth
  {{- end }}
{{- end }}
{{- end }}

{{- define "element-io.deployment-markers.overrideEnv" }}
{{- $root := .root -}}
{{- with required "element-io.deployment-markers.overrideEnv missing context" .context -}}
env:
- name: "NAMESPACE"
  value: {{ $root.Release.Namespace | quote }}
{{- end -}}
{{- end -}}
