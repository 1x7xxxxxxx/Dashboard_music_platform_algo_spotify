#!/usr/bin/env bash
# Logical backup of the spotify_etl database — pg_dump (inside the postgres
# container, where the binary lives) → gzip on the host → retention prune.
#
# Usage:   tools/db_backup.sh            # → backups/spotify_etl_<UTC>.sql.gz
# Env:     BACKUP_DIR (default ./backups), RETENTION_DAYS (14), PG_CONT (auto),
#          DB_NAME (spotify_etl), DB_USER (postgres).
#
# Designed for a daily cron on the VPS. Since 2026-09-04 it also pushes the archive
# OFF the machine — see the offsite block at the bottom and ADR-014.
# Env (offsite): R2_REMOTE (rclone remote:bucket/prefix), R2_RETENTION_DAYS (30).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PG_CONT="${PG_CONT:-$(docker ps --format '{{.Names}}' | grep '^postgres_spotify' | head -1)}"
DB="${DB_NAME:-spotify_etl}"
USER="${DB_USER:-postgres}"
OUT_DIR="${BACKUP_DIR:-$ROOT/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

if [ -z "$PG_CONT" ]; then
    echo "❌ Postgres container not running. Run 'make up' first." >&2
    exit 1
fi

mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%d_%H%M%S)"
OUT="$OUT_DIR/${DB}_${STAMP}.sql.gz"

echo "→ Dumping '$DB' from container '$PG_CONT' ..."
# --no-owner/--no-privileges keep the dump portable across hosts/roles.
docker exec "$PG_CONT" pg_dump -U "$USER" -d "$DB" --no-owner --no-privileges \
    | gzip > "$OUT"

if [ ! -s "$OUT" ]; then
    echo "❌ Backup is empty — pg_dump likely failed." >&2
    rm -f "$OUT"
    exit 1
fi
echo "✅ Backup written: $OUT ($(du -h "$OUT" | cut -f1))"

# Retention — prune dumps older than RETENTION_DAYS.
find "$OUT_DIR" -name "${DB}_*.sql.gz" -type f -mtime +"$RETENTION_DAYS" -print -delete \
    | sed 's/^/  pruned: /' || true
echo "✅ Retention applied (> ${RETENTION_DAYS} days)."

# ── Copie hors-site ──────────────────────────────────────────────────────────
#
# Mesuré le 2026-09-03 : les 21 archives vivaient sur `/dev/sda1`, LE DISQUE DE LA
# BASE, et le crontab ne contenait ni rsync, ni s3, ni rclone. Une sauvegarde qui
# meurt avec ce qu'elle protège n'est pas une sauvegarde, c'est une copie.
#
# Pourquoi ce bloc ne fait PAS échouer le script quand `R2_REMOTE` est absent : la
# sauvegarde locale, elle, a réussi, et la faire passer en rouge la rendrait
# indiscernable d'un `pg_dump` cassé. Ce qui rend l'absence impossible à ignorer,
# c'est le contrôle de fraîcheur distant dans `alert_monitor` — il le dit chaque
# nuit. Une variable absente doit crier ailleurs, pas éteindre ce qui marche.
if [ -z "${R2_REMOTE:-}" ]; then
    echo "⚠️  R2_REMOTE non défini — AUCUNE copie hors-site. L'archive ne survit pas" >&2
    echo "    à la perte de ce disque. Configurer :" >&2
    echo "      rclone config   (remote de type 's3', provider Cloudflare)" >&2
    echo "      R2_REMOTE=r2:streamlytics-backups/db" >&2
    exit 0
fi

if ! command -v rclone >/dev/null 2>&1; then
    echo "❌ R2_REMOTE est défini mais rclone est absent — copie hors-site IMPOSSIBLE." >&2
    echo "   curl https://rclone.org/install.sh | sudo bash" >&2
    exit 1
fi

echo "→ Copie hors-site vers ${R2_REMOTE} ..."
if ! rclone copy "$OUT" "${R2_REMOTE}/" --s3-no-check-bucket --stats-one-line; then
    # Échec dur, à dessein : ici l'intention d'avoir une copie distante est explicite
    # (la variable est posée), donc son échec est un incident, pas une abstention.
    echo "❌ La copie hors-site a échoué. L'archive locale existe, mais elle est SEULE." >&2
    exit 1
fi

# Rétention distante, indépendante de la locale : un disque plein sur la machine ne
# doit pas emporter l'historique distant, et réciproquement.
R2_RETENTION_DAYS="${R2_RETENTION_DAYS:-30}"
rclone delete "${R2_REMOTE}/" --min-age "${R2_RETENTION_DAYS}d" \
    --include "${DB}_*.sql.gz" || true

REMOTE_N="$(rclone lsf "${R2_REMOTE}/" --include "${DB}_*.sql.gz" 2>/dev/null | wc -l)"
echo "✅ Hors-site OK — ${REMOTE_N} archive(s) distante(s), rétention ${R2_RETENTION_DAYS} j."
