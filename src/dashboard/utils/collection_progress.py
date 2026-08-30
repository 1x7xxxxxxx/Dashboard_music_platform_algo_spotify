"""What happened to the collection the artist just launched.

Type: Utility
Uses: airflow_monitor (get_task_instances / get_task_log), session_state
Depends on: nothing at import time
Persists in: st.session_state['_collection_runs'] — {dag_id: run_id} for this session

The sidebar button said "Lancé !" and stopped there: no run id kept, nothing
polled, no result. An artist pressed it, waited, saw an empty dashboard and
concluded the app was broken — which is what both beta testers did. The polling
primitives existed (`airflow_monitor.get_task_instances`, `get_task_log`); they
were simply never wired to the trigger.

Pure functions here (`summarise`, `failure_hint`) so the reading of a run's state
is testable without Streamlit or Airflow.
"""
from __future__ import annotations

RUNS_KEY = "_collection_runs"
# Ce qui n'a même pas démarré. Séparé de RUNS_KEY parce qu'il n'y a PAS de run à
# interroger : un déclenchement refusé n'a pas d'identifiant de run, donc aucune
# tâche à lire. C'était dit dans une `st.status` qui se referme, puis nulle part.
NOT_LAUNCHED_KEY = "_collection_not_launched"

_TERMINAL_OK = {"success"}
_TERMINAL_KO = {"failed", "upstream_failed"}

# What a failure means in the artist's terms. Matched against the task log, most
# specific first — each line is a failure actually seen in production.
_HINTS = (
    ("playlistNotFound", "la chaîne YouTube est introuvable ou vide — si ta musique "
                         "est distribuée, cherche ta chaîne « … - Topic »"),
    ("Object does not exist", "ton compte publicitaire Meta n'est pas partagé avec "
                              "l'app de la plateforme (asset sharing)"),
    ("code-190", "le token Meta de la plateforme est expiré — action administrateur"),
    ("Permission denied", "problème de droits sur le serveur — action administrateur"),
    ("no unique or exclusion constraint",
     "incohérence de schéma côté serveur — action administrateur"),
    ("quotaExceeded", "quota d'API atteint pour aujourd'hui — réessaie demain"),
    ("401", "identifiants refusés par la plateforme — vérifie ta connexion"),
    ("404", "l'identifiant fourni est introuvable côté plateforme"),
)


def summarise(task_states: list[str]) -> str:
    """One state for a run, from its tasks. 'running' | 'success' | 'failed' | 'unknown'.

    A run is only a success when every task ended well; one failed task makes the
    run failed, whatever the others did — the artist cares about the outcome, not
    about which of the four tasks reached it.
    """
    states = [s for s in task_states if s]
    if not states:
        return "unknown"
    if any(s in _TERMINAL_KO for s in states):
        return "failed"
    if all(s in _TERMINAL_OK for s in states):
        return "success"
    return "running"


def failure_hint(log_text: str) -> str | None:
    """Translate a task log into the artist's next action, or None if unrecognised.

    Returning None is deliberate: inventing an explanation for an unknown error is
    how "toutes les credentials ont échoué" became the only thing anyone could say.
    """
    if not log_text:
        return None
    for needle, hint in _HINTS:
        if needle.lower() in log_text.lower():
            return hint
    return None


def remember_runs(runs: dict[str, str]) -> None:
    """Keep {dag_id: run_id} so a later rerun can report on them."""
    import streamlit as st

    if runs:
        st.session_state[RUNS_KEY] = runs


def remember_not_launched(failures: dict[str, str]) -> None:
    """Keep {dag_id: reason} for collections that never started.

    Écrit à chaque clic, y compris vide : sans l'effacement, une plateforme réparée
    resterait affichée en échec jusqu'à la fin de la session.
    """
    import streamlit as st

    st.session_state[NOT_LAUNCHED_KEY] = failures or {}


def render_progress(monitor, labels: dict[str, str]) -> None:
    """Show the state of the runs launched in this session. Safe to call every rerun."""
    import streamlit as st

    from src.dashboard.utils.i18n import t

    runs = st.session_state.get(RUNS_KEY) or {}
    not_launched = st.session_state.get(NOT_LAUNCHED_KEY) or {}
    if not runs and not not_launched:
        return

    st.sidebar.markdown(t("app.collection_progress", "**Collecte en cours**"))

    # D'abord ce qui n'a pas démarré : c'est la seule ligne qui appelle un geste.
    for dag_id, reason in not_launched.items():
        st.sidebar.write(f"❌ {labels.get(dag_id, dag_id)}")
        if reason:
            st.sidebar.caption(reason)

    for dag_id, run_id in runs.items():
        label = labels.get(dag_id, dag_id)
        tasks = monitor.get_task_instances(dag_id, run_id) if monitor else []
        state = summarise([task.get("state") for task in tasks])

        if state == "success":
            st.sidebar.write(f"✅ {label}")
        elif state == "running":
            st.sidebar.write(f"🔄 {label}")
        elif state == "unknown":
            st.sidebar.write(f"⏳ {label}")
        else:
            failed = next((task for task in tasks
                           if task.get("state") in _TERMINAL_KO), None)
            hint = None
            if failed and monitor:
                hint = failure_hint(monitor.get_task_log(
                    dag_id, run_id, failed["task_id"], failed.get("try_number", 1)))
            st.sidebar.write(f"❌ {label}" + (f" — {hint}" if hint else ""))
            if not hint:
                # Le texte renvoyait vers « 📊 Airflow KPI », qui est dans
                # `_ADMIN_ONLY` : l'artiste à qui on le disait ne pouvait pas y
                # aller. Un cul-de-sac, pas une aide.
                st.sidebar.caption(t(
                    "app.collection_failed_unknown",
                    "Nous n'avons pas su interpréter cette erreur. Réessaie ; "
                    "si elle revient, contacte l'administrateur."))

    if st.sidebar.button(t("app.collection_refresh", "🔄 Rafraîchir l'état"),
                         key="_collection_refresh"):
        st.rerun()
