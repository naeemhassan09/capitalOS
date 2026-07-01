#!/usr/bin/env bash
# Idempotent VPS bootstrap for a multi-site Docker host (Ubuntu 22.04/24.04).
# Run as a sudo-capable user (e.g. `ubuntu`):
#     sudo bash deploy/scripts/bootstrap.sh
#
# It: updates the OS, installs Docker + Compose, configures UFW (SSH/HTTP/HTTPS),
# fail2ban, unattended-upgrades, swap (if low RAM), Docker log rotation, and
# creates the shared `edge` and `dbnet` networks. It does NOT disable SSH
# password auth — do that with harden-ssh.sh AFTER you confirm key login works.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "Please run with sudo: sudo bash $0" >&2
  exit 1
fi

TARGET_USER="${SUDO_USER:-ubuntu}"
log() { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }

log "Updating the operating system"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get upgrade -y

log "Installing base packages"
apt-get install -y ca-certificates curl gnupg lsb-release ufw fail2ban \
  unattended-upgrades

log "Installing Docker Engine + Compose plugin"
if ! command -v docker >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin
fi
systemctl enable --now docker

log "Adding ${TARGET_USER} to the docker group"
usermod -aG docker "${TARGET_USER}" || true

log "Configuring Docker log rotation"
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'JSON'
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
JSON
systemctl restart docker

log "Configuring UFW firewall (SSH, HTTP, HTTPS)"
ufw allow OpenSSH || ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
ufw status verbose || true

log "Enabling unattended security upgrades"
dpkg-reconfigure -f noninteractive unattended-upgrades || true

log "Enabling fail2ban"
systemctl enable --now fail2ban

# Swap: add 2G if there is less than ~2G RAM and no swap yet (helps a 1-2G VPS).
if [[ ! -f /swapfile ]]; then
  mem_kb=$(awk '/MemTotal/ {print $2}' /proc/meminfo)
  if (( mem_kb < 2100000 )); then
    log "Low RAM detected — creating a 2G swapfile"
    fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
  fi
fi

log "Creating shared Docker networks (edge, dbnet)"
docker network inspect edge  >/dev/null 2>&1 || docker network create edge
docker network inspect dbnet >/dev/null 2>&1 || docker network create dbnet

log "Creating application directory /opt"
mkdir -p /opt
chown "${TARGET_USER}:${TARGET_USER}" /opt

cat <<EOF

Bootstrap complete.
Next steps (as ${TARGET_USER}; log out/in once so docker-group membership applies):
  1) Put the repo at /opt/capitalos  (git clone or scp).
  2) cp deploy/edge/.env.example              deploy/edge/.env               # edit
  3) cp deploy/stacks/capitalos/.env.example  deploy/stacks/capitalos/.env   # edit
  4) docker compose -f deploy/edge/docker-compose.yml up -d
  5) bash deploy/scripts/provision-db.sh capitalos
  6) bash deploy/scripts/deploy-capitalos.sh
  7) (after confirming SSH key login) sudo bash deploy/scripts/harden-ssh.sh
EOF
