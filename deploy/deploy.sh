#!/usr/bin/env bash
# Canonical copy of the server-side redeploy script.
#
# Production location: /opt/telefam-bot/deploy.sh on the Docker host
# (root:root, mode 0755). It is invoked by the Deploy workflow over SSH
# through a forced-command authorized_keys entry, so this script is the
# only thing the CI key can execute. Keep this copy in sync with prod.

set -euo pipefail

cd /opt/telefam-bot

docker compose pull
docker compose up -d --remove-orphans
docker image prune -f
