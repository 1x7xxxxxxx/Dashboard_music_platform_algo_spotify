#!/usr/bin/env python3
"""Evalue les conditions de REOUVERTURE que les taches closes se sont donnees.

Type: Utility
Uses: json, pathlib, subprocess
Triggers: make reopen-check
Depends on: .claude/dev-docs/error-class-health.json, daily_ops_metrics (optionnel)
Persists in: rien

Le defaut mesure le 2026-09-17
-------------------------------
Huit taches closes portent une « condition de reouverture, calculable » ecrite noir sur
blanc dans la roadmap. **Aucune n'etait evaluee par quoi que ce soit.**

Le cas qui l'a revele : R122 (revue des classes d'erreur) a ete close en se donnant
« rouvrir si `ever_recurred_observed` repasse au-dessus de 47 ». Mesure du 2026-09-17 :
le compteur valait **48** deja avant la seance, puis **49**. La condition etait donc
remplie, et personne ne l'a su — parce qu'ecrire un declencheur et le VERIFIER sont deux
gestes, et que seul le premier avait ete fait.

Ce n'est pas un defaut du cliquet des classes d'erreur : lui verifie que les trous ne
GRANDISSENT pas, ce qu'il fait bien. Il ne lui a jamais ete demande de dire si une tache
close doit rouvrir.

Ce que cet outil est, et ce qu'il n'est pas
--------------------------------------------
Il n'analyse PAS la prose de la roadmap. Les conditions y sont ecrites en francais, sous
huit formes differentes ; un analyseur les lirait mal et donnerait un faux calme, ce qui
serait pire que rien.

Il porte un REGISTRE explicite : une condition, une fonction qui l'evalue, et le verdict.
Une condition qu'on ne sait pas evaluer se declare `MANUELLE` et s'affiche comme telle —
jamais comme satisfaite.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
from typing import Callable, Optional

ROOT = pathlib.Path(__file__).resolve().parents[2]
HEALTH = ROOT / ".claude" / "dev-docs" / "error-class-health.json"

# ⚠️ Au niveau MODULE, pas dans `__main__`. Plusieurs évaluations importent
# `src.database.postgres_handler` ; posé seulement sous `if __name__`, l'outil démarre
# en ligne de commande et casse dès qu'on l'IMPORTE — ce que `night_run.cmd_check` fait
# désormais. Trouvé par `tests/test_a_tool_script_can_actually_start.py`.
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MET = "ROUVRIR"
NOT_MET = "en attente"
UNKNOWN = "INDÉCIDABLE"


class Trigger:
    """Une condition de reouverture, et le moyen de la trancher."""

    def __init__(self, task: str, wording: str, where: str,
                 evaluate: Optional[Callable[[], tuple[str, str]]] = None):
        self.task = task
        self.wording = wording
        self.where = where
        self.evaluate = evaluate

    def run(self) -> tuple[str, str]:
        if self.evaluate is None:
            return UNKNOWN, "aucune évaluation automatique — à trancher à la main"
        try:
            return self.evaluate()
        except Exception as exc:                                # noqa: BLE001
            # ⚠️ Une panne d'evaluation ne rend JAMAIS « en attente ». Ce serait lire
            # « rien a faire » sur un instrument muet — le defaut que ce depot a paye
            # plusieurs fois.
            return UNKNOWN, f"évaluation impossible ({type(exc).__name__}: {exc})"


def _health() -> dict:
    return json.loads(HEALTH.read_text(encoding="utf-8"))["aggregate"]


def _r122() -> tuple[str, str]:
    agg = _health()
    n = agg["population"]["ever_recurred_observed"]
    # 47 → 48 le 2026-09-25 : la condition a tiré (48, récidives du jour), personne ne
    # l'aurait vu — rien ne lançait ce script avant que le nightly ne le fasse (R170).
    # ACQUITTÉE : le travail qu'elle rouvre est la liste de `make error-debt` (R169, les
    # classes récidivées sans garde auto-prouvant d'abord). Le compteur ne fait que
    # monter : le seuil se relève à chaque acquittement, une nouvelle classe qui récidive
    # le refait tirer — c'est le signal voulu, pas du bruit.
    seuil = 48
    verdict = MET if n > seuil else NOT_MET
    return verdict, f"ever_recurred_observed = {n} (seuil : > {seuil})"


# ── LES DEUX CONDITIONS QUI PARLENT DE PRODUCTION SE MESURENT EN PRODUCTION ──
#
# ⚠️ **Mesure le 2026-09-20 : ces deux controles interrogeaient la base LOCALE.** Ils
# appelaient `from_env_or_config()`, qui depuis un poste de developpement resout
# `localhost:5433`. Les chiffres divergeaient :
#
#                      local (ce que l'outil disait)   production (la verite)
#     R116                  0 jour complet                    2
#     R131                  5 jours sur 30                    4
#
# `daily_ops_metrics` est alimentee par le DAG de production. Une condition de
# reouverture qui porte sur du TRAFIC ne peut pas se juger sur une base de
# developpement — elle y sera toujours fausse, dans un sens ou dans l'autre, et c'est
# l'outil meme dont le role est de decider quand une tache revient.
#
# Le motif correct existait deja dans ce fichier : `_r114()` passe par `PROD_SSH` et
# LEVE si la variable manque, plutot que de conclure sur rien. Ces deux-la le suivent
# desormais — un controle qui ne peut pas mesurer rend INDECIDABLE, jamais « en
# attente ». Une condition indecidable n'est pas une condition satisfaite, et elle
# n'est pas non plus une condition refusee.
def _ops_metrics_en_prod(sql: str) -> int:
    """Interroge `daily_ops_metrics` DANS la base de production. Leve sans `PROD_SSH`."""
    import os
    ssh = os.environ.get("PROD_SSH", "").strip()
    if not ssh:
        raise RuntimeError(
            "PROD_SSH non défini — ce contrôle n'a RIEN vérifié. `daily_ops_metrics` est "
            "alimentée par le DAG de PRODUCTION ; la mesurer en local rend un chiffre "
            "qui ne décrit rien. Relancer avec PROD_SSH=user@host.")
    r = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=10", ssh,
         "docker exec -i postgres_spotify_airflow psql -U postgres -d spotify_etl "
         f"-tA -c \"{sql}\""],
        capture_output=True, text=True, check=False, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"ssh/psql en échec : {(r.stderr or '').strip()[:120]}")
    valeurs = [x for x in r.stdout.split() if x.isdigit()]
    if not valeurs:
        raise RuntimeError(f"réponse illisible : {r.stdout[:80]!r}")
    return int(valeurs[-1])


def _r116() -> tuple[str, str]:
    n = _ops_metrics_en_prod(
        "SELECT count(*) FROM daily_ops_metrics WHERE complete")
    return (MET if n >= 14 else NOT_MET), f"{n} jour(s) complet(s) en PROD (seuil : 14)"


def _r131() -> tuple[str, str]:
    n = _ops_metrics_en_prod(
        "SELECT count(*) FROM daily_ops_metrics "
        "WHERE day > now() - interval '30 days'")
    return (MET if n >= 30 else NOT_MET), f"{n} jour(s) sur 30 en PROD"


def _data_quality_dag() -> tuple[str, str]:
    """Le DAG `data_quality_check`, en pause parce que sa source est muette.

    Sa condition : « le jour ou `freshness_monitor` cesse de marquer Spotify S4A comme
    `stale` ». Elle est evaluable — c'est une ligne en base — et elle ne l'etait pas.
    """
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler.from_env_or_config()
    try:
        rows = db.fetch_query(
            "SELECT count(*) FROM etl_run_log "
            "WHERE platform ILIKE %s AND started_at > now() - interval '3 days' "
            "AND status = 'success'", ("%s4a%",))
    finally:
        db.close()
    n = (rows or [[0]])[0][0]
    return (MET if n > 0 else NOT_MET), (
        f"{n} collecte(s) S4A réussie(s) sur 3 jours — la source est "
        f"{'FRAÎCHE' if n else 'toujours muette'}")


def _r114() -> tuple[str, str]:
    """Les deux declencheurs de `scale_check.sh`. Demande un acces a la prod."""
    prod = subprocess.run(
        ["bash", str(ROOT / "tools" / "scale_check.sh")],
        capture_output=True, text=True, check=False,
        env={**__import__("os").environ, "PROD_SSH": __import__("os").environ.get(
            "PROD_SSH", "")})
    if prod.returncode != 0 and "PROD_SSH" in prod.stderr:
        raise RuntimeError("PROD_SSH non défini — ce contrôle n'a RIEN vérifié")
    fired = "✅ sous le seuil" not in prod.stdout
    return (MET if fired else NOT_MET), (
        "au moins un des deux seuils franchi" if fired
        else "les deux déclencheurs sous le seuil")


def _fact_table_rows() -> tuple[str, str]:
    """« Retirer les 110 index jamais scannés » — rouvre si une table de faits > 1 M."""
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler.from_env_or_config()
    try:
        n = db.fetch_query("SELECT COALESCE(max(n_live_tup), 0) "
                           "FROM pg_stat_user_tables")[0][0]
    finally:
        db.close()
    return (MET if n > 1_000_000 else NOT_MET), f"{n:,} lignes (seuil : 1 000 000)"


def _gold_layer() -> tuple[str, str]:
    """« Construire la couche or » — rouvre si un locataire depasse 100 000 lignes."""
    from src.database.postgres_handler import PostgresHandler

    db = PostgresHandler.from_env_or_config()
    try:
        n = db.fetch_query(
            "SELECT COALESCE(max(c), 0) FROM ("
            "  SELECT count(*) c FROM s4a_song_timeline GROUP BY artist_id) x")[0][0]
    finally:
        db.close()
    return (MET if n > 100_000 else NOT_MET), f"{n:,} lignes pour le plus gros locataire"


def _pytest_third_worker() -> tuple[str, str]:
    """« Chercher un 3e worker » — rouvre si `MemAvailable` au repos depasse 7 220 Mo."""
    for line in pathlib.Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            mo = int(line.split()[1]) // 1024
            return (MET if mo > 7220 else NOT_MET), f"MemAvailable = {mo} Mo (seuil : 7 220)"
    raise RuntimeError("MemAvailable introuvable dans /proc/meminfo")


def _dashboard_ram() -> tuple[str, str]:
    """« Sortir Airflow de la boite » — rouvre si la RAM du dashboard depasse 2 Go."""
    out = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{.Name}} {{.MemUsage}}"],
        capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise RuntimeError("`docker stats` indisponible — ce contrôle n'a RIEN vérifié")
    seen: list[float] = []
    for line in out.stdout.splitlines():
        if "dashboard" not in line:
            continue
        used = line.split()[1]                      # ex. « 412.3MiB » ou « 1.2GiB »
        unit = "GiB" if used.endswith("GiB") else "MiB"
        try:
            value = float(used[: -len(unit)])
        except ValueError:
            continue
        seen.append(value * (1024 if unit == "GiB" else 1))

    # ⚠️ AUCUN conteneur dashboard trouvé n'est pas « 0 Mio ». Une première version
    # rendait 0 et donc « en attente » — un faux calme, sur une machine où le conteneur
    # n'est simplement pas levé. C'est le défaut que cet outil existe pour refuser, et
    # je l'avais réintroduit dans l'outil lui-même.
    if not seen:
        raise RuntimeError("aucun conteneur `dashboard` dans `docker stats` — "
                           "ce contrôle n'a RIEN vérifié")
    worst = max(seen)
    return (MET if worst > 2048 else NOT_MET), f"{worst:.0f} Mio (seuil : 2 048)"


TRIGGERS = [
    Trigger("R122", "rouvrir si `ever_recurred_observed` repasse au-dessus de 47",
            "archive.md:170", _r122),
    Trigger("R116", "14 jours `complete` dans `daily_ops_metrics`",
            "checklist.md:204", _r116),
    Trigger("R131", "30 jours de `daily_ops_metrics`",
            "checklist.md:432", _r131),
    Trigger("R114", "un des deux seuils de `tools/scale_check.sh`",
            "archive.md:6461", _r114),
    Trigger("data_quality", "le jour où `freshness_monitor` cesse de marquer "
            "« Spotify S4A » comme `stale`, relancer le DAG à la main",
            "archive.md:1471", _data_quality_dag),
    Trigger("index inutilisés", "une table de faits dépasse 1 M lignes",
            "checklist.md — Conditions d'attente", _fact_table_rows),
    Trigger("couche or", "un locataire dépasse 100 000 lignes sur une table de faits",
            "checklist.md — Conditions d'attente", _gold_layer),
    Trigger("3ᵉ worker", "`MemAvailable` au repos dépasse durablement 7 220 Mo",
            "checklist.md — Conditions d'attente", _pytest_third_worker),
    Trigger("Airflow hors boîte", "la RAM des conteneurs dashboard dépasse 2 Go",
            "checklist.md — Conditions d'attente", _dashboard_ram),
    Trigger("R87", "`loadtest_dashboard.py -n 12` rend un p50 > 200 ms",
            "archive.md:5146", None),
    Trigger("« DB ping »",
            "un incident où la latence de rendu est normale et Postgres en cause",
            "grafana-correspondence.md", None),
]


def main() -> int:
    only_met = "--only-met" in sys.argv
    rows = []
    for t in TRIGGERS:
        verdict, detail = t.run()
        rows.append((t, verdict, detail))

    met = [r for r in rows if r[1] == MET]
    unknown = [r for r in rows if r[1] == UNKNOWN]

    print("═" * 74)
    print("  CONDITIONS DE RÉOUVERTURE — ce que les tâches closes se sont donné")
    print("═" * 74)
    for t, verdict, detail in rows:
        if only_met and verdict != MET:
            continue
        mark = {MET: "🔴", NOT_MET: "  ", UNKNOWN: "❔"}[verdict]
        print(f"{mark} {t.task:12} {verdict:12} {detail}")
        print(f"     « {t.wording} »  —  {t.where}")
    print("─" * 74)
    print(f"  {len(met)} à ROUVRIR · {len(rows) - len(met) - len(unknown)} en attente · "
          f"{len(unknown)} indécidable(s) ici")
    if unknown:
        print("  ⚠️ Une condition indécidable n'est PAS une condition satisfaite.")
    return 1 if met else 0


if __name__ == "__main__":
    raise SystemExit(main())
