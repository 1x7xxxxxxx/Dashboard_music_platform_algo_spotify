# Migration Railway → Hetzner CX33 — play-by-play

Reference doc for the future migration of streaMLytics from Railway to a self-hosted Hetzner Cloud VPS. **Not yet executed.** Estimated total effort : 1 working day (4-8h setup + 2h smoke tests + DNS bascule).

## Why this migration

- Airflow scheduler must run 24/7 (daemon, not request-driven). Railway is built for stateless web services ; running a scheduler dyno there is an anti-pattern that costs €30-50/mo.
- Hetzner CX33 (4 vCPU AMD, 8 GB RAM, 80 GB NVMe, 20 TB BW) costs **€6.99/mo** (incl. IPv4) — divides infra cost by 5-7×.
- Stack is already 100 % Docker Compose : no Railway-specific lock-in to undo.
- Full benchmark and rationale : `.claude/plans/fais-moi-un-r-cap-des-iridescent-pelican.md`.

---

## 0. Pre-requisites (do this BEFORE provisioning the VPS)

### 0.1 — Backup current PG
```bash
# From wherever PG currently runs (Railway PG plugin OR local Docker)
docker exec spotify-postgres pg_dump -U postgres -d spotify_etl \
  --format=custom --file=/tmp/spotify_etl.dump
docker cp spotify-postgres:/tmp/spotify_etl.dump ./backup-$(date +%F).dump

# Sanity check the dump is non-empty
ls -lh backup-*.dump   # should be ≥ several MB
```

### 0.2 — Repo state
- `main` branch up to date and CI green
- No uncommitted secrets in `.env*` (verify via `git status` + `git ls-files | grep -E '\.env'`)
- `.env.production` template exists in `.env.production.example` (or document the exact var list — see step 5)

### 0.3 — DNS
Have a domain ready and 3 sub-domains decided :
- `dashboard.<domain>` → Streamlit (port 8501)
- `airflow.<domain>` → Airflow webserver (port 8080)
- `api.<domain>` → FastAPI (port 8000)

DNS records will be flipped at step 10 — for now just identify the domain registrar and confirm you have access.

### 0.4 — Critical secrets to migrate (DO NOT regenerate)
- `FERNET_KEY` — ⚠️ MUST be the same on Hetzner. Regenerating it makes every `artist_credentials` row undecryptable. Copy the existing value byte-for-byte.
- `STRIPE_WEBHOOK_SECRET` — must match the value Stripe uses to sign webhook events. Either reuse, or rotate AFTER updating the Stripe dashboard webhook URL (step 10).

---

## 1. Provision Hetzner CX33

1. Console : https://console.hetzner.cloud → New Project → Add Server
2. Image : **Ubuntu 24.04**
3. Type : **CX33** (4 vCPU AMD, 8 GB RAM, 80 GB NVMe SSD)
4. Location : **Falkenstein (FSN1)** or **Helsinki (HEL1)** — Falkenstein has lower latency to most EU users, Helsinki is greener (hydro power)
5. Networking : IPv4 + IPv6
6. SSH key : upload your public key (`~/.ssh/id_ed25519.pub`) so first login is key-based
7. Backups : ✅ Enable (+€1.30/mo, 7-day retention) — cheapest insurance available
8. Name : `streamlytics-prod`
9. Click **Create & Buy now** (~€8.30/mo total with backups)

Note the public IPv4 — we'll use it as `HETZNER_HOST` later.

---

## 2. Initial hardening (10 minutes)

```bash
ssh root@<IPv4>

# Update + essentials
apt update && apt upgrade -y
apt install -y ufw fail2ban git curl

# Firewall — only SSH + HTTP/HTTPS
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable

# Create unprivileged deploy user
adduser --disabled-password --gecos "" deploy
usermod -aG sudo deploy
mkdir -p /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/
chown -R deploy:deploy /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
chmod 600 /home/deploy/.ssh/authorized_keys

# Disable root SSH + password login
sed -i 's/^#*PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config
sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart sshd

# Confirm fail2ban running
systemctl enable --now fail2ban
fail2ban-client status sshd
```

From now on, log in as `deploy` : `ssh deploy@<IPv4>`.

---

## 3. Docker + docker-compose

```bash
# As deploy user
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker deploy
# Re-login so the group takes effect
exit && ssh deploy@<IPv4>

# Sanity check
docker run --rm hello-world
docker compose version    # should report v2.x
```

---

## 4. Caddy (reverse proxy + automatic Let's Encrypt)

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy
```

Edit `/etc/caddy/Caddyfile` :
```caddyfile
dashboard.example.com {
    reverse_proxy localhost:8501
}

airflow.example.com {
    reverse_proxy localhost:8080
}

api.example.com {
    reverse_proxy localhost:8000
}
```

```bash
sudo systemctl restart caddy
sudo systemctl enable caddy
# Caddy auto-fetches Let's Encrypt certs on first request — DNS must point to this host first (step 10)
```

---

## 5. Clone repo + `.env.production`

```bash
cd /home/deploy
git clone https://github.com/<owner>/streaMLytics.git
cd streaMLytics
cp .env.example .env       # then edit with production values
```

**Required env vars** (verify against `.env.example` + `docker-compose.yml`) :
| Var | Source / how to get |
|---|---|
| `DATABASE_HOST` | `postgres` (docker-compose service name) |
| `DATABASE_PORT` | `5432` |
| `DATABASE_NAME` | `spotify_etl` |
| `DATABASE_USER` | `postgres` |
| `DATABASE_PASSWORD` | strong random — generate via `openssl rand -base64 32` |
| `FERNET_KEY` | ⚠️ **REUSE existing value** (see § 0.4) |
| `AIRFLOW_ADMIN_USERNAME` | `admin` (or rename) |
| `AIRFLOW_ADMIN_PASSWORD` | strong random |
| `AIRFLOW_BASE_URL` | `http://airflow-webserver:8080` (internal Docker network) |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | Gmail App Password |
| `ALERT_EMAIL` | recipient for DAG failure callbacks |
| `STRIPE_SECRET_KEY` | Stripe Dashboard → Developers → API keys |
| `STRIPE_WEBHOOK_SECRET` | Stripe Dashboard → Webhooks → endpoint signing secret |
| `STRIPE_CHECKOUT_URL` / `STRIPE_PORTAL_URL` | Stripe customer portal config |
| `META_APP_SECRET` | Meta Developer Console (only if used outside per-artist creds) |
| `YOUTUBE_API_KEY` | Google Cloud Console |

```bash
chmod 600 .env             # restrict to owner only
```

---

## 6. Restore DB

```bash
# Bring up only Postgres
docker compose up -d postgres

# Wait for it to be ready
until docker compose exec -T postgres pg_isready -U postgres; do sleep 1; done

# Copy + restore the dump
docker cp ./backup-<DATE>.dump streamlytics-postgres-1:/tmp/
docker compose exec -T postgres pg_restore \
  -U postgres -d spotify_etl --clean --if-exists /tmp/backup-<DATE>.dump

# Sanity : count artists
docker compose exec -T postgres psql -U postgres -d spotify_etl \
  -c "SELECT COUNT(*) FROM saas_artists;"
```

---

## 7. Bring up the rest

```bash
docker compose up -d                          # all services
make migrate                                  # apply any new migrations safely
docker compose ps                             # all services should be "Up"
docker compose logs --tail=50 airflow-scheduler   # confirm DAGs are picked up
```

Visit each subdomain (after DNS is pointed at step 10) :
- `https://dashboard.example.com` → login → confirm the artist list + one dashboard view loads with real data
- `https://airflow.example.com` → confirm DAG list is the production set
- `https://api.example.com/health` → expect 200

---

## 8. CI/CD — GitHub Action `deploy-on-main`

`.github/workflows/deploy.yml` :
```yaml
name: Deploy to Hetzner

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.HETZNER_HOST }}
          username: deploy
          key: ${{ secrets.HETZNER_SSH_KEY }}
          script: |
            set -euo pipefail
            cd /home/deploy/streaMLytics
            git fetch --all --prune
            git reset --hard origin/main
            docker compose pull
            docker compose up -d --build
            # Apply migrations
            cd /home/deploy/streaMLytics && make migrate
            # Restart Airflow scheduler so it picks up DAG file changes
            docker compose restart airflow-scheduler
```

GitHub repo settings → Secrets and variables → Actions :
- `HETZNER_HOST` — public IPv4
- `HETZNER_SSH_KEY` — private SSH key of the `deploy` user (generate a dedicated key pair, NOT your personal key)

---

## 9. Daily PG backups → Storage Box

Provision a **Storage Box BX11** (1 TB, €4.50/mo) via Hetzner console. Note the SSH user (e.g. `u123456`) and host (`u123456.your-storagebox.de`).

```bash
# Add Storage Box SSH key to deploy user
ssh-keygen -t ed25519 -f /home/deploy/.ssh/storagebox -N ""
cat /home/deploy/.ssh/storagebox.pub  # paste into Storage Box → Sub-account SSH keys
```

`/etc/cron.daily/pg-backup` (chmod 755) :
```bash
#!/bin/bash
set -euo pipefail
TS=$(date +%F-%H%M)
DUMP="/tmp/spotify_etl-$TS.dump"

docker exec streamlytics-postgres-1 pg_dump -U postgres -d spotify_etl \
  --format=custom > "$DUMP"

rsync -e "ssh -i /home/deploy/.ssh/storagebox -o StrictHostKeyChecking=accept-new" \
  -av "$DUMP" u123456@u123456.your-storagebox.de:backups/

# Local cleanup (keep 3 days)
find /tmp/spotify_etl-*.dump -mtime +3 -delete

# Storage Box rotation (keep 30 days)
ssh -i /home/deploy/.ssh/storagebox u123456@u123456.your-storagebox.de \
  "find backups/ -mtime +30 -delete"
```

Test it once manually before relying on cron : `sudo /etc/cron.daily/pg-backup`.

---

## 10. DNS bascule + Railway sunset

1. **Run in parallel for 24-48h** : keep Railway serving production traffic, while Hetzner is reachable on a temporary subdomain (e.g. `staging.example.com`).
2. **Smoke test on staging** : login as a real artist, trigger a manual DAG, verify data lands, check Stripe webhook delivery (Stripe Dashboard → Events → Webhook attempts).
3. **Update Stripe webhook URL** : Stripe Dashboard → Developers → Webhooks → edit endpoint URL to `https://api.example.com/webhooks/stripe`. Verify a test event delivers OK.
4. **Update DNS A/AAAA records** : `dashboard`/`airflow`/`api` → Hetzner IP. Set TTL to 300s 24h beforehand for fast rollback.
5. **Watch Caddy logs for first cert provisioning** : `sudo journalctl -u caddy -f` — you should see Let's Encrypt obtain certificates within seconds.
6. **Retain Railway PG read-only for 7 days** as rollback insurance. Pause non-PG services to stop billing.
7. **After 7 days clean** : delete the Railway project.

---

## 11. Monitoring (optional but recommended)

Quick win : **Uptime Kuma** in Docker, exposed via Caddy on `uptime.example.com`. Free, dashboard-driven, supports HTTP/TCP/cron checks + Discord/email/Telegram alerts.

```bash
# Add to docker-compose.yml or run standalone:
docker run -d --restart=always -p 3001:3001 \
  -v uptime-kuma:/app/data --name uptime-kuma louislam/uptime-kuma:1
```

Add Caddy block :
```caddyfile
uptime.example.com {
    reverse_proxy localhost:3001
}
```

Probe targets to add immediately :
- `https://dashboard.example.com` — HTTP 200, every 60s
- `https://api.example.com/health` — HTTP 200, every 60s
- `https://airflow.example.com/health` — HTTP 200, every 5min
- TCP `localhost:5432` (postgres) — every 60s, only reachable inside the VPS

---

## Estimated effort

| Phase | Time |
|---|---|
| 0 — pre-reqs + backup | 30 min |
| 1-3 — provision + harden + Docker | 30 min |
| 4 — Caddy | 15 min |
| 5-7 — repo + .env + restore + smoke | 1-2h |
| 8 — GitHub Action | 30 min |
| 9 — backups | 30 min |
| 10 — DNS bascule + Stripe webhook update | 1-2h (incl. wait time) |
| 11 — monitoring | 30 min |
| **Total** | **~1 working day** |

---

## Rollback plan

If anything goes badly wrong post-DNS-bascule :
1. Re-point DNS records back to Railway (TTL 300s = recovery in ~5 min).
2. Re-enable Railway services if paused.
3. PG : Railway PG was kept read-only for 7 days. To resync any new writes done on Hetzner during the cutover window : `pg_dump` Hetzner → `pg_restore` Railway (with `--data-only --table=...` for the tables that received writes).
4. Stripe webhook : revert URL in Stripe Dashboard.

---

## Out of scope for this doc

- Multi-region / HA (single VPS is single point of failure — acceptable at current scale)
- Kubernetes / orchestration beyond docker-compose
- Centralized logs (default `docker logs` is enough until ≥10 services)
- Secret manager (Vault, Doppler) — env file is fine until team grows beyond solo
