{{- /*
Copyright 2025 New Vector Ltd

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
{{- /* We allow deploying of Synapse without Matrix Authentication Service, only
   * if it was initialized as legacy_auth. This effectively prevents enabling Matrix Authentication Service
   * until Synapse 2 Matrix Authentication Service has been run.
   **/}}
{{- if and $root.Values.synapse.enabled
          (not $root.Values.matrixAuthenticationService.enabled) }}
- {{ (printf "%s-markers" $root.Release.Name) }}:MATRIX_STACK_MSC3861:legacy_auth:legacy_auth
{{- end }}
{{- /* We allow deploying of Synapse with Matrix Authentication Service, only
   * if it was initialized as delegated_auth. This effectively prevents disabling Matrix Authentication Service
   * once it has been enabled.
  **/}}
{{- if and $root.Values.synapse.enabled
          ($root.Values.matrixAuthenticationService.enabled) }}
- {{ (printf "%s-markers" $root.Release.Name) }}:MATRIX_STACK_MSC3861:delegated_auth:delegated_auth
{{- end }}
{{- end }}

{{- define "element-io.deployment-markers.env" }}
{{- $root := .root -}}
{{- with required "element-io.deployment-markers.env missing context" .context -}}
{{- $resultEnv := dict -}}
{{- range $envEntry := .extraEnv -}}
{{- $_ := set $resultEnv $envEntry.name $envEntry.value -}}
{{- end -}}
{{- $overrideEnv := dict "NAMESPACE" $root.Release.Namespace
-}}
{{- $resultEnv := mustMergeOverwrite $resultEnv $overrideEnv -}}
{{- range $key, $value := $resultEnv }}
- name: {{ $key | quote }}
  value: {{ $value | quote }}
{{- end -}}
{{- end -}}
{{- end -}}
