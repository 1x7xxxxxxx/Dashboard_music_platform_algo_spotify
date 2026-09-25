#!/usr/bin/env bash
# Rotate one or more app secrets everywhere they live, without ever printing them.
#
#   tools/dev/rotate_secret.sh SPOTIFY_CLIENT_SECRET YOUTUBE_API_KEY META_APP_SECRET
#
# Type: Utility (interactive — run it in YOUR terminal, it reads each value hidden)
# Uses: bash, ssh, python3 on both ends; tools/check_central_apps.py (bind-mounted in the
#       prod scheduler) as the proof
# Persists in: ~/streamlytics/.env, ~/streamlytics/.env.local (when they carry the variable),
#              /opt/streamlytics/.env on prod (backup .env.bak-rotate-<date> first)
#
# Why (R177, 2026-09-25): gitleaks found 12 real secrets in the PUBLIC history, two still in
# service. Rewriting history does nothing (clones, forks); only rotation does. The console
# gesture is human; everything after it — three .env files, a container recreate, a proof —
# is this script, so the value is typed once, hidden, and never lands in a chat or a log.
#
# The database password is REFUSED here: it must change inside Postgres too (ALTER USER),
# in step with every client — runbook §27, step 4.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
PROD="${ROTATE_PROD_SSH-root@167.233.92.1}"          # empty = local files only (tests)
PROD_ENV="${ROTATE_PROD_ENV:-/opt/streamlytics/.env}"
read -r -a LOCAL_FILES <<< "${ROTATE_ENV_FILES:-$REPO/.env $REPO/.env.local}"
source "$(dirname "${BASH_SOURCE[0]}")/secret_dialog.sh"
ALLOWED="SPOTIFY_CLIENT_SECRET YOUTUBE_API_KEY META_APP_SECRET SOUNDCLOUD_CLIENT_SECRET"

[ $# -ge 1 ] || { echo "usage: $0 VAR [VAR…]   (parmi : $ALLOWED)"; exit 2; }
for v in "$@"; do
    case " $ALLOWED " in
        *" $v "*) ;;
        *) echo "❌ $v refusée : seules $ALLOWED se tournent ici (la base : runbook §27 étape 4)"; exit 2 ;;
    esac
done

# replace_var <file> <VAR> ; the value arrives on stdin, never on a command line
replace_var_py='
import sys, pathlib
path, var = sys.argv[1], sys.argv[2]
val = sys.stdin.read().rstrip("\n")
p = pathlib.Path(path)
lines = p.read_text(encoding="utf-8").splitlines()
out, hit = [], False
for ln in lines:
    if ln.startswith(var + "="):
        out.append(var + "=" + val); hit = True
    else:
        out.append(ln)
if not hit:
    sys.exit(3)
p.write_text("\n".join(out) + "\n", encoding="utf-8")
'

stamp="$(date +%Y%m%d-%H%M%S)"
if [ -n "$PROD" ]; then
    ssh -o BatchMode=yes "$PROD" "cp '$PROD_ENV' '$PROD_ENV.bak-rotate-$stamp'" \
        && echo "💾 prod : sauvegarde $PROD_ENV.bak-rotate-$stamp"
fi

for v in "$@"; do
    if [ "${ROTATE_GUI-}" = 1 ]; then
        val="$(dialog "$v")"          # masked Windows dialog — lets Claude run the script
    else
        printf "Nouvelle valeur de %s (masquée, Entrée pour valider) : " "$v" > /dev/tty 2>/dev/null || true
        IFS= read -rs val
        echo > /dev/tty 2>/dev/null || true
    fi
    [ -n "$val" ] || { echo "❌ $v : valeur vide, rien n'est changé"; exit 1; }
    echo "🔑 $v : ${#val} caractères reçus"
    for f in "${LOCAL_FILES[@]}"; do
        [ -f "$f" ] || continue
        if printf '%s' "$val" | python3 -c "$replace_var_py" "$f" "$v"; then
            echo "   ✓ $f"
        fi
    done
    if [ -n "$PROD" ]; then
        if printf '%s' "$val" | ssh -o BatchMode=yes "$PROD" "python3 -c '$replace_var_py' '$PROD_ENV' '$v'"; then
            echo "   ✓ prod:$PROD_ENV"
        else
            echo "   ⚠ prod : $v absente de $PROD_ENV — non ajoutée"
        fi
    fi
    unset val
done

if [ -n "$PROD" ]; then
    echo "▶ prod : recréation des conteneurs pour relire l'environnement"
    ssh -o BatchMode=yes "$PROD" "cd /opt/streamlytics && docker compose up -d --force-recreate api dashboard airflow-scheduler airflow-webserver" >/dev/null
    echo "▶ prod : preuve — authentification de chaque app centrale"
    ssh -o BatchMode=yes "$PROD" "docker exec airflow_scheduler python3 /opt/airflow/tools/check_central_apps.py --require" \
        && echo "✅ les apps centrales s'authentifient avec les nouvelles valeurs" \
        || { echo "❌ une app ne s'authentifie pas — sauvegarde : $PROD_ENV.bak-rotate-$stamp"; exit 1; }
fi
echo "Dernière étape : dis « fait » à Claude — il ajoute les empreintes gitleaks des secrets tournés à .gitleaksignore."
