{{- /*
Copyright 2024-2025 New Vector Ltd
Copyright 2025-2026 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
*/ -}}

{{- $root := .root -}}
{{- with required "postgres/configure-dbs.sh.tpl missing context" .context -}}

#!/bin/sh
set -e;
# Function to create or ensure a user and database
create_or_ensure_db() {
  user="$1"
  db="$2"
  password="$3"
  admin_password="$4"

  # Check if user exists, if so update password; otherwise create user
  if echo -n "$admin_password" | psql -W -U postgres -tc "SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '$user'" | grep -q 1; then
    echo -n "$admin_password" | psql -W -U postgres -c "ALTER USER $user PASSWORD '$password'"
  else
    echo -n "$admin_password" | psql -W -U postgres -c "CREATE ROLE $user LOGIN PASSWORD '$password'"
  fi

  # Check if database exists, if not create it
  if ! echo -n "$admin_password" | psql -W -U postgres -tc "SELECT 1 FROM pg_database WHERE datname = '$db'" | grep -q 1; then
    echo -n "$admin_password" | createdb --encoding=UTF8 --locale=C --template=template0 --owner=$user $db -U postgres
  fi
}

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
create_or_ensure_db "{{ $key | lower }}_user" "{{ $key | lower }}" "$ESS_PASSWORD" "$POSTGRES_PASSWORD"
{{- end -}}
{{- end -}}
{{- end -}}
