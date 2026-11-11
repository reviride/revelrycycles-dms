#!/usr/bin/env bash
# All-in-one ERPNext pilot install for dms.revelrycycles.com.au (Ubuntu 24.04, run as root).
# Paste this whole file into an SSH session as root, or save it and run: bash install-pilot.sh
set -euo pipefail
DOMAIN="${DOMAIN:-dms.revelrycycles.com.au}"
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a
mkdir -p /opt/erpnext && cd /opt/erpnext
set -euo pipefail

# 1. Updates and automatic security patches
apt-get update && apt-get -y upgrade
apt-get -y install unattended-upgrades ufw curl git
dpkg-reconfigure -f noninteractive unattended-upgrades

# 2. 4 GB swap: ERPNext needs headroom above 4 GB RAM during updates
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
sysctl -w vm.swappiness=10 && echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf

# 3. Firewall: SSH and web only
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable

# 4. Docker (official install script)
if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | sh; fi

echo "Server ready. Next: copy compose.yml, Caddyfile and .env here, then: docker compose up -d"

cd /opt/erpnext

cat > compose.yml <<'__EOF__'
# ERPNext v15 pilot, adapted from frappe_docker's pwd.yml and tuned for a 4 GB server.
# Changes from upstream: pinned v15 image, MariaDB 10.6 with a 512 MB buffer pool,
# one combined worker, passwords from .env, and Caddy in front for automatic HTTPS.
x-erpnext: &erpnext
  image: ${ERPNEXT_IMAGE}
  restart: unless-stopped
  volumes:
    - sites:/home/frappe/frappe-bench/sites
    - logs:/home/frappe/frappe-bench/logs

services:
  configurator:
    <<: *erpnext
    restart: "no"
    entrypoint: ["bash", "-c"]
    command:
      - >
        ls -1 apps > sites/apps.txt;
        bench set-config -g db_host db;
        bench set-config -gp db_port 3306;
        bench set-config -g redis_cache "redis://redis-cache:6379";
        bench set-config -g redis_queue "redis://redis-queue:6379";
        bench set-config -g redis_socketio "redis://redis-queue:6379";
        bench set-config -gp socketio_port 9000;
    depends_on:
      db:
        condition: service_healthy
      redis-cache:
        condition: service_started
      redis-queue:
        condition: service_started

  create-site:
    <<: *erpnext
    restart: "no"
    entrypoint: ["bash", "-c"]
    command:
      - >
        wait-for-it -t 120 db:3306;
        wait-for-it -t 120 redis-cache:6379;
        wait-for-it -t 120 redis-queue:6379;
        until [ -f sites/common_site_config.json ]; do sleep 5; done;
        if [ ! -d "sites/${DOMAIN}" ]; then
          bench new-site "${DOMAIN}" --mariadb-user-host-login-scope='%' --admin-password="${ADMIN_PASSWORD}" --db-root-username=root --db-root-password="${DB_ROOT_PASSWORD}" --install-app erpnext --set-default;
        fi
    depends_on:
      configurator:
        condition: service_completed_successfully

  backend:
    <<: *erpnext
    depends_on:
      configurator:
        condition: service_completed_successfully

  frontend:
    <<: *erpnext
    command: ["nginx-entrypoint.sh"]
    environment:
      BACKEND: backend:8000
      SOCKETIO: websocket:9000
      FRAPPE_SITE_NAME_HEADER: ${DOMAIN}
      UPSTREAM_REAL_IP_ADDRESS: 0.0.0.0/0
      UPSTREAM_REAL_IP_HEADER: X-Forwarded-For
      PROXY_READ_TIMEOUT: 120
      CLIENT_MAX_BODY_SIZE: 50m
    depends_on: [backend, websocket]

  websocket:
    <<: *erpnext
    command: ["node", "/home/frappe/frappe-bench/apps/frappe/socketio.js"]
    depends_on:
      configurator:
        condition: service_completed_successfully

  # One worker for all queues instead of upstream's two, to save about 300 MB RAM.
  worker:
    <<: *erpnext
    command: ["bench", "worker", "--queue", "long,default,short"]
    depends_on:
      configurator:
        condition: service_completed_successfully

  scheduler:
    <<: *erpnext
    command: ["bench", "schedule"]
    depends_on:
      configurator:
        condition: service_completed_successfully

  db:
    image: mariadb:10.6
    restart: unless-stopped
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --skip-character-set-client-handshake
      - --skip-innodb-read-only-compressed
      - --innodb-buffer-pool-size=512M
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
      MARIADB_ROOT_PASSWORD: ${DB_ROOT_PASSWORD}
    healthcheck:
      test: ["CMD", "healthcheck.sh", "--connect", "--innodb_initialized"]
      interval: 5s
      retries: 20
    volumes:
      - db-data:/var/lib/mysql

  redis-cache:
    image: redis:6.2-alpine
    restart: unless-stopped
    command: ["redis-server", "--maxmemory", "128mb", "--maxmemory-policy", "allkeys-lru"]

  redis-queue:
    image: redis:6.2-alpine
    restart: unless-stopped
    volumes:
      - redis-queue-data:/data

  caddy:
    image: caddy:2
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    environment:
      DOMAIN: ${DOMAIN}
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
    depends_on: [frontend]

volumes:
  db-data:
  redis-queue-data:
  sites:
  logs:
  caddy-data:
__EOF__

cat > Caddyfile <<'__EOF__'
{$DOMAIN} {
	encode gzip
	reverse_proxy frontend:8080
}
__EOF__

cat > backup.sh <<'__EOF__'
#!/usr/bin/env bash
# Nightly backup. Install with:  echo "30 2 * * * root /opt/erpnext/backup.sh" > /etc/cron.d/erpnext-backup
# Off-server copy is still TODO: choose a destination (e.g. Backblaze B2 or S3) and add an rclone line below.
set -euo pipefail
cd /opt/erpnext
docker compose exec -T backend bench --site all backup --with-files
docker compose exec -T backend bash -c 'find sites/*/private/backups -type f -mtime +14 -delete'
# rclone copy <volume path> b2:revelry-erpnext-backups   # TODO once a destination is chosen
__EOF__
chmod +x backup.sh
if [ ! -f .env ]; then
  umask 077
  cat > .env <<__EOF__
DOMAIN=${DOMAIN}
DB_ROOT_PASSWORD=$(openssl rand -hex 24)
ADMIN_PASSWORD=$(openssl rand -base64 18 | tr -d '/+=')
ERPNEXT_IMAGE=frappe/erpnext:v15.124.5
__EOF__
fi
echo "30 2 * * * root /opt/erpnext/backup.sh >> /var/log/erpnext-backup.log 2>&1" > /etc/cron.d/erpnext-backup
docker compose pull -q
docker compose up -d
echo "Waiting for the site to install (5 to 10 minutes)..."
until [ "$(docker compose ps -a create-site --format '{{.State}}')" = "exited" ]; do sleep 15; done
docker compose ps -a create-site --format 'create-site exit code: {{.ExitCode}}'
docker compose restart backend worker scheduler websocket frontend
echo
echo "Done. Open https://${DOMAIN} once DNS points here."
echo "Administrator password is in /opt/erpnext/.env (ADMIN_PASSWORD). Do not paste it into chat."
free -h | head -2
