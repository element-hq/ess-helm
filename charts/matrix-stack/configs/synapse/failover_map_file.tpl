{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: LicenseRef-Element-Commercial
*/ -}}

{{- $root := .root -}}

# A map file that is used in haproxy config to map from matrix paths to the
# named backend. The format is: path_regexp backend_name

{{ $enabledWorkerTypes := keys ((include "element-io.synapse.enabledWorkers" (dict "root" $root)) | fromJson) }}
{{- range $workerType := $enabledWorkerTypes | sortAlpha }}
{{- $workersPaths := (include "element-io.synapse.process.workerPaths" (dict "root" $root "context" (dict "workerType" $workerType "enabledWorkerTypes" $enabledWorkerTypes))) | fromJsonArray }}
{{- if len $workersPaths }}
# {{ $workerType }}
{{- range $path := $workersPaths }}
{{- if include "element-io.synapse.process.canFallbackToMain" (dict "root" $root "context" $workerType) }}
{{ $path }} main-failover
{{- end }}
{{- end }}
{{- end }}
{{- end }}
