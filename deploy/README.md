# ERPNext pilot server (KVM 4, Ubuntu 24.04)

Tested 10 Nov 2026 in a local Docker run: ERPNext 15.124.5 / Frappe 15.126.0 installed, login works,
and the whole stack idled at about 540 MB RAM on an empty site.

## Steps (as root on the new VPS)
1. Point a DNS A record (e.g. `dms.revelrycycles.com.au`) at the VPS IP.
2. `mkdir -p /opt/erpnext && cd /opt/erpnext`, copy these files in.
3. `bash setup-server.sh` (updates, 4 GB swap, firewall, Docker).
4. `cp env.example .env` and set DOMAIN and two long random passwords.
5. `docker compose up -d`. The first start takes 5 to 10 minutes while the site installs.
   Watch it with `docker compose logs -f create-site`.
6. Open https://DOMAIN and log in as Administrator with ADMIN_PASSWORD.
7. Install the nightly backup: `echo "30 2 * * * root /opt/erpnext/backup.sh" > /etc/cron.d/erpnext-backup`.

## Files
- `setup-server.sh`: one-time server preparation.
- `compose.yml`: the ERPNext stack, tuned for 4 GB (one worker, 512 MB database cache, 128 MB Redis cache).
- `Caddyfile`: HTTPS with automatic certificates.
- `env.example`: settings template. The real `.env` holds passwords and stays on the server.
- `backup.sh`: nightly backup, 14 days kept. Off-server copy still to be chosen.

## Note on Docker Hub
If an image pull fails with "429 Too Many Requests", pull via `mirror.gcr.io/<image>` and retag it.

## Switching to the custom image (ERPNext + WooCommerce Fusion + workshop module)

GitHub Actions builds `ghcr.io/reviride/revelrycycles-dms` whenever `image/` or `apps/` changes.
On the server:

```
cd /opt/erpnext
sed -i 's|^ERPNEXT_IMAGE=.*|ERPNEXT_IMAGE=ghcr.io/reviride/revelrycycles-dms:latest|' .env
./backup.sh
docker compose pull && docker compose up -d
docker compose exec backend bench --site dms.revelrycycles.com.au install-app woocommerce_fusion
docker compose exec backend bench --site dms.revelrycycles.com.au migrate
```
