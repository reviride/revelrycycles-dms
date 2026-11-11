#!/usr/bin/env bash
# Nightly backup. Install with:  echo "30 2 * * * root /opt/erpnext/backup.sh" > /etc/cron.d/erpnext-backup
# Off-server copy is still TODO: choose a destination (e.g. Backblaze B2 or S3) and add an rclone line below.
set -euo pipefail
cd /opt/erpnext
docker compose exec -T backend bench --site all backup --with-files
docker compose exec -T backend bash -c 'find sites/*/private/backups -type f -mtime +14 -delete'
# rclone copy <volume path> b2:revelry-erpnext-backups   # TODO once a destination is chosen
