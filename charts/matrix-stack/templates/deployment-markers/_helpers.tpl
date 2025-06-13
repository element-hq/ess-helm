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
   * We can run with Matrix Authentication Service enabled if we are running syn2mas.
   * We stay in legacy_auth mode after the dryRun mode has been completed.
   **/}}
{{- if and $root.Values.synapse.enabled
           (or (not $root.Values.matrixAuthenticationService.enabled)
              (and $root.Values.matrixAuthenticationService.enabled
                    $root.Values.matrixAuthenticationService.syn2mas.enabled
                    $root.Values.matrixAuthenticationService.syn2mas.dryRun)) }}
- {{ (printf "%s-markers" $root.Release.Name) }}:MATRIX_STACK_MSC3861:legacy_auth:legacy_auth
{{- end }}

{{- /* We allow migrating from legacy_auth to syn2mas_migrated, if we are running syn2mas in migrate mode.
  **/}}
{{- if and $root.Values.synapse.enabled
          $root.Values.matrixAuthenticationService.enabled
          $root.Values.matrixAuthenticationService.syn2mas.enabled
          (not $root.Values.matrixAuthenticationService.syn2mas.dryRun) }}
- {{ (printf "%s-markers" $root.Release.Name) }}:MATRIX_STACK_MSC3861:syn2mas_migrated:legacy_auth
{{- end }}

{{- /* We allow deploying of Synapse with Matrix Authentication Service, only
   * if it was initialized as delegated_auth, or if syn2mas was just ran and migration was completed.
   * This effectively prevents disabling Matrix Authentication Service
   * once it has been enabled.
  **/}}
{{- if and $root.Values.synapse.enabled
           $root.Values.matrixAuthenticationService.enabled
           (not $root.Values.matrixAuthenticationService.syn2mas.enabled) }}
- {{ (printf "%s-markers" $root.Release.Name) }}:MATRIX_STACK_MSC3861:delegated_auth:delegated_auth;syn2mas_migrated
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
