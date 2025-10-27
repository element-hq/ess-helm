<!--
Copyright 2025 New Vector Ltd
Copyright 2025 Element Creations Ltd

SPDX-License-Identifier: AGPL-3.0-only
-->

# Migrating

## From Ansible Docker Deploy project

If you want to migrate from Ansible Docker Deploy project, follow the following steps :

1. Follow the [Preparing the environment](../README.md#preparing-the-environment) section of the documentation.
1. Install [yq](https://github.com/mikefarah/yq?tab=readme-ov-file#install).
1. Run this command: `./scripts/ansible-docker-deploy-to-values.sh /matrix ~/ess-config-values`.
This will create initial values file with all your configuration from ansible-docker-deploy.
2. A difference with the ansible-docker-deploy project is that Matrix Authentication Service is deployed under a dedicated hostname. If you are using Matrix Authentication Service, replace `CHANGEME` with the new DNS Name for MAS in the generated `hostnames.yaml`.
2. Install PostgreSQL on your server. Make sure that k3s can access it :
  1. In `postgresql.conf`, `listen_addresses` must be set to a routable IP of your server, different from localhost. Usually, you can use the same IP as the one discovered by Traefik in [the reverse proxy configuration](../README.md#using-an-existing-reverse-proxy).
  2. In `pg_hba.conf`, make sure that you allow synapse and Matrix Authentication Service :
  ```
  host    <synapse db>         <synapse_user>    10.42.0.1/24            md5
  host    <mas db>             <mas_user>       10.42.0.1/24            md5
  ```
  3. Make sure that the firewall denies connections from outside of the server, and allows connection from your 10.42.0.1/24 network.
3. Create a new database for Synapse and Matrix Authentication Service. Follow the [Using a dedicated PostgreSQL database](./advanced.md#using-a-dedicated-PostgreSQL-database) section of the advanced documentation.
4. Stop Synapse systemd unit: `sudo systemctl stop matrix-synapse.service`
5. Export `matrix-ansible-docker` PostgreSQL Synapse database into a local dump : `docker exec matrix-postgres pg_dump -C -h localhost -U matrix synapse > ./synapse.sql`
6. Adjust the user from the dump file to match your new database user and password: `sed -i 's/OWNER TO synapse/OWNER TO <your_synapse_user>/g' synapse.sql`
6. Import `matrix-ansible-docker` PostgreSQL Synapse database into your new Synapse database : `sudo -u postgres psql <synapse_db> < synapse.sql`
7. Follow the [Certificates](../README.md#certificates) section of the documentation
8. Follow the [Installation](../README.md#installation) section of the documentation
9. Import the media-store from your old Synapse to your new one :
   1. Import `local_content` : `sudo kubectl cp -n ess /matrix/synapse/storage/media-store/local_content ess-synapse-main-0:/media/media_store`
   1. Import `local_thumbnails` : `sudo kubectl cp -n ess /matrix/synapse/storage/media-store/local_thumbnails ess-synapse-main-0:/media/media_store`
   1. Import `remote_content` : `sudo kubectl cp -n ess /matrix/synapse/storage/media-store/remote_content ess-synapse-main-0:/media/media_store`
10. Follow [the verification steps](../README.md#verifying-the-setup) of the documentation to assert that your server is running properly.


The migration should now be completed.
