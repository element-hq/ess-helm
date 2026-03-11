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
  url: "http://{{ include "element-io.synapse.internal-hostport" (dict "root" $root "context" (dict "targetProcessType" "")) }}"
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
  redisUri: "redis://{{ $root.Release.Name }}-redis.{{ $root.Release.Namespace }}.svc.{{ $root.Values.clusterDomain }}:6379"

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
{{- if and $root.Values.synapse.enabled (not .ingress.host) }}
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
{{- if and $root.Values.synapse.enabled (not .ingress.host) }}
    prefix: "/_matrix/hookshot"
{{- end }}

generic:
{{ if .ingress.host }}
  urlPrefix: https://{{ (tpl .ingress.host $root) }}/webhook
{{ else if $root.Values.synapse.enabled }}
  urlPrefix: https://{{ (tpl $root.Values.synapse.ingress.host $root) }}/_matrix/hookshot/webhook
{{ end }}

widgets:
{{- if .ingress.host }}
  publicUrl: https://{{ tpl .ingress.host $root }}/widgetapi/v1/static
{{ else if $root.Values.synapse.enabled }}
  publicUrl: https://{{ tpl $root.Values.synapse.ingress.host $root }}/_matrix/hookshot/widgetapi/v1/static
{{ end }}

{{- end -}}
