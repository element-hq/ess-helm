{{- /*
Copyright 2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root }}
{{- with required "hookshot/config-overrides.yaml.tpl missing context" .context }}
{{- $context := . -}}
bridge:
  domain: "{{ tpl $root.Values.serverName $root }}"
{{- if $root.Values.synapse.enabled }}
  url: "http://{{ include "element-io.synapse.internal-hostport" (dict "root" $root) }}"
{{- end }}
  port: 9993
  {{- /* We can only bind to 1 and so in the dual-stack case we bind :: and rely on the lack of IPV6_V6ONLY on the socket options */}}
  bindAddress: {{ ( has $root.Values.networking.ipFamily (list "ipv6" "dual-stack")) | ternary "::" "0.0.0.0" | quote }}

passFile: /secrets/{{
                include "element-io.ess-library.init-secret-path" (
                      dict "root" $root
                      "context" (dict
                        "secretPath" "hookshot.passkey"
                        "initSecretKey" "HOOKSHOT_RSA_PASSKEY"
                        "defaultSecretName" (include "element-io.hookshot.secret-name" (dict "root" $root "context" $context))
                        "defaultSecretKey" "RSA_PASSKEY"
                      )
                    ) }}

{{- if .enableEncryption }}
encryption:
 storagePath: /storage
{{- end }}

cache:
{{- if .redis }}
  redisUri: "redis{{ if .redis.tls }}s{{ end }}://{{ if .redis.password }}:${HOOKSHOT_REDIS_PASSWORD}@{{ end }}{{ tpl .redis.host $root }}:{{ .redis.port | default 6379 }}/{{ .redis.db | default 0 }}"
{{- else }}
  redisUri: "redis://{{ $root.Release.Name }}-redis.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}:6379"
{{- end }}

logging:
  level: {{ .logging.level }}

metrics:
  enabled: true

listeners:
  - port: 7775
    {{- /* We can only bind to 1 and so in the dual-stack case we bind :: and rely on the lack of IPV6_V6ONLY on the socket options */}}
    bindAddress: {{ ( has $root.Values.networking.ipFamily (list "ipv6" "dual-stack")) | ternary "::" "0.0.0.0" | quote }}
    resources:
      - webhooks
{{- if and $root.Values.synapse.enabled (not (include "element-io.ess-library.inboundTrafficHandler.host" (dict "root" $root "context" (dict "component" .)))) }}
    prefix: "/_matrix/hookshot"
{{- end }}
  - port: 7777
    {{- /* We can only bind to 1 and so in the dual-stack case we bind :: and rely on the lack of IPV6_V6ONLY on the socket options */}}
    bindAddress: {{ ( has $root.Values.networking.ipFamily (list "ipv6" "dual-stack")) | ternary "::" "0.0.0.0" | quote }}
    resources:
      - metrics
  - port: 7778
    {{- /* We can only bind to 1 and so in the dual-stack case we bind :: and rely on the lack of IPV6_V6ONLY on the socket options */}}
    bindAddress: {{ ( has $root.Values.networking.ipFamily (list "ipv6" "dual-stack")) | ternary "::" "0.0.0.0" | quote }}
    resources:
      - widgets
{{- if and $root.Values.synapse.enabled (not (include "element-io.ess-library.inboundTrafficHandler.host" (dict "root" $root "context" (dict "component" .)))) }}
    prefix: "/_matrix/hookshot"
{{- end }}

generic:
{{ if include "element-io.ess-library.inboundTrafficHandler.host" (dict "root" $root "context" (dict "component" .)) }}
  urlPrefix: https://{{ include "element-io.ess-library.inboundTrafficHandler.host" (dict "root" $root "context" (dict "component" .)) }}/webhook
{{ else if $root.Values.synapse.enabled }}
  urlPrefix: https://{{ include "element-io.ess-library.inboundTrafficHandler.host" (dict "root" $root "context" (dict "component" $root.Values.synapse)) }}/_matrix/hookshot/webhook
{{ end }}

widgets:
{{- if include "element-io.ess-library.inboundTrafficHandler.host" (dict "root" $root "context" (dict "component" .)) }}
  publicUrl: https://{{ include "element-io.ess-library.inboundTrafficHandler.host" (dict "root" $root "context" (dict "component" .)) }}/widgetapi/v1/static
{{ else if $root.Values.synapse.enabled }}
  publicUrl: https://{{ include "element-io.ess-library.inboundTrafficHandler.host" (dict "root" $root "context" (dict "component" $root.Values.synapse)) }}/_matrix/hookshot/widgetapi/v1/static
{{ end }}

{{- end -}}
