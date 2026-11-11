#!/usr/bin/env bash
# One-off: connect nightly backups to a Google Workspace Shared Drive, encrypted.
# Usage (as root):  bash setup-gdrive-backup.sh /root/gdrive-sa.json <SHARED_DRIVE_ID>
set -euo pipefail
SA_FILE=${1:?service account JSON path}
DRIVE_ID=${2:?shared drive ID}
[ -s "$SA_FILE" ] || { echo "Missing $SA_FILE"; exit 1; }
chmod 600 "$SA_FILE"

apt-get -o DPkg::Lock::Timeout=900 install -y -qq rclone >/dev/null

rclone config create gdrive drive scope=drive service_account_file="$SA_FILE" \
  team_drive="$DRIVE_ID" --non-interactive >/dev/null

PWFILE=/root/gdrive-backup-key.txt
if [ ! -s "$PWFILE" ]; then
  umask 077
  echo "password=$(openssl rand -hex 32)" >  "$PWFILE"
  echo "salt=$(openssl rand -hex 32)"     >> "$PWFILE"
fi
PW=$(grep '^password=' "$PWFILE" | cut -d= -f2)
SALT=$(grep '^salt=' "$PWFILE" | cut -d= -f2)
rclone config create gdrive-crypt crypt remote=gdrive:erpnext-backups \
  password="$(rclone obscure "$PW")" password2="$(rclone obscure "$SALT")" \
  --non-interactive --no-obscure >/dev/null

echo "Testing upload..."
echo "test $(date -Is)" | rclone rcat gdrive-crypt:_test.txt
rclone cat gdrive-crypt:_test.txt && rclone deletefile gdrive-crypt:_test.txt
echo
echo "OK. Running a backup now..."
/opt/erpnext/backup.sh
echo
echo "IMPORTANT: copy both lines of $PWFILE into your password manager."
echo "Without them the backups in Google Drive cannot be decrypted."
