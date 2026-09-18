"""La ligne « Total » des CSV Spotify for Artists — un seul littéral pour tout le dépôt.

Type: Utility
Uses: rien
Triggers: toute requête sur `s4a_song_timeline`
Depends on: rien
Persists in: nothing

Pourquoi ce module existe — mesuré le 2026-09-18
-------------------------------------------------
CLAUDE.md déclare cette valeur **obligatoire** : « every query on `s4a_song_timeline`
must add `AND song NOT ILIKE '%1x7xxxxxxx%'` ». Elle était écrite **cinq fois** :

    src/dashboard/utils/kpi_helpers.py:50   ARTIST_NAME_FILTER   (la canonique)
    src/dashboard/views/db_health.py:25     _ARTIST_NAME_FILTER
    src/api/routers/ml.py:17                _ARTIST_NAME_FILTER
    src/api/routers/kpis.py:16              _ARTIST_NAME_FILTER
    src/api/routers/streams.py:17           _ARTIST_NAME_FILTER

⚠️ **Et les trois copies de l'API avaient une RAISON**, ce qui est le point : importer
depuis `kpi_helpers` tirerait `streamlit` dans le processus `uvicorn` — ce module
l'importe à la ligne 5. Un développeur qui refuse cette dépendance et recopie la
constante fait le bon arbitrage avec les mauvais outils. Le remède n'est donc pas
« importez la canonique », c'est **un domicile que les deux couches peuvent atteindre** :
`src/utils/` est déjà ce que `src/api/` importe (`http_metrics`, `request_throttle`,
`pg_connect`…).

Les cinq copies étaient identiques le jour où elles ont été trouvées. La divergence
était LATENTE, pas mesurée — et c'est exactement ce que
`a-rule-copied-is-a-rule-that-will-diverge` décrit : elle se déclenchera à la première
modification d'une seule copie.
"""
from __future__ import annotations

# Le nom d'artiste factice que Spotify for Artists met sur sa ligne de TOTAL. Une
# requête qui l'oublie compte le total comme un morceau de plus.
ARTIST_NAME_FILTER = "1x7xxxxxxx"

# Le motif `ILIKE` prêt à l'emploi — la forme que toutes les requêtes utilisaient en
# recomposant `f"%{ARTIST_NAME_FILTER}%"` chacune de leur côté.
ARTIST_NAME_LIKE = f"%{ARTIST_NAME_FILTER}%"
