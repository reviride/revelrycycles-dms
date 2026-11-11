#!/usr/bin/env bash
# One-time preparation of the ERPNext pilot VPS (Ubuntu 24.04, KVM 4: 4 GB RAM, 2 cores).
# Run as root:  bash setup-server.sh
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

# 5. SSH hardening: fail2ban, and key-only login once a key is installed (never locks you out)
apt-get -y install fail2ban && systemctl enable --now fail2ban
if [ -s /root/.ssh/authorized_keys ]; then
  printf 'PasswordAuthentication no\nKbdInteractiveAuthentication no\nPermitRootLogin prohibit-password\n' > /etc/ssh/sshd_config.d/00-keys-only.conf
  systemctl reload ssh
  echo "SSH is now key-only."
else
  echo "WARNING: no SSH key in /root/.ssh/authorized_keys, so password login stays ON. Add a key and re-run."
fi

echo "Server ready. Next: copy compose.yml, Caddyfile and .env here, then: docker compose up -d"
