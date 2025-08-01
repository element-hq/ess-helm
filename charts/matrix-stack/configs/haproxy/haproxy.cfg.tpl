{{- /*
Copyright 2024-2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
{{- with required "haproxy/haproxy.cfg.tpl missing context" .context -}}

global
  maxconn 40000
  log stdout format raw local0 info

  # Allow for rewriting HTTP headers (e.g. Authorization) up to 4k
  # https://github.com/haproxy/haproxy/issues/1743
  tune.maxrewrite 4096

  # Allow HAProxy Stats sockets
  stats socket ipv4@127.0.0.1:1999 level admin

defaults
  mode http
  fullconn 20000

  maxconn 20000

  log global

  # wait for 5s when connecting to a server
  timeout connect 5s

  # ... but if there is a backlog of requests, wait for 60s before returning a 500
  timeout queue 60s

  # close client connections 5m after the last request
  # (as recommened by https://support.cloudflare.com/hc/en-us/articles/212794707-General-Best-Practices-for-Load-Balancing-with-CloudFlare)
  timeout client 900s

  # give clients 5m between requests (otherwise it defaults to the value of 'timeout http-request')
  timeout http-keep-alive 900s

  # give clients 10s to complete a request (either time between handshake and first request, or time spent sending headers)
  timeout http-request 10s

  # time out server responses after 90s
  timeout server 180s

  # allow backend sessions to be shared across frontend sessions
  http-reuse aggressive

  # limit the number of concurrent requests to each server, to stop
  # the python process having to juggle hundreds of queued
  # requests. Any requests beyond this limit are held in a queue for
  # up to <timeout-queue> seconds, before being rejected according
  # to "errorfile 503" below.
  #
  # (bear in mind that we have two haproxies, each of which will use
  # up to this number of connections, so the actual number of
  # connections to the server may be up to twice this figure.)
  #
  # Note that this is overridden for some servers and backends.
  default-server maxconn 500

  option redispatch

  compression algo gzip
  compression type text/plain text/html text/xml application/json text/css

  # Use a consistent hashing scheme so that worker with balancing going down doesn't cause
  # the traffic for all others to be shuffled around.
  hash-type consistent sdbm

resolvers kubedns
  parse-resolv-conf
  accepted_payload_size 8192
  hold timeout 600s
  hold refused 600s

frontend prometheus
  bind *:8405
  http-request use-service prometheus-exporter if { path /metrics }
  monitor-uri /haproxy_test
  no log

frontend http-blackhole
  bind *:8009

  # same as http log, with %Th (handshake time)
  log-format "%ci:%cp [%tr] %ft %b/%s %Th/%TR/%Tw/%Tc/%Tr/%Ta %ST %B %CC %CS %tsc %ac/%fc/%bc/%sc/%rc %sq/%bq %hr %hs %{+Q}r"

  capture request header Host len 32
  capture request header Referer len 200
  capture request header User-Agent len 200

  http-request deny content-type application/json string '{"errcode": "M_FORBIDDEN", "error": "Blocked"}'

{{ if $root.Values.synapse.enabled }}
{{ tpl ($root.Files.Get "configs/synapse/partial-haproxy.cfg.tpl") (dict "root" $root "context" $root.Values.synapse) }}
{{ end }}

{{ if $root.Values.wellKnownDelegation.enabled }}
{{ tpl ($root.Files.Get "configs/well-known/partial-haproxy.cfg.tpl") (dict "root" $root "context" $root.Values.wellKnownDelegation) }}
{{ end }}

{{- end -}}

# a fake backend which fonxes every request with a 500. Useful for
# handling overloads etc.
backend return_500
  http-request deny deny_status 500
