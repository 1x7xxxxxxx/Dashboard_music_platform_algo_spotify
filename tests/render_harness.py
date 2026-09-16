"""La liste des vues et le script de rendu — écrits UNE fois.

Type: Utility (test helper)
Uses: rien — des constantes, pas d'import lourd
Triggers: tests/test_views_render_smoke.py, tests/test_a_render_opens_one_connection.py
Persists in: nothing

Pourquoi ce module existe — mesuré le 2026-09-16
------------------------------------------------
Deux fichiers rendaient les mêmes vues avec le même script, chacun avec sa PROPRE copie
de la liste et du gabarit. Ils se sont accordés la plupart du temps, et neuf jours
durant ils ne se sont pas accordés : `process_guide` (module supprimé) et `upload_csv`
(plus de `show()` depuis la fusion du 2026-09-04) ont quitté la liste de
`test_views_render_smoke.py` le 2026-09-06, et celle de
`test_a_render_opens_one_connection.py` seulement le **2026-09-15**.

Ce que ça a coûté, écrit dans le fichier concerné : pendant ces neuf jours, le script
levait à l'import, le rendu ouvrait **zéro** connexion, et `0 <= 1` passait. Deux
rendus `AppTest` complets payés à chaque exécution pour ne rien prouver — et un garde
vert sur deux vues qui n'existaient plus.

Le précédent exact du dépôt est `tests/nav_source.py`, écrit après que neuf gardes
soient partis au rouge ensemble le jour où `_NAV_SECTIONS` a changé de fichier : quand
N tests lisent la même chose, ils la lisent au même endroit.

Ce que ce module ne fait PAS
----------------------------
Il ne fusionne pas les deux fichiers et ne réduit pas le nombre de rendus. Chacun
prouve une chose différente — `at.exception` d'un côté, le compte de connexions de
l'autre — et `test_a_render_opens_one_connection.py` est nommé comme garde par une
signature du catalogue d'erreurs. Ce dépôt attaque le temps d'ATTENTE (le sharding
parallélise ces rendus), jamais la couverture de la porte.
"""
from __future__ import annotations

# Les vues rendues sous une session ADMIN. Une vue absente d'ici n'est rendue par
# personne — c'est arrivé jusqu'au 2026-08-20 pour les trois que rencontre d'abord un
# artiste neuf (`onboarding`, `onboarding_health`, `register`), ajoutées depuis.
VIEWS = [
    "admin", "account", "airflow_kpi", "alerts", "apple_music", "billing",
    "credentials", "data_wrapped", "db_health", "etl_logs", "export_csv",
    "export_pdf", "home", "hypeddit", "imusician", "instagram", "meta_ads_overview",
    "meta_breakdowns", "meta_cpr_optimizer", "meta_creatives", "meta_mapping",
    "meta_x_spotify", "ml_performance",
    "promo_admin", "referral", "referral_admin",
    "revenue_forecast", "sacem", "saisie_s4a", "soundcloud",
    "spotify_s4a_combined", "trigger_algo", "upgrade", "usage_analytics",
    "useful_links", "youtube",
    "onboarding", "onboarding_health", "register",
]

# Les vues rendues sous un locataire NEUF ET VIDE — l'état du premier jour, où la
# plupart des requêtes ne rendent rien.
#
# ⚠️ Ce n'est PAS « les vues qu'un locataire atteint », et le nom le dit maintenant.
# Deux autres listes de vues vivent dans la suite, avec des QUESTIONS différentes, et
# elles ne doivent pas être unifiées :
#   * `tests/test_stray_session_reads_nothing.py::TENANT_VIEWS` (22) — les vues qui
#     LISENT de la donnée scopée par locataire ; une vue absente y est sans locataire
#     par nature ou réservée aux admins ;
#   * `tests/test_a_view_says_something_or_says_why.py::_VIEWS` (11) — les vues du
#     parcours qui doivent MONTRER quelque chose ; les pages d'action en sont exclues.
# Jusqu'au 2026-09-16, celle-ci s'appelait `TENANT_VIEWS` elle aussi : deux constantes
# du même nom, dans la même suite, différant de dix entrées.
EMPTY_TENANT_VIEWS = [
    "home", "onboarding", "onboarding_health", "credentials", "account",
    "soundcloud", "youtube", "instagram", "spotify_s4a_combined", "apple_music",
    "export_csv", "export_pdf", "useful_links",
]

# `AppTest.from_string` exécute ce script DANS le processus des tests : tout ce qu'il
# mute dans un module y survit. Il ne mute rien — il pose de l'état de session, qui est
# recréé par `AppTest` à chaque rendu.
SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "admin"
st.session_state["artist_id"] = 1
st.session_state["email"] = "admin@test"
st.session_state["authenticated"] = True
from src.dashboard.views.{view} import show
show()
"""

TENANT_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["role"] = "artist"
st.session_state["artist_id"] = {artist_id}
st.session_state["email"] = "artist@test"
st.session_state["authenticated"] = True
from src.dashboard.views.{view} import show
show()
"""
