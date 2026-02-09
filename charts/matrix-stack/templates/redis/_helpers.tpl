{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- define "element-io.redis.configmap-data" -}}
{{- $root := .root -}}
{{- with required "element-io.redis.configmap-data missing context" .context -}}
redis.conf: |
{{- (tpl ($root.Files.Get "configs/redis/redis.conf.tpl") (dict "root" $root "context" .)) | nindent 2 -}}
{{- end -}}
{{- end -}}


{{- define "element-io.redis.labels" -}}
{{- $root := .root -}}
{{- with required "element-io.redis.labels missing context" .context -}}
{{ include "element-io.ess-library.labels.common" (dict "root" $root "context" (dict "labels" .labels "withChartVersion" .withChartVersion)) }}
app.kubernetes.io/component: matrix-pubsub-small-cache
app.kubernetes.io/name: redis
app.kubernetes.io/instance: {{ $root.Release.Name }}-redis
app.kubernetes.io/version: {{ include "element-io.ess-library.labels.makeSafe" .image.tag }}
{{- end }}
{{- end }}

{{- define "element-io.redis.overrideEnv" }}
env: []
{{- end -}}

{{- define "element-io.redis.internalRedisEnabled" -}}
{{- $root := .root -}}
{{- $synapseNeedsRedis := and $root.Values.synapse.enabled (not $root.Values.synapse.externalRedis) (include "element-io.synapse.enabledWorkers" (dict "root" $root) | fromJson) -}}
{{- $hookshotNeedsRedis := $root.Values.hookshot.enabled -}}
{{- if or $synapseNeedsRedis $hookshotNeedsRedis -}}
true
{{- end }}
{{- end }}
