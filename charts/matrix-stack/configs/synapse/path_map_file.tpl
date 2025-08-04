{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}

# A map file that is used in haproxy config to map from matrix paths to the
# named backend. The format is: path_regexp backend_name

{{ $enabledWorkerTypes := keys ((include "element-io.synapse.enabledWorkers" (dict "root" $root)) | fromJson) }}
{{- range $workerType := $enabledWorkerTypes | sortAlpha }}
{{- $workersPaths := (include "element-io.synapse.process.workerPaths" (dict "root" $root "context" $workerType)) | fromJsonArray }}
{{- if len $workersPaths }}
# {{ $workerType }}
{{- range $path := $workersPaths }}
{{ $path }} {{ $workerType }}
{{- end }}
{{- end }}
{{- end }}
