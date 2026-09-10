{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.valkey.configmap-data" -}}
{{- $root := .root -}}
{{- with required "element-io.valkey.configmap-data missing context" .context -}}
valkey.conf: |
{{- (tpl ($root.Files.Get "configs/valkey/valkey.conf.tpl") (dict "root" $root "context" .)) | nindent 2 -}}
{{- end -}}
{{- end -}}


{{- define "element-io.valkey.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.valkey.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-pubsub-small-cache
app.kubernetes.io/name: valkey
app.kubernetes.io/instance: {{ $root.Release.Name }}-valkey
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.valkey.overrideEnv" }}
env: []
{{- end -}}

{{- define "element-io.valkey-exporter.overrideEnv" }}
env: []
{{- end -}}

{{- define "element-io.valkey.internalValkeyEnabled" -}}
{{- $root := .root -}}
{{- $synapseNeedsRedis := and $root.Values.synapse.enabled (not $root.Values.synapse.redisOrValkey) (not $root.Values.synapse.redis) (include "element-io.synapse.enabledWorkers" (dict "root" $root) | fromJson) -}}
{{- $hookshotNeedsRedis := and $root.Values.hookshot.enabled (not $root.Values.hookshot.redisOrValkey) (not $root.Values.hookshot.redis) -}}
{{- $matrixRTCNeedsRedis := and $root.Values.matrixRTC.enabled (not $root.Values.matrixRTC.redisOrValkey) (not $root.Values.matrixRTC.sfu.redisOrValkey) (not $root.Values.matrixRTC.sfu.redis) -}}
{{- if or $synapseNeedsRedis $hookshotNeedsRedis $matrixRTCNeedsRedis -}}
true
{{- end }}
{{- end }}
