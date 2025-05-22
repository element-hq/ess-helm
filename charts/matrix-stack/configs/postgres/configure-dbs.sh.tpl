{{- /*
Copyright 2024-2025 New Vector Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
{{- with required "postgres/configure-dbs.sh.tpl missing context" .context -}}

#!/bin/sh
set -e;
export POSTGRES_PASSWORD=`cat /secrets/{{
    include "element-io.ess-library.init-secret-path" (
  dict "root" $root "context" (
    dict "secretPath" "postgres.adminPassword"
          "initSecretKey" "POSTGRES_ADMIN_PASSWORD"
          "defaultSecretName" (include "element-io.postgres.secret-name" (dict "root" $root "context"  (dict "isHook" false)))
          "defaultSecretKey" "ADMIN_PASSWORD"
    )
) }}`;
{{- range $key := (.essPasswords | keys | uniq | sortAlpha) -}}
{{- if (index $root.Values $key).enabled -}}
{{- $prop := index $root.Values.postgres.essPasswords $key }}
export ESS_PASSWORD=`cat /secrets/{{
include "element-io.ess-library.init-secret-path" (
dict "root" $root "context" (
  dict "secretPath" (printf "postgres.essPasswords.%s" $key)
        "initSecretKey" (include "element-io.ess-library.postgres-env-var" (dict "root" $root "context" $key))
        "defaultSecretName" (include "element-io.postgres.secret-name" (dict "root" $root "context"  (dict "isHook" false)))
        "defaultSecretKey" (printf "ESS_PASSWORD_%s" ($key | upper))
  )
) }}`;
(
  (echo -n $POSTGRES_PASSWORD | psql -W -U postgres -tc "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '{{ $key | lower }}_user'" | grep -q 1) && \
  (echo -n $POSTGRES_PASSWORD | psql -W -U postgres -c "ALTER USER {{ $key | lower }}_user PASSWORD '"$ESS_PASSWORD"'")
) || \
  (echo -n $POSTGRES_PASSWORD | psql -W -U postgres -c "CREATE ROLE {{ $key | lower }}_user LOGIN PASSWORD '"$ESS_PASSWORD"'");
(echo -n $POSTGRES_PASSWORD | psql -W -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = '{{ $key | lower }}'" | grep -q 1) || \
(echo -n $POSTGRES_PASSWORD | createdb --encoding=UTF8 --locale=C --template=template0 --owner={{ $key | lower }}_user {{ $key | lower }} -U postgres)
{{- end -}}
{{- end -}}
{{- end -}}
