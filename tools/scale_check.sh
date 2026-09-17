#!/usr/bin/env bash
# Les deux déclencheurs de R87, rejoués en une commande.
#
# R87 (répliques Streamlit + affinité Caddy) a été CLOSE PAR LA MESURE le 2026-09-11,
# avec deux seuils calculables (`.claude/dev-docs/roadmap/archive.md`). Les relire
# coûtait jusqu'ici de retrouver deux commandes dans une archive de 4 500 lignes ;
# ADR-014 § « Comment relire cette décision » a le même défaut — il LISTE ses commandes
# sans les avoir outillées. Une décision qu'on ne sait pas relire se périme en silence.
#
# ── La requête a été CORRIGÉE le 2026-09-16, et l'écart est d'un facteur deux ──
# L'ancienne comptait TOUS les `session_id`, canaris et bac à sable compris. Mesuré ce
# jour-là : pic de **12** toutes sessions confondues, **6** en ne gardant que des
# humains — et **320 des 1 043 événements (31 %) venaient du locataire `sandbox`**,
# c'est-à-dire de nous. Un canari n'a jamais été un utilisateur ; le compter dans un
# seuil de charge rapprochait artificiellement la décision de son déclencheur.
#
# Usage : make scale-check PROD_SSH=user@host
set -euo pipefail

PROD_SSH="${PROD_SSH:?set PROD_SSH=user@host}"
PG_CONT="${PROD_PG:-postgres_spotify_airflow}"
SEUIL_SESSIONS="${SEUIL_SESSIONS:-20}"

echo "▶ Déclencheur 1/2 — sessions HUMAINES distinctes dans une même minute"
echo "  (seuil de réouverture : > ${SEUIL_SESSIONS})"

# ⚠️ Fenêtre de 180 jours, ajoutée le 2026-09-17, et il faut dire ce qu'elle change
# exactement — ni plus, ni moins.
#
# Elle est aujourd'hui SÉMANTIQUEMENT NEUTRE, et c'est mesuré : `usage_events` porte
# 1 224 lignes s'étalant du 2026-06-09 au 2026-09-17, **0 au-delà de 180 jours**, pour
# 352 ko. Le pic rendu est le même borné ou non — 12 dans les deux cas.
#
# Elle n'est donc PAS un correctif de lenteur : il n'y a pas de lenteur à corriger. Elle
# aligne la requête sur la rétention que `src/utils/telemetry_retention.py` applique
# désormais (180 jours pour cette table). Au-delà de cette borne les lignes n'existeront
# plus, donc « le pic de tous les temps » et « le pic de la fenêtre » deviennent la même
# chose — et la requête cesse de dépendre d'une table dont la taille était, jusqu'au
# 2026-09-17, bornée par personne.
read -r -d '' SQL <<'SQLEOF' || true
SELECT
  COALESCE(max(s), 0) AS pic_humain,
  (SELECT COALESCE(max(t), 0) FROM (
     SELECT count(DISTINCT session_id) t FROM usage_events
     WHERE ts > now() - interval '180 days'
     GROUP BY date_trunc('minute', ts)) y) AS pic_brut_toutes_sessions
FROM (
  SELECT count(DISTINCT u.session_id) s
  FROM usage_events u
  LEFT JOIN saas_artists a ON a.id = u.artist_id
  WHERE u.ts > now() - interval '180 days'
    AND COALESCE(a.is_canary,  FALSE) = FALSE
    AND COALESCE(a.is_sandbox, FALSE) = FALSE
  GROUP BY date_trunc('minute', u.ts)) x;
SQLEOF

LIGNE=$(ssh -o ConnectTimeout=15 "$PROD_SSH" \
          "docker exec -i $PG_CONT psql -U postgres -d spotify_etl -tA -F'|'" <<< "$SQL")
PIC_HUMAIN="${LIGNE%%|*}"
PIC_BRUT="${LIGNE##*|}"

printf '  pic humain      : %s\n  pic brut        : %s  (canaris et bac à sable inclus)\n' \
       "$PIC_HUMAIN" "$PIC_BRUT"

if [ "${PIC_HUMAIN:-0}" -gt "$SEUIL_SESSIONS" ]; then
  echo "  🔴 SEUIL FRANCHI — R87 se rouvre. Voir l'inventaire de ce qui casse à N>1 :"
  echo "     tests/test_in_memory_limits_forbid_replicas.py"
else
  echo "  ✅ sous le seuil — répliques toujours injustifiées"
fi

echo
echo "▶ Déclencheur 2/2 — p50 de rendu sous 12 rendus, SUR LE SERVEUR"
echo "  (seuil de réouverture : p50 > 200 ms)"

# La mesure ne peut PAS se faire d'ici : `/mnt/…` gonfle les temps de 5× à 160× et
# `loadtest_dashboard.py` refuse de tourner depuis un chemin DrvFS. On l'expédie donc
# dans le conteneur qui sert les pages.
#
# ── L'invocation, et pourquoi elle est plus longue qu'on ne le croirait ──
# La première version de ce script IMPRIMAIT `docker exec … python3 /tmp/lt.py`. Elle
# ne marchait pas : le script importe `src.…`, donc il lui faut `/app` comme répertoire
# de travail, et `tools/` n'est pas un chemin d'import depuis `/tmp`. Le message d'erreur
# du script lui-même le disait — il a fallu le lire.
# C'est la classe `a-printed-command-is-runnable-as-printed`, commise dans le fichier
# qui la cite. Le script EXÉCUTE donc, au lieu de suggérer : ce qui n'est pas exécuté
# n'est pas vérifié. Même forme que `artist-preflight-prod` dans le Makefile.
TMP_TGZ=$(mktemp -u /tmp/_scale_lt_XXXX.tgz)
tar czf "$TMP_TGZ" tools/loadtest_dashboard.py
scp -q "$TMP_TGZ" "$PROD_SSH:$TMP_TGZ"
rm -f "$TMP_TGZ"

SORTIE=$(ssh -o ConnectTimeout=20 "$PROD_SSH" \
  "docker cp $TMP_TGZ ${DASH_CONT:-streamlytics_dashboard}:/tmp/ >/dev/null \
   && docker exec -w /app ${DASH_CONT:-streamlytics_dashboard} sh -c \
        'tar xzf $TMP_TGZ -C /app && python3 tools/loadtest_dashboard.py -n 12' 2>&1; \
   rm -f $TMP_TGZ")

echo "$SORTIE" | sed -n '/rendus mesurés/,$p' | sed 's/^/  /'

P50=$(echo "$SORTIE" | sed -n 's/.*p50 *\([0-9]\+\) ms.*/\1/p' | head -1)
if [ -n "${P50:-}" ] && [ "$P50" -gt "${SEUIL_P50:-200}" ]; then
  echo "  🔴 SEUIL FRANCHI — R87 se rouvre."
else
  echo "  ✅ p50 = ${P50:-?} ms, sous le seuil de ${SEUIL_P50:-200} ms"
fi

echo
# Guillemets SIMPLES : une apostrophe inverse dans une chaîne double devient une
# substitution de commande, et ce bloc s'est exécuté comme tel au premier essai
# (`loadtest_dashboard.py: command not found`). Un avertissement qui se casse en
# s'affichant n'avertit de rien.
echo '⚠️  Ces deux déclencheurs ne mesurent PAS la concurrence. loadtest_dashboard.py'
echo '   rend 12 fois EN SÉRIE puis divise, et il le dit lui-même (lignes 27-40) : sous'
echo "   AppTest, un st.write('hello') passe de 352 ms à un fil à 2 144 ms à six."
echo "   Le plafond d'utilisateurs qu'il imprime est une ARITHMÉTIQUE sur p50, pas une"
echo "   observation. Pour le vrai chiffre : tools/loadtest_concurrency.py."
