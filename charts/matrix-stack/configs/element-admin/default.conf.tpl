{{- /*
Copyright 2025 New Vector Ltd
Copyright 2025 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
{{- with required "configs/element-admin/default.conf.tpl missing context" .context -}}
# Built from https://github.com/element-hq/element-admin/blob/main/docker/nginx.conf
# * /health added for k8s
# * setting a charset
# * setting error_page
# * listening on IPv6
# * setting server_name
# * adding 'Cache-Control: no-cache' to root
# * ensuring security headers are applied even where there's location blocks
server {
{{- if has $root.Values.networking.ipFamily (list "ipv4" "dual-stack") }}
  listen       8080;
{{- end }}
{{- if has $root.Values.networking.ipFamily (list "ipv6" "dual-stack") }}
  listen  [::]:8080 ipv6only={{ (eq $root.Values.networking.ipFamily "dual-stack") | ternary "on" "off" }};
{{- end }}
  server_name  localhost;

  root   /dist;  # noqa
  index  index.html;
  charset utf-8;

  # Enable gzip compression
  gzip on;
  gzip_static on;

  # Cache static assets
  location /assets {
      expires 1y;
      add_header Cache-Control "public, max-age=31536000, immutable";
      include /etc/nginx/security_headers.conf;
  }

  include /etc/nginx/security_headers.conf;

  # Set no-cache for the index.html
  # so that browsers always check for a new copy of Element Admin.
  # NB http://your-domain/ and http://your-domain/? are also covered by this
  location / {
      add_header Cache-Control "no-cache";
      index /index.runtime.html /index.html;
      try_files $uri $uri/ /;
      include /etc/nginx/security_headers.conf;
  }

  location = /health {
      allow all;
      default_type 'application/json';
      return 200 '{"status": "ok"}';
  }
  # redirect server error pages to the static page /50x.html
  #
  error_page   500 502 503 504  /50x.html;
}
{{- end }}
