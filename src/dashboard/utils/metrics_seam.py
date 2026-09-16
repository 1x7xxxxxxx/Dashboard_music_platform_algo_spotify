"""La couture entre le rendu Streamlit et les métriques.

Type: Utility
Uses: src.utils.metrics, src.database.postgres_handler
Triggers: `src/dashboard/app.py` au seuil et à la fin de chaque rerun
Persists in: nothing

Pourquoi ce module et pas dix lignes dans `app.py`
---------------------------------------------------
`src/dashboard/app.py` porte un cliquet de longueur qui ne monte jamais
(`tests/test_a_file_only_gets_shorter.py`). Ce n'est pas une contrainte de style : c'est
déjà le fichier le plus lu du produit, et chaque sujet qu'on y ajoute est un sujet qu'on
ne peut plus tester seul. La couture vit donc ici, où elle s'appelle sans Streamlit ;
`app.py` ne porte que trois appels.

Ce que la couture mesure, et pourquoi en DEUX temps
----------------------------------------------------
La phase `chrome` ne peut pas être un gestionnaire de contexte : elle commence à la
première ligne du script et s'arrête quand la vue démarre, avec des `st.stop()`
possibles au milieu — et `st.stop()` lève `StopException`, qu'un `with` ne survivrait
pas proprement. Un chronomètre posé en haut et lu en bas, si.

La phase `view`, elle, enveloppe un bloc : c'est un contexte ordinaire.
"""
from __future__ import annotations

import time

# L'instant d'entrée dans le rerun courant. Une LISTE et non une variable de module
# parce que le script est ré-exécuté à chaque rerun : une case qu'on écrase se lit mieux
# qu'un `global`. Déclaré dans le registre des états de processus
# (`tests/test_process_state_is_declared_for_a_second_instance.py`) : per-instance et
# même per-rerun, il n'y a rien à partager entre deux instances.
_CHROME_T0 = [0.0]


def start_rerun() -> None:
    """Pose le chronomètre du rerun et expose les métriques. Ne lève jamais.

    `start_metrics_server()` est idempotent : Streamlit ré-exécute ce script à chaque
    rerun, et sans son drapeau de module chaque rerun retenterait une liaison de port
    et journaliserait un avertissement.
    """
    _CHROME_T0[0] = time.perf_counter()
    try:
        from src.utils.metrics import start_metrics_server

        start_metrics_server()
    except Exception:  # noqa: BLE001 — l'observabilité ne casse pas le produit
        pass


def end_chrome(page: str) -> None:
    """Clôt la phase CHROME et publie l'état du pool. Ne lève jamais.

    ⚠️ C'est la correction d'un angle mort, pas une métrique de plus : le chronomètre
    historique d'`app.py` ne mesure que `_render_page` et EXCLUT tout ce qui précède.

    Ce docstring a longtemps affirmé que la partie exclue pesait « un facteur 8 » de
    plus que la vue. C'était faux, et c'est cette couture qui l'a montré : côté SERVEUR
    le 2026-09-16, sur 8 pages, la chrome est plate à 11-13 ms et la vue va de 50 à
    777 ms. Le chiffre venait d'une soustraction jamais faite — `468-538 ms` est mesuré
    sous `AppTest`, dont le plancher pour `st.write('hello')` vaut 352 ms dans le même
    conteneur (`tools/loadtest_dashboard.py:30-33`). Ce qu'on prenait pour la barre
    latérale était le harnais.

    L'angle mort reste réel : une seule des deux phases était mesurée. Ce qui a changé,
    c'est laquelle pèse — et donc où va le travail de performance (R118 avant R120).

    L'état du pool est publié ICI parce que c'est le seul instant où le nombre de
    connexions empruntées veut dire quelque chose : la chrome vient d'en ouvrir et de
    les rendre.
    """
    try:
        from src.database.postgres_handler import publish_pool_metrics
        from src.utils.metrics import observe_chrome

        observe_chrome(page, time.perf_counter() - _CHROME_T0[0])
        publish_pool_metrics()
    except Exception:  # noqa: BLE001
        pass


def view_timer(page: str):
    """Le contexte qui chronomètre la VUE. Rend un contexte neutre en cas d'échec."""
    try:
        from src.utils.metrics import timed_rerun

        return timed_rerun(page, phase="view")
    except Exception:  # noqa: BLE001
        from contextlib import nullcontext

        return nullcontext()


# ⚠️ `record_session_render()` a ete RETIREE le 2026-09-16, en meme temps que la vue
# `perf_monitor` (R115 etape 6). Elle remplissait `st.session_state["_perf_log"]`, que
# cette vue etait la SEULE a lire — son propre docstring disait qu'elle ne survivrait pas
# a la suppression, et le dire ne suffit pas a l'enlever.
#
# Ce depot a une classe pour ce qui restait sinon : `du-code-mort-qui-cache-une-
# consequence-vivante`. `purge_expired()` a vecu des mois dans une `show()` que rien
# n'atteignait, et plus rien ne purgeait pendant ce temps. Une fonction sans lecteur
# n'est pas neutre : elle se fait lire comme une garantie.
#
# Ce qu'elle mesurait vit dans l'histogramme Prometheus, qui le fait mieux : toutes les
# sessions, les DEUX phases, et interrogeable apres coup.
