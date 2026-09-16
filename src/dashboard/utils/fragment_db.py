"""La connexion d'un `@st.fragment`, qui dépend de COMMENT il est exécuté.

Type: Utility
Uses: streamlit, src.dashboard.utils.project_db
Triggers: tout `@st.fragment` d'une vue qui interroge la base
Persists in: nothing (st.session_state, le temps d'un rendu)

Le problème, en une phrase
--------------------------
Un `@st.fragment` s'exécute de DEUX façons, et elles n'ont pas la même connexion
disponible :

* **dans un rendu complet** — la vue a ouvert la sienne quelques lignes plus haut et la
  fermera dans son `finally`. Elle est vivante, et en ouvrir une seconde coûte une
  poignée de main SCRAM pour rien (p50 mesuré : **13 ms**, dont ~8,5 de poignée) ;
* **seul, après un mouvement de filtre** — des minutes plus tard. La connexion de la vue
  n'existe plus. La réutiliser ne lève même pas : `PostgresHandler._ensure_connection()`
  la ré-emprunte au pool **et personne ne la rend**. Une fuite par session, sur
  `maxconn=10`, avec un journal qui dit « connexion perdue » alors qu'on l'avait fermée
  exprès.

Pourquoi ce module existe plutôt que la règle simple
------------------------------------------------------
La règle simple — « un fragment ouvre toujours la sienne » — est correcte et **coûte**.
Mesuré le 2026-09-16 par `tests/test_a_render_opens_one_connection.py`, qui compte les
connexions d'un rendu RÉEL : cinq vues sont passées au-dessus de leur plafond, et
`revenue_forecast` à **4 connexions au lieu d'une** — trois fragments plus la page.
C'est ~39 ms ajoutés à chaque rendu complet pour économiser un rerun complet sur les
mouvements de filtre. Un troc non mesuré, dans le mauvais sens pour le premier rendu.

⚠️ Ce cliquet-là est celui qui dit la vérité. Un second, `test_view_connection_budget.py`,
compte les `get_db_connection()` écrits dans le FICHIER — je lui avais appris à ignorer
les corps de fragment, ce qui l'a rendu vert sur un défaut bien réel. **Une exemption
accordée au garde le plus facile à contenter n'est pas une exemption.**

Comment on sait dans quel cas on est
--------------------------------------
Streamlit n'a pas d'API publique pour « suis-je un rerun de fragment ». Mais la
distinction est observable sans elle : lors d'un rerun de fragment, **le script de la
page ne s'exécute pas**. Une vue qui dépose sa connexion vivante dans
`st.session_state` au début de son rendu, et la retire dans son `finally`, décrit donc
exactement l'état recherché — présente pendant le rendu complet, absente après.

`st.session_state` et pas une variable de module : un module est partagé par TOUTES les
sessions du processus, et une connexion qui traverserait de l'une à l'autre serait un
défaut de locataire, pas une optimisation.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

_SLOT = "_live_page_db"
_TENANT = "_live_page_tenant"


@contextmanager
def page_db_scope(db, artist_id=None) -> Iterator[None]:
    """Déclare la connexion vivante de la page ET son locataire, le temps du rendu.

    À poser dans `show()`, AUTOUR du rendu et à l'intérieur du `try` qui possède `db` —
    la fente doit être libérée avant `db.close()`, jamais après.

    ⚠️ `artist_id` voyage avec la connexion, et ce n'est pas un confort : un fragment qui
    résoudrait le locataire lui-même par `get_artist_id()` réintroduirait la forme
    manuelle que la règle transverse #7 interdit, avec son repli admin à écrire une
    deuxième fois. Il HÉRITE de celui que la page a déjà résolu — une seule résolution,
    un seul endroit où elle peut être fausse.
    """
    import streamlit as st

    try:
        st.session_state[_SLOT] = db
        st.session_state[_TENANT] = artist_id
    except Exception:          # noqa: BLE001 — hors contexte Streamlit (tests headless)
        yield
        return
    try:
        yield
    finally:
        for key in (_SLOT, _TENANT):
            try:
                st.session_state.pop(key, None)
            except Exception:  # noqa: BLE001
                pass


@contextmanager
def fragment_db() -> Iterator[tuple]:
    """`(db, artist_id)` pour un fragment. Réutilise, ou rouvre une session complète.

    Rend la connexion vivante de la page quand le fragment s'exécute à l'intérieur d'un
    rendu complet — sans rien ouvrir ni fermer, puisqu'il ne la possède pas. Sinon, il
    rouvre par `view_session()`, qui ferme par construction **et** résout le locataire
    avec le garde de la règle #7.
    """
    import streamlit as st

    from src.dashboard.utils import view_session

    try:
        live = st.session_state.get(_SLOT)
        tenant = st.session_state.get(_TENANT)
    except Exception:          # noqa: BLE001
        live, tenant = None, None

    if live is not None:
        # On NE FERME PAS : la page la possède et la fermera dans son `finally`.
        yield live, tenant
        return

    with view_session() as (db, artist_id):
        yield db, artist_id


def declare_page_db(db, artist_id=None) -> None:
    """La même déclaration que `page_db_scope`, en deux appels au lieu d'un `with`.

    Elle existe pour une raison de FORME, pas de fonction : beaucoup de `show()` ont déjà
    un `try/finally` qui possède la connexion, et y glisser un gestionnaire de contexte
    obligerait à réindenter tout le corps du rendu. Un diff qui déplace cent lignes pour
    en ajouter une est un diff que personne ne relit — et c'est ainsi qu'une erreur passe.

    À appeler juste avant le `try`, et à libérer dans le `finally` **avant** `db.close()`.
    """
    import streamlit as st

    try:
        st.session_state[_SLOT] = db
        st.session_state[_TENANT] = artist_id
    except Exception:          # noqa: BLE001 — hors contexte Streamlit (tests headless)
        pass


def release_page_db() -> None:
    """Libère la fente. **Avant** `db.close()**, jamais après.

    L'ordre n'est pas cosmétique : entre la fermeture et la libération, un fragment qui
    s'exécuterait verrait une connexion fermée dans la fente et la réutiliserait — très
    exactement le défaut que tout ce module existe pour rendre impossible.
    """
    import streamlit as st

    for key in (_SLOT, _TENANT):
        try:
            st.session_state.pop(key, None)
        except Exception:      # noqa: BLE001
            pass
