{{- /*
Copyright 2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
version: 1

formatters:
  precise:
    format: '%(asctime)s - %(name)s - %(lineno)d - %(levelname)s - %(request)s - %(message)s'

handlers:
  console:
    class: logging.StreamHandler
    formatter: precise

loggers:
{{- /*
Increasing synapse.storage.SQL past INFO will log access tokens. Putting in the values default will mean it gets
nuked if an override is set and then if the root level is increased to debug, the access tokens will be logged.
Putting here means it is an explicit customer choice to override it.
*/}}
{{- range $logger, $level := mustMergeOverwrite (dict "synapse.storage.SQL" "INFO") $root.Values.synapse.logging.levelOverrides }}
  {{ $logger }}:
    level: "{{ $level }}"
{{- end }}

root:
  level: "{{ $root.Values.synapse.logging.rootLevel }}"
  handlers:
  - console

disable_existing_loggers: false
