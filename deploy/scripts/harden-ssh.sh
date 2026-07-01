#!/usr/bin/env bash
# Disable SSH password auth and root login — key-based access only.
# RUN THIS ONLY AFTER you have confirmed you can log in with your SSH KEY,
# otherwise you can lock yourself out.
#     sudo bash deploy/scripts/harden-ssh.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then echo "Run with sudo: sudo bash $0" >&2; exit 1; fi

TARGET_USER="${SUDO_USER:-ubuntu}"
KEYS="/home/${TARGET_USER}/.ssh/authorized_keys"

if [[ ! -s "$KEYS" ]]; then
  echo "Refusing to harden: $KEYS is missing or empty." >&2
  echo "Install your public key first (from your Mac):" >&2
  echo "  ssh-copy-id ${TARGET_USER}@<server-ip>" >&2
  exit 1
fi

echo "Found authorized_keys for ${TARGET_USER}. Disabling password + root SSH login."
mkdir -p /etc/ssh/sshd_config.d
# sshd uses the FIRST value seen for a keyword. Ubuntu's 50-cloud-init.conf often
# sets "PasswordAuthentication yes" and sorts before a 99- file, so it would win.
# We (a) rewrite any cloud-init/cloudimg drop-ins to "no" and (b) drop our rule as
# 00- so it is also read first.
for f in /etc/ssh/sshd_config.d/*cloud-init*.conf /etc/ssh/sshd_config.d/*cloudimg*.conf; do
  [ -f "$f" ] && sed -i 's/^\s*PasswordAuthentication\s\+yes/PasswordAuthentication no/I' "$f"
done
cat > /etc/ssh/sshd_config.d/00-hardening.conf <<'CONF'
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
CONF
cp /etc/ssh/sshd_config.d/00-hardening.conf /etc/ssh/sshd_config.d/99-hardening.conf

# Validate config before restarting so a typo can't lock you out.
sshd -t
systemctl restart ssh || systemctl restart sshd

echo "Effective settings:"
sshd -T 2>/dev/null | grep -E "^(passwordauthentication|permitrootlogin|pubkeyauthentication)" || true

echo "SSH hardened: key-only login, no root SSH. Keep your current session open"
echo "and verify a NEW key-based login works before closing it."
