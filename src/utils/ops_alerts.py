"""Ce qui a alerte dans les 24 dernieres heures, lu chez Prometheus.

Type: Utility
Uses: requests (API Prometheus)
Triggers: la tache `check_ops_alerts` du DAG `alert_monitor` (23 h UTC)
Persists in: rien — la source de verite est Prometheus, et le mail du soir

Pourquoi ce module existe plutot qu'un Alertmanager
---------------------------------------------------
ADR-026 ecarte Alertmanager avec un declencheur ecrit : « plus de ~10 regles, ou un
besoin d'astreinte ». Nous en avons quatre et personne n'est d'astreinte. En ajouter un
serait un quatrieme conteneur, un second canal, et surtout un SECOND endroit d'ou part
un mail — alors qu'ADR-011 tient justement parce qu'il n'y en a qu'un, consolide, une
fois par nuit.

Les regles vivent donc dans `deploy/prometheus/rules/streamlytics.yml`, Prometheus les
evalue toutes les 30 s, et ce module vient lire le resultat.

Le piege qu'il evite, et c'est tout son interet
------------------------------------------------
Lire l'etat INSTANTANE (`ALERTS{alertstate="firing"}`) a 23 h ne montre que les pannes
qui durent ENCORE a 23 h. Une pointe de latence de 14 h a 15 h, exactement le genre
d'evenement pour lequel on a pose une regle a fenetre, serait invisible. On interroge
donc `max_over_time(ALERTS{alertstate="firing"}[24h])`, qui rend 1 des lors que l'alerte
a ete active a un moment de la journee — et on dit separement si elle l'est encore.

Les annotations ne sont PAS dans la serie
------------------------------------------
`ALERTS` ne porte que des LABELS. Le symptome et le geste, qui sont l'exigence
d'ADR-011, vivent dans les `annotations` de la regle et ne se lisent que par
`/api/v1/rules`. Ce module fait donc deux appels et les rapproche par `alertname` —
sans quoi le mail dirait qu'une alerte a sonne sans jamais dire quoi faire, ce qui est
exactement l'alerte qu'ADR-011 interdit.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://streamlytics_prometheus:9090")
_TIMEOUT_S = 15

# Les deux annotations qu'ADR-011 rend obligatoires. Une regle qui n'a pas les deux ne
# doit pas exister ; `tests/test_an_alert_rule_names_a_symptom_and_an_action.py` le
# tient cote fichier, et ce module le re-constate cote SERVEUR — parce qu'un fichier
# corrige au depot et jamais remonte a Prometheus est une divergence que ce depot a
# deja payee sur le Caddyfile.
_REQUIRED_ANNOTATIONS = ("symptom", "action")


def _get(path: str, params: dict | None = None):
    """Une reponse JSON de Prometheus, ou None. Ne leve jamais."""
    try:
        import requests

        r = requests.get(f"{PROMETHEUS_URL}{path}", params=params or {},
                         timeout=_TIMEOUT_S)
        r.raise_for_status()
        payload = r.json()
        if payload.get("status") != "success":
            logger.warning("Prometheus %s : status=%s", path, payload.get("status"))
            return None
        return payload.get("data")
    except Exception as exc:  # noqa: BLE001 — Prometheus absent n'est pas une panne produit
        logger.warning("Prometheus injoignable sur %s (%s)", path, type(exc).__name__)
        return None


def _rule_annotations() -> dict[str, dict]:
    """{alertname: annotations}. Dictionnaire vide si les regles sont illisibles."""
    data = _get("/api/v1/rules")
    if not data:
        return {}
    out: dict[str, dict] = {}
    for group in data.get("groups") or []:
        for rule in group.get("rules") or []:
            if rule.get("type") != "alerting":
                continue
            out[rule["name"]] = dict(rule.get("annotations") or {})
    return out


def _fired_names(window: str = "24h") -> dict[str, dict]:
    """{alertname: labels} des alertes actives a un moment de la fenetre."""
    data = _get("/api/v1/query",
                {"query": f'max_over_time(ALERTS{{alertstate="firing"}}[{window}])'})
    if not data:
        return {}
    out: dict[str, dict] = {}
    for row in data.get("result") or []:
        labels = dict(row.get("metric") or {})
        name = labels.get("alertname")
        if name:
            out[name] = labels
    return out


def _still_firing() -> set[str]:
    data = _get("/api/v1/query", {"query": 'ALERTS{alertstate="firing"}'})
    if not data:
        return set()
    return {(row.get("metric") or {}).get("alertname")
            for row in data.get("result") or []} - {None}


def fired_since(window: str = "24h") -> list[dict]:
    """Les alertes de la fenetre, chacune avec son symptome et son geste.

    Rend UNE entree `UNAVAILABLE` quand Prometheus ne repond pas. C'est deliberе et
    c'est le meme contrat que les autres detecteurs du DAG : une liste vide se lit
    « tout va bien », et un instrument muet ne doit jamais se lire ainsi. Ce depot a
    paye cette classe assez souvent pour la nommer — `a-crashing-check-empties-its-
    section-silently`.
    """
    annotations = _rule_annotations()
    if not annotations:
        return [{
            "alertname": "UNAVAILABLE",
            "severity": "high",
            "still_firing": True,
            "symptom": "La surveillance elle-meme est muette : Prometheus n'a pas rendu "
                       "ses regles. Rien de ce qui suit sur la sante du VPS, la latence "
                       "de rendu ou le pool n'a ete verifie cette nuit.",
            "action": "Sur la machine — `docker compose --profile observability ps` puis "
                      "`docker logs streamlytics_prometheus --tail 50`. Tunnel pour "
                      "regarder : `ssh -N -L 3000:127.0.0.1:3000 root@167.233.92.1`.",
            "panel": "—",
        }]

    fired = _fired_names(window)
    live = _still_firing()
    out: list[dict] = []
    for name, labels in sorted(fired.items()):
        ann = annotations.get(name)
        # DEUX absences distinctes, et les confondre accuse a tort. Une regle PRESENTE
        # sans `action` est un defaut de REDACTION, a corriger dans le fichier. Une
        # regle ABSENTE de Prometheus a simplement ete retiree ou renommee depuis
        # qu'elle a sonne — la serie `ALERTS` la garde pourtant 24 h de plus.
        #
        # Le cas est reel, pas theorique : la verification de bout en bout du
        # 2026-09-16 a pose une regle `SelfTestAlwaysFiring`, l'a vue sonner, puis l'a
        # retiree — et elle est restee dans la fenetre jusqu'au lendemain. La premiere
        # redaction l'aurait accusee d'etre « hors contrat ADR-011 », c'est-a-dire
        # envoye corriger un fichier ou il n'y a rien a corriger.
        if ann is None:
            out.append({
                "alertname": name,
                "severity": labels.get("severity", "?"),
                "still_firing": name in live,
                "symptom": "A sonne dans les dernieres 24 h, puis sa regle a disparu de "
                           f"Prometheus. `{name}` a ete retiree, renommee, ou le fichier "
                           "de regles a ete recharge entre-temps.",
                "action": "Rien a corriger dans les regles actuelles. Si ce nom ne dit "
                          "rien, regarder l'historique de `deploy/prometheus/rules/` : "
                          "la ligne disparaitra d'elle-meme en sortant de la fenetre de "
                          "24 h.",
                "panel": "—",
            })
            continue
        missing = [k for k in _REQUIRED_ANNOTATIONS if not ann.get(k)]
        if missing:
            # On ne tait pas la regle : on dit qu'elle est hors contrat. La taire
            # reviendrait a faire disparaitre une alerte reelle pour un defaut de
            # redaction.
            logger.error("regle %s sans annotation(s) %s — ADR-011", name, missing)
        out.append({
            "alertname": name,
            "severity": labels.get("severity", "?"),
            "still_firing": name in live,
            "symptom": ann.get("symptom")
            or f"⚠️ regle `{name}` sans `symptom` — hors contrat ADR-011.",
            "action": ann.get("action")
            or f"⚠️ regle `{name}` sans `action` — hors contrat ADR-011. "
               "L'ecrire dans `deploy/prometheus/rules/streamlytics.yml`.",
            "panel": ann.get("panel", "—"),
        })
    return out


def collect() -> list[dict]:
    """Ce que la tache du DAG appelle. Ne leve jamais, et ne rend jamais [] en panne.

    Le corps vit ICI et pas dans `alert_monitor.py` pour la meme raison que
    `metrics_seam` ne vit pas dans `app.py` : le DAG porte un cliquet de longueur qui ne
    monte jamais (`tests/test_a_file_only_gets_shorter.py`), et il fait deja 2 700
    lignes. Ce qui releve des metriques appartient a ce module ; ce qui releve de
    l'ordonnancement reste la-bas.
    """
    try:
        return fired_since("24h")
    except Exception as exc:  # noqa: BLE001 — meme contrat que les autres controles
        logger.error("lecture des alertes d'infrastructure impossible : %s",
                     type(exc).__name__)
        return [{
            "alertname": "UNAVAILABLE", "severity": "high", "still_firing": True,
            "symptom": f"Le lecteur d'alertes a leve ({type(exc).__name__}). La sante du "
                       "VPS, la latence de rendu et le pool n'ont PAS ete verifies cette "
                       "nuit.",
            "action": "Lire la trace de la tache `check_ops_alerts` dans Airflow.",
            "panel": "—",
        }]


_TD = 'style="padding:6px 12px;border-bottom:1px solid #eee"'


def render_html(rows: list[dict]) -> str:
    """La section « Infrastructure » du mail du soir.

    Elle vient EN TETE du corps, avant les detecteurs de donnees : quand le VPS manque de
    RAM ou que le pool est vide, la moitie des constats qui suivent sont des
    CONSEQUENCES, et les lire d'abord envoie reparer au mauvais endroit. Ce depot a paye
    exactement cela — une alerte qui accusait une plateforme qui marchait.

    Les trois colonnes sont l'exigence d'ADR-011 rendue visible : la regle, ce que
    l'artiste voit, et le geste de ce soir.
    """
    body = ""
    for o in rows:
        etat = "🔴 en cours" if o.get("still_firing") else "🟠 resolue depuis"
        body += (
            f'<tr><td {_TD} style="vertical-align:top"><b>{o["alertname"]}</b><br>'
            f'<span style="color:#777">{o["severity"]} · {etat}</span></td>'
            f'<td {_TD}>{o["symptom"]}</td>'
            f'<td {_TD}>{o["action"]}<br>'
            f'<span style="color:#777;font-size:0.85em">{o.get("panel", "—")}</span>'
            f'</td></tr>')
    return (
        '<h3 style="color:#b00">🖥️ Infrastructure — ce qui a alerté sur 24 h</h3>'
        '<table style="border-collapse:collapse;font-size:0.9em">'
        '<tr><th style="text-align:left;padding:6px 12px">Règle</th>'
        '<th style="text-align:left;padding:6px 12px">Ce que l\'artiste voit</th>'
        '<th style="text-align:left;padding:6px 12px">Le geste de ce soir</th></tr>'
        f'{body}</table>'
        '<p style="color:#555;font-size:0.85em">Les courbes : '
        '<code>ssh -N -L 3000:127.0.0.1:3000 root@167.233.92.1</code> puis '
        '<code>http://localhost:3000</code>. Les seuils vivent dans '
        '<code>deploy/prometheus/rules/streamlytics.yml</code>.</p>')
