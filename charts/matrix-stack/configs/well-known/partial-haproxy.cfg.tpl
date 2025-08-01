{{- /*
Copyright 2024-2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
{{- with required "well-known/partial-haproxy.cfg.tpl missing context" .context -}}

frontend well-known-in
  bind *:8010

  # same as http log, with %Th (handshake time)
  log-format "%ci:%cp [%tr] %ft %b/%s %Th/%TR/%Tw/%Tc/%Tr/%Ta %ST %B %CC %CS %tsc %ac/%fc/%bc/%sc/%rc %sq/%bq %hr %hs %{+Q}r"

  acl is_delete_put_post_method method DELETE POST PUT
  http-request deny status 405 if is_delete_put_post_method

  acl well-known path /.well-known/matrix/server
  acl well-known path /.well-known/matrix/client
  acl well-known path /.well-known/matrix/support

{{ if .baseDomainRedirect.enabled }}
{{- if $root.Values.elementWeb.enabled }}
{{- with $root.Values.elementWeb }}
{{- $elementWebHttps := include "element-io.ess-library.ingress.tlsHostsSecret" (dict "root" $root "context" (dict "hosts" (list .ingress.host) "tlsSecret" .ingress.tlsSecret "ingressName" "element-web")) }}
  http-request redirect  code 301  location http{{ if $elementWebHttps }}s{{ end }}://{{ tpl .ingress.host $root }} unless well-known
{{- end }}
{{- else if .baseDomainRedirect.url }}
  http-request redirect  code 301  location {{ .baseDomainRedirect.url }} unless well-known
{{- end }}
{{- end }}

  use_backend well-known-static if well-known
  default_backend well-known-no-match

backend well-known-static
  mode http

  http-after-response set-header X-Frame-Options SAMEORIGIN
  http-after-response set-header X-Content-Type-Options nosniff
  http-after-response set-header X-XSS-Protection "1; mode=block"
  http-after-response set-header Content-Security-Policy "frame-ancestors 'self'"
  http-after-response set-header X-Robots-Tag "noindex, nofollow, noarchive, noimageindex"

  http-after-response set-header Access-Control-Allow-Origin *
  http-after-response set-header Access-Control-Allow-Methods "GET, POST, PUT, DELETE, OPTIONS"
  http-after-response set-header Access-Control-Allow-Headers "X-Requested-With, Content-Type, Authorization"

  http-request return status 200 content-type "application/json" file "/well-known/server" if { path /.well-known/matrix/server }
  http-request return status 200 content-type "application/json" file "/well-known/client" if { path /.well-known/matrix/client }
  http-request return status 200 content-type "application/json" file "/well-known/support" if { path /.well-known/matrix/support }

backend well-known-no-match
  mode http

  http-request deny status 404

{{- end -}}
