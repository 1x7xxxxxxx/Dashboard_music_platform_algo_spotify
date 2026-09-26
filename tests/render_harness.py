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
    # Routed and rendered by nobody until 2026-09-26 — `algo_preview` was born that day
    # without a render, like the two older ones. Guard:
    # tests/test_every_routed_view_is_rendered.py
    "algo_preview", "platform_status", "privacy",
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
    "service",
    "home", "onboarding", "onboarding_health", "credentials", "account",
    "soundcloud", "youtube", "instagram", "spotify_s4a_combined", "apple_music",
    "export_csv", "export_pdf", "useful_links",
    # its empty state (no prediction yet) is the most frequent one while activation is
    # the blocker (ADR-028) — so it is rendered for a brand-new tenant too.
    "algo_preview",
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

_Rendu = namedtuple("_Rendu", "erreur connexions figures")

# ── CE QU'UNE FIGURE RENDUE DIT DE SA MISE EN PAGE — 2026-09-26 (R189) ───────
#
# Trois défauts de R188 (hauteurs inégales sur une rangée, titre tronqué, étiquettes de
# bandes superposées, légende sur la barre d'outils) ont traversé toute la suite : ils
# ne se voyaient qu'à l'écran. Le rendu `AppTest` a déjà la spec Plotly et l'arbre des
# colonnes ; on en retient des FAITS SCALAIRES par figure — jamais l'arbre, jamais la
# spec entière (la rétention de l'arbre a fait sortir la suite par l'OOM le 2026-09-17).
# Les règles vivent dans tests/test_a_rendered_figure_is_laid_out.py.
Fig = namedtuple("Fig", "row col width height title title_size annotations "
                        "legend_top legend_chars modebar")


def _x_value(x):
    """A Plotly x as a float — ISO dates to epoch seconds; None when unreadable."""
    import datetime as _dt
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return float(x)
    if isinstance(x, str):
        try:
            return _dt.datetime.fromisoformat(x.replace("Z", "+00:00")[:26]).timestamp()
        except ValueError:
            return None
    return None


def _fig_facts(spec: dict, row, col, width: float, config: str) -> "Fig":
    import json
    import re as _re
    lay = spec.get("layout", {}) or {}
    title = lay.get("title")
    size = 17
    if isinstance(title, dict):
        size = (title.get("font") or {}).get("size") or size
        title = title.get("text")
    title = _re.sub(r"<[^>]+>", "\n", title or "")
    height = lay.get("height") or 450
    margin = lay.get("margin") or {}
    mt = margin.get("t", 100)
    plot_h = max(1, height - mt - margin.get("b", 80))
    xs = [v for tr in spec.get("data", []) for v in (tr.get("x") or [])
          if isinstance(tr.get("x"), list)]
    xs = [v for v in map(_x_value, xs) if v is not None]
    lo, hi = (min(xs), max(xs)) if xs else (None, None)
    anns = []
    for a in lay.get("annotations") or []:
        xref = str(a.get("xref", "x"))
        if xref.startswith("paper") or xref.endswith("domain"):
            frac = a.get("x") if isinstance(a.get("x"), (int, float)) else None
        else:
            xv = _x_value(a.get("x"))
            frac = (xv - lo) / (hi - lo) if xv is not None and lo is not None and hi > lo else None
        anns.append((frac, f"{a.get('yref', 'y')}:{a.get('y')}", str(a.get("text") or "")))
    leg = lay.get("legend") or {}
    legend_top = None
    if leg.get("orientation") == "h" and isinstance(leg.get("y"), (int, float)) and leg["y"] > 1:
        top = mt - (leg["y"] - 1) * plot_h          # px from the figure's top edge
        legend_top = top if leg.get("yanchor", "top") != "bottom" else top - 22
    names = [str(tr.get("name") or "") for tr in spec.get("data", [])
             if tr.get("showlegend", True) is not False and tr.get("name")]
    try:
        modebar = json.loads(config or "{}").get("displayModeBar", True) is not False
    except ValueError:
        modebar = True
    return Fig(row, col, width, height, title, size, tuple(anns), legend_top,
               sum(len(n) + 6 for n in names), modebar)


def figure_facts(tree) -> tuple:
    """Every Plotly figure of a rendered tree, as `Fig` scalars. `row` is the innermost
    `st.columns` row holding it (None outside any), `width` its share of the page."""
    import json
    out, counter = [], [0]

    def walk(node, row, col, width):
        kind = getattr(node, "type", None)
        if kind == "plotly_chart":
            out.append(_fig_facts(json.loads(node.proto.spec), row, col, width,
                                  node.proto.config))
            return
        kids = list(node.children.values()) if hasattr(node, "children") else []
        if kids and all(getattr(k, "type", None) == "column" for k in kids):
            counter[0] += 1
            rid = counter[0]
            for i, k in enumerate(kids):
                walk(k, rid, i, width * (getattr(k, "weight", None) or 1 / len(kids)))
            return
        for k in kids:
            walk(k, row, col, width)

    walk(tree, None, None, 1.0)
    return tuple(out)


@lru_cache(maxsize=None)
def render_once(view: str) -> "_Rendu":
    """Rend `view` UNE fois par worker et retient ce que les deux gardes lisent.

    Rend `(erreur, connexions, figures)` : l'erreur est le message formaté si le rendu a levé,
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
    return _Rendu(erreur, compte["n"], figure_facts(at._tree))


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
