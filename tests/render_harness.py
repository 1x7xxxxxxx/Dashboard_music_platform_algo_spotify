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
Il ne fusionne pas les deux fichiers. Chacun prouve une chose différente —
`at.exception` d'un côté, le compte de connexions de l'autre — et
`test_a_render_opens_one_connection.py` est nommé comme garde par une signature du
catalogue d'erreurs. Les deux noms survivent, les deux propriétés survivent.

Ce qu'il fait depuis le 2026-09-18 : le RENDU est payé une fois
---------------------------------------------------------------
Les deux propriétés se lisent sur le même `AppTest`. `render_once()` rend la vue,
retient `(erreur, connexions)` — deux scalaires, jamais l'objet `AppTest`, dont la
rétention avait fait sortir la suite par l'OOM le 2026-09-17 — et sert les deux
gardes depuis un `lru_cache`.

⚠️ Un `lru_cache` vit dans UN processus. Sous `xdist`, les deux tests d'une même vue
doivent tomber dans le même worker, sinon le cache ne sert rien et le rendu est payé
deux fois comme avant — sans que rien ne rougisse. C'est
`@pytest.mark.xdist_group(<vue>)` qui l'assure, avec `--dist loadgroup` (déjà le
drapeau du Makefile). Retirer l'un ou l'autre ne casse aucun test : ça rend
seulement le gain nul, en silence.
"""

from __future__ import annotations

from collections import namedtuple
from functools import lru_cache

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


# ── LE RENDU PAYÉ UNE FOIS — 2026-09-18 ──────────────────────────────────────
#
# `test_views_render_smoke.py` et `test_a_render_opens_one_connection.py` importent le
# MÊME `SCRIPT` et la MÊME liste `VIEWS`, et rendaient les mêmes **40 vues** chacun de
# son côté : 88,6 s, soit **21,3 % de la suite**, dont 34,1 s strictement dupliquées.
# `airflow_kpi` coûtait 9,96 s d'un côté et 12,91 s de l'autre — 22,9 s pour une vue.
#
# Les deux questions posées sont différentes — « ça lève ? » et « combien de connexions
# ouvertes ? » — mais elles se répondent sur UN seul rendu : le compteur de connexions
# doit simplement être installé pendant celui-ci.
#
# ⚠️ Pourquoi les deux fichiers survivent, alors qu'une fusion serait plus simple : une
# signature du catalogue NOMME `test_a_render_opens_one_connection.py`, et
# `.claude/dev-docs/test-suite-performance.md` écarte explicitement la fusion pour cette
# raison. On partage le RENDU, pas les fichiers.
#
# ⚠️ Et sous `xdist`, un cache de processus ne se partage pas entre workers. Les deux
# tests d'une même vue doivent donc tomber dans le MÊME worker : c'est à quoi sert
# `@pytest.mark.xdist_group(view)` des deux côtés, avec `--dist loadgroup` que le
# Makefile passe déjà. Sans le marqueur, le cache ne sert qu'une fois sur deux et le
# gain disparaît sans qu'aucun test ne rougisse.
#
# ⚠️ Le cache ne retient PAS l'objet `AppTest` : seulement le message d'erreur et le
# compte. Quarante arbres de rendu en mémoire rouvriraient les OOM de `make test`
# mesurés le 2026-09-17.

_Rendu = namedtuple("_Rendu", "erreur connexions")


@lru_cache(maxsize=None)
def render_once(view: str) -> "_Rendu":
    """Rend `view` UNE fois par worker et retient ce que les deux gardes lisent.

    Rend `(erreur, connexions)` : l'erreur est le message formaté si le rendu a levé,
    `None` sinon ; `connexions` est le nombre d'appels RÉELS à `PostgresHandler._connect`
    pendant ce rendu.
    """
    import os

    from streamlit.testing.v1 import AppTest

    from src.database.postgres_handler import PostgresHandler

    compte = {"n": 0}
    original = PostgresHandler._connect

    def comptant(self, *args, **kwargs):
        compte["n"] += 1
        return original(self, *args, **kwargs)

    PostgresHandler._connect = comptant
    try:
        at = AppTest.from_string(SCRIPT.format(root=os.getcwd(), view=view))
        at.run(timeout=180)
    finally:
        PostgresHandler._connect = original

    erreur = None
    if at.exception:
        ex = at.exception[0]
        detail = getattr(ex, "value", ex)
        erreur = f"{type(detail).__name__}: {detail}"
    return _Rendu(erreur, compte["n"])


def une_vue_ouvre_vraiment_une_connexion() -> tuple[str, int]:
    """La mutation de `render_once` : l'instrument doit BOUGER sur une vraie vue.

    Un compteur branché sur rien rend 0 partout, et `0 <= 1` passe pour les 39 vues
    — le mode d'aveuglement que ce dépôt a déjà touché quatre fois. Rend la première
    vue qui ouvre au moins une connexion, avec son compte.
    """
    for vue in VIEWS:
        rendu = render_once(vue)
        if rendu.erreur is None and rendu.connexions >= 1:
            return vue, rendu.connexions
    return "", 0
