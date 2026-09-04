#!/usr/bin/env bash
# Logical backup of the spotify_etl database — pg_dump (inside the postgres
# container, where the binary lives) → gzip on the host → retention prune.
#
# Usage:   tools/db_backup.sh            # → backups/spotify_etl_<UTC>.sql.gz
# Env:     BACKUP_DIR (default ./backups), RETENTION_DAYS (14), PG_CONT (auto),
#          DB_NAME (spotify_etl), DB_USER (postgres).
#
# Designed for a daily cron on the VPS. Since 2026-09-04 it also pushes the archive
# OFF the machine — see the offsite block at the bottom, ADR-014 and ADR-015.
# Env (offsite): R2_REMOTE (rclone remote:bucket/prefix) OR OFFSITE_GIT_REMOTE
#          (git URL, archive encrypted before push), R2_RETENTION_DAYS (30),
#          BACKUP_PASSPHRASE_FILE (./.backup_passphrase), OFFSITE_RECEIPT.
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
# Pourquoi ce bloc ne fait PAS échouer le script quand aucune cible n'est posée : la
# sauvegarde locale, elle, a réussi, et la faire passer en rouge la rendrait
# indiscernable d'un `pg_dump` cassé. Ce qui rend l'absence impossible à ignorer,
# c'est le contrôle de fraîcheur dans `alert_monitor` — il le dit chaque nuit. Une
# variable absente doit crier ailleurs, pas éteindre ce qui marche.
#
# Deux cibles possibles, une seule mécanique. `R2_REMOTE` reste la cible préférée
# (object storage, rétention native, egress nul) ; `OFFSITE_GIT_REMOTE` est celle
# qui a pu être posée SANS carte bancaire ni compte nouveau — un dépôt GitHub privé,
# une clé de déploiement limitée à ce seul dépôt, l'archive chiffrée AES256 avant de
# partir. Voir ADR-015 : ce n'est pas le meilleur stockage, c'est le seul qui
# existait le jour où le disque était encore la seule copie.
OFFSITE_RETENTION_DAYS="${R2_RETENTION_DAYS:-30}"
RECEIPT="${OFFSITE_RECEIPT:-$ROOT/data/offsite_receipt.json}"

# Le reçu est la seule chose que le moniteur peut lire. Il tourne dans le conteneur
# Airflow, où NI rclone NI git ne sont installés — mesuré le 2026-09-04, et c'est
# pourquoi `check_offsite_backup` aurait répondu `unreadable` par construction, même
# une fois R2 configuré. Un contrôle qui appelle un binaire absent de son image ne
# devient jamais vert. Le reçu ne s'écrit qu'APRÈS relecture du distant : il atteste
# une présence, pas une intention.
write_receipt() {  # $1 = cible, $2 = nombre d'archives, $3 = la plus récente
    mkdir -p "$(dirname "$RECEIPT")"
    printf '{"target":"%s","verified_at":"%s","archives":%s,"newest":"%s"}\n' \
        "$1" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$2" "$3" > "$RECEIPT"
    chmod 644 "$RECEIPT"
}

if [ -z "${R2_REMOTE:-}" ] && [ -z "${OFFSITE_GIT_REMOTE:-}" ]; then
    echo "⚠️  Aucune cible hors-site — AUCUNE copie hors-site. L'archive ne survit pas" >&2
    echo "    à la perte de ce disque. Configurer l'une des deux :" >&2
    echo "      R2_REMOTE=r2:streamlytics-backups/db   (rclone config, type s3)" >&2
    echo "      OFFSITE_GIT_REMOTE=git@github-backup:<owner>/<repo>.git" >&2
    exit 0
fi

if [ -n "${R2_REMOTE:-}" ]; then
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
    rclone delete "${R2_REMOTE}/" --min-age "${OFFSITE_RETENTION_DAYS}d" \
        --include "${DB}_*.sql.gz" || true

    REMOTE_N="$(rclone lsf "${R2_REMOTE}/" --include "${DB}_*.sql.gz" 2>/dev/null | wc -l)"
    write_receipt "$R2_REMOTE" "${REMOTE_N:-0}" "$(basename "$OUT")"
    echo "✅ Hors-site OK — ${REMOTE_N} archive(s) distante(s), rétention ${OFFSITE_RETENTION_DAYS} j."
    exit 0
fi

# ── Cible git : chiffrer d'abord, pousser ensuite ────────────────────────────
#
# L'archive part sur une infrastructure tierce : elle en sort chiffrée, ou elle ne
# sort pas. La phrase de passe ne doit PAS vivre uniquement sur la machine qu'elle
# protège — une sauvegarde qu'on ne peut plus déchiffrer n'est pas une sauvegarde.
PASSPHRASE_FILE="${BACKUP_PASSPHRASE_FILE:-$ROOT/.backup_passphrase}"
if [ ! -s "$PASSPHRASE_FILE" ]; then
    echo "❌ OFFSITE_GIT_REMOTE est défini mais $PASSPHRASE_FILE est absent ou vide." >&2
    echo "   Sans phrase de passe, rien ne part : le dépôt distant recevrait du clair." >&2
    exit 1
fi
for bin in gpg git; do
    command -v "$bin" >/dev/null 2>&1 || {
        echo "❌ '$bin' est absent — copie hors-site IMPOSSIBLE." >&2; exit 1; }
done

ENC="${OUT}.gpg"
gpg --batch --yes --quiet --symmetric --cipher-algo AES256 \
    --passphrase-file "$PASSPHRASE_FILE" -o "$ENC" "$OUT"
if [ ! -s "$ENC" ]; then
    echo "❌ Le chiffrement a produit un fichier vide." >&2
    exit 1
fi

# Rétention hors-site : le contenu du répertoire DEVIENT le contenu du distant, donc
# l'élagage se fait ici, avant de composer le commit.
find "$OUT_DIR" -name "${DB}_*.sql.gz.gpg" -type f \
    -mtime +"$OFFSITE_RETENTION_DAYS" -delete || true

WORK="${OFFSITE_GIT_WORK:-$ROOT/.offsite-git}"
if [ ! -d "$WORK/.git" ]; then
    mkdir -p "$WORK"
    git -C "$WORK" init -q
    git -C "$WORK" remote add origin "$OFFSITE_GIT_REMOTE"
fi
git -C "$WORK" remote set-url origin "$OFFSITE_GIT_REMOTE"
git -C "$WORK" config user.email "backup@streamlytics.fr"
git -C "$WORK" config user.name "streaMLytics backup"

find "$WORK" -maxdepth 1 -name '*.sql.gz.gpg' -delete || true
cp "$OUT_DIR"/${DB}_*.sql.gz.gpg "$WORK"/ 2>/dev/null || true
cat > "$WORK/README.md" <<'READMEEOF'
# streaMLytics — copie hors-site de `spotify_etl`

Chaque fichier est un `pg_dump` gzippé **puis chiffré en AES256** (`gpg --symmetric`).
Sans la phrase de passe, ce dépôt ne contient rien de lisible.

Restaurer :

    gpg --batch --passphrase-file <phrase> -d spotify_etl_<stamp>.sql.gz.gpg \
      | gunzip | psql -U postgres -d <base_cible>

L'historique est réécrit chaque nuit (commit orphelin, force-push) : le dépôt ne
porte que la fenêtre de rétention courante, jamais l'accumulation.
READMEEOF

# Commit orphelin : le dépôt ne doit pas grossir d'une archive par nuit pour
# l'éternité. Chaque nuit remplace l'arbre entier ; les objets devenus inatteignables
# sont ramassés des deux côtés.
git -C "$WORK" checkout -q --orphan _next
git -C "$WORK" add -A
git -C "$WORK" commit -q -m "backup $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git -C "$WORK" branch -q -D backups 2>/dev/null || true
git -C "$WORK" branch -q -m backups

echo "→ Copie hors-site vers ${OFFSITE_GIT_REMOTE} ..."
if ! git -C "$WORK" push -q --force origin backups; then
    echo "❌ La copie hors-site a échoué. L'archive locale existe, mais elle est SEULE." >&2
    exit 1
fi

# Relecture : le distant porte-t-il EXACTEMENT ce qu'on vient de pousser ? Un push
# qui rend 0 sans que la référence bouge reste possible ; deux SHA qui coïncident,
# non. C'est ce qui autorise le reçu.
LOCAL_SHA="$(git -C "$WORK" rev-parse HEAD)"
REMOTE_SHA="$(git -C "$WORK" ls-remote origin refs/heads/backups 2>/dev/null | cut -f1)"
if [ "$LOCAL_SHA" != "$REMOTE_SHA" ]; then
    echo "❌ Le distant ne porte pas le commit poussé (local $LOCAL_SHA ≠ distant ${REMOTE_SHA:-vide})." >&2
    exit 1
fi

git -C "$WORK" reflog expire --expire=now --all >/dev/null 2>&1 || true
git -C "$WORK" gc -q --prune=now >/dev/null 2>&1 || true

REMOTE_N="$(find "$WORK" -maxdepth 1 -name '*.sql.gz.gpg' | wc -l)"
write_receipt "$OFFSITE_GIT_REMOTE" "${REMOTE_N:-0}" "$(basename "$ENC")"
echo "✅ Hors-site OK — ${REMOTE_N} archive(s) distante(s) chiffrée(s), rétention ${OFFSITE_RETENTION_DAYS} j."
