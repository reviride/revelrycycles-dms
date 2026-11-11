#!/usr/bin/env bash
# Nightly backup, run by /etc/cron.d/erpnext-backup.
# Keeps 14 days on the server. If the encrypted Google Drive remote exists
# (see setup-gdrive-backup.sh), copies backups there and keeps 90 days.
set -euo pipefail
cd /opt/erpnext
docker compose exec -T backend bench --site all backup --with-files
docker compose exec -T backend bash -c 'find sites/*/private/backups -type f -mtime +14 -delete'

if command -v rclone >/dev/null && rclone listremotes 2>/dev/null | grep -q '^gdrive-crypt:$'; then
  SITES=$(docker volume inspect -f '{{.Mountpoint}}' "$(docker compose ps -q backend | xargs docker inspect -f '{{range .Mounts}}{{if eq .Destination "/home/frappe/frappe-bench/sites"}}{{.Name}}{{end}}{{end}}')")
  for dir in "$SITES"/*/private/backups; do
    site=$(basename "$(dirname "$(dirname "$dir")")")
    rclone copy "$dir" "gdrive-crypt:$site" --max-age 2d
  done
  rclone delete gdrive-crypt: --min-age 90d
  echo "$(date -Is) off-server copy done"
else
  echo "$(date -Is) WARNING: no gdrive-crypt remote, backups are on this server only"
fi
