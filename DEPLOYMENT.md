# CapitalOS — Multi-Site VPS Deployment

This deploys CapitalOS to a single VPS designed to host **multiple independent
websites**:

- **One shared Caddy** reverse proxy — the only public service (ports 80/443),
  automatic **Let's Encrypt** TLS for every domain.
- **One shared Postgres** — each site gets its **own database + dedicated role**
  (isolated credentials), which is far lighter on RAM than one Postgres per site.
- **Each app is its own isolated Compose stack** (own containers, own network,
  own secrets). Adding a site later = new stack folder + one Caddy block + a
  provisioned database.

```
internet ──▶ Caddy (edge)  ──▶ capitalos-frontend  (SPA)
                           ──▶ capitalos-backend    (/api → FastAPI)
                                     │
                                     └─▶ shared-postgres (private dbnet, db: capitalos)
```

Target for this guide: **your-domain.example → YOUR_SERVER_IP** (A record
already configured).

---

## 0. Prerequisites & security first

- DNS `A` record `your-domain.example → YOUR_SERVER_IP` (✅ done). Let's Encrypt
  needs this resolving before step 5.
- **Rotate the VPS password** you were given (it was shared in plaintext). After
  step 6 we switch to **key-only SSH** and disable passwords entirely.

### Install your SSH key (run on your **Mac**, you type the password)

Pick one of your existing public keys (you have `id_rsa.pub`, `your-key.pub`, …):

```bash
# Default RSA key (simplest):
ssh-copy-id -i ~/.ssh/id_rsa.pub ubuntu@YOUR_SERVER_IP

# …or a specific key:
ssh-copy-id -i ~/.ssh/your-key.pub ubuntu@YOUR_SERVER_IP
```

Then confirm key login works (should NOT prompt for a password):

```bash
ssh ubuntu@YOUR_SERVER_IP
```

> Assistant note: I don't log in with your password — that's why you run
> `ssh-copy-id` yourself. Once the key works, all remaining steps are key-based.

---

## 1. Get the code onto the server

From your Mac (rsync, excluding local junk):

```bash
rsync -az --exclude .git --exclude node_modules --exclude 'frontend/node_modules' \
  --exclude '.env' --exclude 'backend/scripts/seed_real.py' \
  ./  ubuntu@YOUR_SERVER_IP:/opt/capitalos/
```
…or `git clone` your repo into `/opt/capitalos` on the server.

## 2. Bootstrap the host (once)

```bash
ssh ubuntu@YOUR_SERVER_IP
cd /opt/capitalos
sudo bash deploy/scripts/bootstrap.sh
# log out and back in so docker-group membership applies
exit && ssh ubuntu@YOUR_SERVER_IP
```

Installs Docker + Compose, UFW (22/80/443), fail2ban, unattended-upgrades, swap
(if low RAM), Docker log rotation, and creates the `edge` + `dbnet` networks.

## 3. Configure the shared edge stack

```bash
cd /opt/capitalos
cp deploy/edge/.env.example deploy/edge/.env
nano deploy/edge/.env
#   ACME_EMAIL=you@example.com
#   POSTGRES_SUPERUSER_PASSWORD=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))")
```

Start Caddy + Postgres:

```bash
docker compose -f deploy/edge/docker-compose.yml up -d
```

## 4. Provision the CapitalOS database

```bash
bash deploy/scripts/provision-db.sh capitalos
# prints:  DATABASE_URL=postgresql+psycopg2://capitalos:<pw>@shared-postgres:5432/capitalos
```

## 5. Configure & deploy the app

```bash
cp deploy/stacks/capitalos/.env.example deploy/stacks/capitalos/.env
nano deploy/stacks/capitalos/.env
#   SECRET_KEY=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))")
#   ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())")
#   DATABASE_URL=...          # paste the line from step 4
#   (APP_URL / DOMAIN / CORS already set to your-domain.example)

bash deploy/scripts/deploy-capitalos.sh
```

This builds the images, runs Alembic migrations, starts the app, waits for the
backend health check, and reloads Caddy.

## 6. Verify

```bash
curl -I https://your-domain.example            # 200, valid Let's Encrypt cert
curl  https://your-domain.example/api/v1/health/ready
```
Open **https://your-domain.example** → complete first-run owner setup.
(The first HTTPS hit may take ~30s while Caddy obtains the certificate.)

## 7. Lock down SSH (after key login is confirmed)

```bash
sudo bash deploy/scripts/harden-ssh.sh   # disables password + root SSH
```

---

## Load your real data (optional)

`seed_real.py` is git-ignored, so copy it up separately and run it in the backend
container:

```bash
scp backend/scripts/seed_real.py ubuntu@YOUR_SERVER_IP:/opt/capitalos/backend/scripts/
docker compose -f deploy/stacks/capitalos/docker-compose.yml \
  exec -T -e SEED_REAL_PASSWORD='<your-login-pw>' backend python -m scripts.seed_real
```

## Adding another website later

1. Point its DNS `A` record at the VPS.
2. Add a site block in `deploy/edge/Caddyfile` (copy the example) with its domain
   and its container aliases; `docker compose -f deploy/edge/docker-compose.yml restart caddy`.
3. `bash deploy/scripts/provision-db.sh <site>` for an isolated database.
4. Create `deploy/stacks/<site>/docker-compose.yml` (join `edge` + `dbnet`, set the
   frontend/backend aliases) and its `.env`, then bring it up.

## Backups

`deploy/scripts/backup.sh` runs `pg_dump` (add `--project`/DB name for the shared
server), gzips, optionally encrypts, and prunes on a 7-daily / 4-weekly / 6-monthly
schedule; `restore.sh` and `verify-backup.sh` accompany it. Schedule nightly with
cron. See `BACKUP_AND_RECOVERY.md`. **Never delete the Caddy `caddy_data` volume**
(it holds your TLS certs) or the `shared_pgdata` volume.

## Updating an app later

```bash
cd /opt/capitalos && git pull        # or rsync again
bash deploy/scripts/deploy-capitalos.sh
```

## Operational notes

- Only Caddy publishes ports (80/443/UDP 443). Postgres is on the private `dbnet`
  network only — never exposed to the internet.
- Certificates auto-renew via Caddy; nothing to do.
- Per-site isolation: a site can only reach its own database (separate role +
  password). Compromise of one app does not grant access to another's data.
