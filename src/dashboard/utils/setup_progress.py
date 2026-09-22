"""L'avancement de la configuration, pour l'en-tête de section du menu.

Type: Sub
Uses: src.dashboard.utils.project_db, setup_completion.read_setup_state
Triggers: app.render_navigation (barre latérale)
Persists in: nothing

POURQUOI UN MODULE, ET PAS TROIS LIGNES DANS `app.py` — 2026-09-22
------------------------------------------------------------------
Écrit d'abord dans `app.py`. **Deux cliquets l'ont refusé, et les deux avaient
raison :**

  * `tests/test_a_file_only_gets_shorter.py` gèle `app.py` à **997 lignes**. Le
    même cliquet avait déjà fait sortir `_neighbour_pages` vers `nav_badges.py` le
    2026-09-22 matin, pour la même raison : « ce qui entre dans ce fichier doit en
    faire sortir autant ».
  * `tests/test_a_connection_is_closed_on_every_path.py` a nommé le défaut à la
    ligne près : « `db` is opened and no try/finally closes it. Use
    `with project_db() as db:` ». Inoffensif à un utilisateur, pas au palier
    suivant — `max_connections=100` est partagé avec Airflow et l'API.

LE POURCENTAGE RÉPOND À UNE QUESTION QUE LE MENU NE POSAIT PAS
---------------------------------------------------------------
« ⚙️ Configuration de streaMLytics » porte sept entrées et aucune ne dit *combien
il m'en reste*. Le pourcentage le dit SANS ouvrir la section.

Le compte vient de `setup_completion.read_setup_state`, le lecteur unique des
étapes de mise en route — celui qu'`onboarding` et l'accueil utilisent déjà. Un
second calcul ici aurait produit deux pourcentages pour une seule question, la
classe `deux-surfaces-deux-nombres` : 30 classes au catalogue, 16,7 % de récidive,
la deuxième famille la plus douloureuse de ce dépôt.

⚠️ EN CACHE, ET L'HORIZON N'EST PAS ARBITRAIRE
-----------------------------------------------
Soixante secondes, **la même valeur qu'`auth._cached_plan_row`**, et pour deux
raisons distinctes :

  * ce code tourne dans le chemin de la barre latérale, donc à chaque rerun de
    chaque page. Sans cache il ouvrirait une connexion par rerun, et un rendu est
    plafonné à UNE (`test_a_render_opens_one_connection`, `_KNOWN_MULTI` vide —
    aucune vue n'a d'exemption) ;
  * les deux chiffres de la barre latérale — le plan et l'avancement — ne doivent
    pas pouvoir décrire deux instants différents. Un horizon commun le garantit.
"""
from __future__ import annotations

import streamlit as st


@st.cache_data(ttl=60, show_spinner=False)
def setup_pct(artist_id, user_id, plan) -> int | None:
    """Le pourcentage d'étapes faites, ou `None` quand on ne peut pas le savoir.

    ⚠️ `None` ET NON `0`. « On ne sait pas » n'est pas « rien n'est fait » : un zéro
    affiché sur une base injoignable annoncerait à un artiste qui a tout branché qu'il
    n'a rien fait. C'est la règle « une lecture qui échoue ne se déguise pas en rien à
    lire » (`.claude/rules/python.md`), appliquée à un chiffre d'en-tête. L'appelant
    n'affiche alors aucun pourcentage.
    """
    if artist_id is None:
        return None
    from src.dashboard.utils import project_db
    from src.dashboard.utils.setup_completion import read_setup_state

    try:
        with project_db() as db:
            if db is None:
                return None
            state = read_setup_state(db, artist_id, user_id, plan=plan)
    except Exception:       # noqa: BLE001 — un menu s'affiche sans son pourcentage
        return None
    if not state.total:
        return None
    return round(100 * state.done_count / state.total)
