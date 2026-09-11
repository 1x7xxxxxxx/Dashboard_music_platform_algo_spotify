"""Launch this tenant's collections — one rule, several buttons.

Type: Utility
Uses: airflow_trigger, collection_progress, safe_error
Triggers: the sidebar panel, the home setup step
Depends on: COLLECTION_DAGS
Persists in: nothing (Airflow runs + session state for the progress panel)

Extracted from `app.show_data_collection_panel` on 2026-09-04, when the home page's
fourth setup step needed to launch a collection itself. The step NAMED the action and
sent the artist to the sidebar to perform it — an instruction is what you write when
the button is somewhere else.

Everything that matters lives here because it is easy to get wrong in a second copy:

* **every trigger carries `conf={'artist_id': …}`**. Without it the collectors run
  fleet-wide, and the CSV watchers default to `artist_id = 1` — i.e. straight into the
  ADMIN's tenant, which is the leak two beta sessions were spent on;
* **a refusal says WHY**. A bare ❌ is what made « toutes les credentials ont échoué »
  impossible to act on during a live session;
* **`safe_error`, never `{e}`**: `trigger_dag` talks to Airflow's REST API with
  credentials, and this message is rendered TO THE ARTIST.
"""
from __future__ import annotations

from typing import Optional


def trigger_all_collections(artist_id: Optional[int], airflow_trigger,
                            collection_dags) -> tuple[dict, dict]:
    """Fire every collection DAG for ONE tenant. Returns (launched, not_launched)."""
    from src.utils.safe_error import safe_error

    launched: dict[str, str] = {}
    not_launched: dict[str, str] = {}
    for dag_id, _label in collection_dags:
        try:
            conf = {'artist_id': artist_id} if artist_id is not None else {}
            result = airflow_trigger.trigger_dag(dag_id, conf=conf)
            if result.get('success'):
                # The cached "latest run per DAG" is stale the instant a run starts.
                from src.dashboard.utils.airflow_monitor import cached_last_run_per_dag
                cached_last_run_per_dag.clear()
                # Et les compteurs eux-mêmes : c'est l'unique moment de la journée
                # où ils changent, donc celui qui autorise leur cache long.
                from src.dashboard.utils.kpi_helpers import clear_kpi_caches
                clear_kpi_caches()
                if result.get('dag_run_id'):
                    launched[dag_id] = result['dag_run_id']
            else:
                not_launched[dag_id] = str(
                    result.get('error', result.get('message', '')) or '')
        except Exception as e:      # noqa: BLE001 — a refusal must still be reported
            not_launched[dag_id] = safe_error(e)
    return launched, not_launched


# ── Le démarrage AUTOMATIQUE, quand le parcours vient d'être bouclé ──────────
#
# Demandé le 2026-09-06 : « créer l'automatisation de lancer la collecte dès que le
# parcours d'import CSV + API credentials est validé ». Jusque-là l'artiste finissait
# de tout saisir et rien ne partait : il fallait qu'il trouve, dans la barre latérale,
# un bouton qu'il n'avait aucune raison de chercher — et la quatrième étape de sa mise
# en route restait ⬜ jusqu'à ce qu'il le fasse.
#
# L'IDEMPOTENCE EST DÉRIVÉE, PAS STOCKÉE, et c'est le cœur de la conception.
# On ne démarre que si `etl_run_log` ne porte AUCUN run réussi pour ce locataire —
# c'est exactement le compteur `has_runs` que le parcours utilise déjà pour sa
# quatrième étape. Conséquences :
#
#   * une fois la première collecte enregistrée, la condition est fausse pour
#     toujours : on ne peut pas relancer en boucle ;
#   * aucune migration, aucune colonne de plus, et surtout aucune SECONDE source de
#     vérité — un drapeau `auto_started` en base pourrait diverger de la réalité des
#     runs, ce compteur non ;
#   * un artiste qui purge ses données repart d'un parcours neuf, ce qui est le
#     comportement juste.
#
# Le drapeau de session ne remplace pas cette condition, il la complète : Streamlit
# ré-exécute le script à chaque interaction, et deux reruns rapprochés pourraient
# tous deux lire `has_runs = 0` avant que le premier run ne soit journalisé.

_AUTOSTART_SESSION_KEY = "_collection_autostarted_for"


def should_autostart(state) -> bool:
    """Le parcours est-il bouclé SAUF la collecte ?

    Pure — pas de base, pas de Streamlit — pour que le garde puisse l'interroger sans
    monter une session. `state` est un `SetupState` de `setup_completion`.

    « Bouclé » veut dire : tout ce que l'ARTISTE devait faire est fait, et la seule
    étape qui reste est celle que la machine fait pour lui. On ne demande pas que
    TOUTES les étapes soient vraies — la dernière est précisément celle qu'on
    déclenche.
    """
    steps = list(getattr(state, "steps", []) or [])
    if not steps:
        return False        # lecture impossible : on ne pousse personne
    by_key = {s.key: s.done for s in steps}
    # `collected` remplace l'ancienne étape « run », retirée de l'affichage le
    # 2026-09-11 : l'artiste ne lance plus rien à la main, la collecte part seule ici
    # et repart chaque matin par cron. Le FAIT reste lu, et il doit l'être — sans lui
    # une collecte repartirait à chaque enregistrement d'identifiant.
    if getattr(state, "collected", False):
        return False        # une collecte a déjà réussi : plus rien à démarrer
    # Les étapes de l'artiste. `apple` n'en fait PAS partie : l'import Apple Music est
    # facultatif — beaucoup d'artistes n'ont pas de compte Apple for Artists, et
    # l'exiger laisserait leur collecte à l'arrêt indéfiniment.
    return bool(by_key.get("creds")) and bool(by_key.get("s4a"))


def autostart_if_journey_complete(db, artist_id, session_state,
                                  airflow_trigger, collection_dags) -> tuple:
    """Démarre la collecte UNE fois, quand le parcours vient d'être bouclé.

    Retourne `(launched, not_launched)` comme `trigger_all_collections`, ou
    `({}, {})` quand il n'y avait rien à faire — ce qui est le cas le plus fréquent
    et doit rester silencieux : cette fonction est appelée à chaque enregistrement.
    """
    if db is None or artist_id is None:
        return {}, {}
    if session_state.get(_AUTOSTART_SESSION_KEY) == artist_id:
        return {}, {}       # déjà lancé dans cette session, avant journalisation
    try:
        from src.dashboard.utils.setup_completion import read_setup_state
        state = read_setup_state(db, artist_id)
    except Exception:       # noqa: BLE001 — une lecture ratée ne pousse personne
        return {}, {}
    if not should_autostart(state):
        return {}, {}
    session_state[_AUTOSTART_SESSION_KEY] = artist_id
    return trigger_all_collections(artist_id, airflow_trigger, collection_dags)
