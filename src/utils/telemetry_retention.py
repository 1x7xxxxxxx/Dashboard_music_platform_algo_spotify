"""Applique les retentions que la BASE declare, au lieu de les redeclarer ici.

Type: Utility
Uses: PostgresHandler
Triggers: src/utils/nightly_maintenance.py
Depends on: les COMMENT ON TABLE poses par la migration 124
Persists in: supprime des lignes des tables de telemetrie

Le defaut que ce module ferme
------------------------------
La migration 124 (2026-09-16) declare les retentions de 13 tables de telemetrie dans des
`COMMENT ON TABLE`, et affirme que « les purges correspondantes vivent dans
`src/utils/telemetry_retention.py` ». Mesure du 2026-09-17 : **ce fichier n'existait
pas**. Les retentions etaient donc declarees en commentaire SQL et appliquees par
personne — exactement la situation que la migration pretendait fermer.

Consequence concrete : `usage_events`, que la migration nomme elle-meme « la table qui
grossit le plus vite », croissait sans borne. Et `tools/scale_check.sh` la balaie pour
decider s'il faut repliquer — un declencheur de scaling dont le cout augmente tout seul.

Pourquoi lire les COMMENTAIRES plutot que redeclarer ici
---------------------------------------------------------
Une table de correspondance ecrite dans ce fichier serait une SECONDE declaration, et
deux declarations divergent. En lisant `obj_description()`, la politique et son
application ne peuvent pas se contredire : il n'y en a qu'une.

Ce module n'apporte que ce que le commentaire ne peut pas porter — **quelle colonne
porte l'age**, qui est un fait de schema et non de politique.

⚠️ Une declaration que ce module ne sait pas interpreter est une ERREUR, jamais un saut
silencieux. Sauter rendrait « rien a purger » et « je n'ai pas compris » indistinguables,
ce qui est precisement le defaut d'origine sous une autre forme.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ⚠️ Allowlist d'identifiants SQL — regle transverse 8. Ces noms sont interpoles dans un
# `DELETE`, donc ils ne viennent JAMAIS de la base : ils sont ecrits ici, et une table
# declaree qui n'y figure pas fait echouer bruyamment.
#
# La valeur est la colonne qui porte l'AGE de la ligne. C'est un fait de schema, que le
# commentaire de la table n'a pas a porter.
_AGE_COLUMN: dict[str, str] = {
    "usage_events": "ts",
    # `started_at` et non `created_at` : c'est l'instant de la COLLECTE, celui que
    # `check_collection_outcomes` et `airflow_kpi` lisent.
    "etl_run_log": "started_at",
    "monitoring_run": "run_at",
    "csv_upload_log": "imported_at",
    # app_error_log est CONDITIONNELLE, traitee a part : voir `_purge_conditional`.
}

# Les tables dont la retention est « garde tout ». Declarees pour que le controle de
# completude ne les signale pas comme oubliees — une exemption ecrite, pas un silence.
_KEEP_EVERYTHING = frozenset({"daily_ops_metrics"})

_DAYS_RE = re.compile(r"RÉTENTION\s*:\s*(\d+)\s*jours", re.I)
_CONDITIONAL_RE = re.compile(r"RÉTENTION\s*:\s*les d[ée]fauts\s+R[ÉE]SOLUS", re.I)
_KEEP_RE = re.compile(r"RÉTENTION\s*:\s*garde tout", re.I)

# ⚠️ Deux formes de plus, trouvees en lancant le module a blanc sur la base reelle plutot
# qu'en lisant la migration. Elles disent toutes deux « rien a purger », mais pour des
# raisons DIFFERENTES, et les confondre ferait perdre l'information :
#
#   * « bornee par construction » — une cle UNIQUE ou primaire ecrase la ligne, donc la
#     table ne peut pas grossir. Rien a purger PARCE QUE rien ne s'accumule.
#   * « TABLE MORTE » — plus personne n'ecrit dedans. Rien a purger parce que rien
#     n'arrive ; c'est une dette de schema, pas une politique de retention.
#
# Les ranger separement permet au resume de dire laquelle est laquelle. Une table morte
# qui se remet a grossir est un signal ; une table bornee qui grossit en est un autre.
_BOUNDED_RE = re.compile(r"born[ée]e? par construction", re.I)
_DEAD_RE = re.compile(r"TABLE MORTE", re.I)


def declared_retentions(db) -> dict[str, str]:
    """Les tables qui DECLARENT une retention, avec leur commentaire brut."""
    rows = db.fetch_query(
        """
        SELECT c.relname, obj_description(c.oid)
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public'
          AND c.relkind = 'r'
          AND obj_description(c.oid) ILIKE '%RÉTENTION%'
        ORDER BY 1
        """)
    return {r[0]: r[1] for r in (rows or [])}


class UndeclaredRetention(RuntimeError):
    """Une table declare une retention que ce module ne sait pas appliquer.

    Levee plutot qu'ignoree, et c'est le point : un saut silencieux rendrait « rien a
    purger » indistinguable de « je n'ai pas compris la declaration », ce qui est le
    defaut d'origine sous une autre forme.
    """


def _purge_simple(db, table: str, days: int) -> int:
    column = _AGE_COLUMN.get(table)
    if column is None:
        raise UndeclaredRetention(
            f"`{table}` declare une retention de {days} jours, mais aucune colonne d'age "
            f"n'est declaree pour elle dans `_AGE_COLUMN`. Ajouter la colonne — ou "
            f"retirer la declaration de la table si elle ne doit pas etre purgee.")
    rows = db.fetch_query(
        f"DELETE FROM {table} WHERE {column} < now() - make_interval(days => %s) "  # noqa: S608
        f"RETURNING 1",
        (days,))
    return len(rows or [])


def _purge_conditional(db, table: str) -> int:
    """`app_error_log` : les defauts RESOLUS vieillissent, les OUVERTS jamais.

    Le commentaire de la table le dit mieux que ce docstring ne pourrait : « un defaut
    ouvert depuis deux ans est le plus interessant du registre, pas le moins ».
    """
    if table != "app_error_log":
        raise UndeclaredRetention(
            f"retention conditionnelle declaree par `{table}`, que ce module ne sait "
            f"appliquer que pour `app_error_log`.")
    rows = db.fetch_query(
        "DELETE FROM app_error_log "
        "WHERE resolved_at IS NOT NULL AND resolved_at < now() - interval '365 days' "
        "RETURNING 1")
    return len(rows or [])


def purge_telemetry(db, dry_run: bool = False) -> dict[str, Any]:
    """Applique chaque retention declaree. Rend un compte par table.

    ⚠️ Ne rend JAMAIS un resultat vide sur une panne : une exception se propage. Le DAG
    qui l'appelle doit voir l'echec, pas lire un « 0 ligne purgee » rassurant.
    """
    declared = declared_retentions(db)
    result: dict[str, Any] = {"purged": {}, "kept": [], "bounded": [], "dead": [],
                              "tables": len(declared)}

    for table, comment in declared.items():
        body = comment or ""
        if _KEEP_RE.search(body) or table in _KEEP_EVERYTHING:
            result["kept"].append(table)
            continue
        if _BOUNDED_RE.search(body):
            result["bounded"].append(table)
            continue
        if _DEAD_RE.search(body):
            result["dead"].append(table)
            continue
        if _CONDITIONAL_RE.search(comment or ""):
            n = 0 if dry_run else _purge_conditional(db, table)
            result["purged"][table] = n
            continue
        m = _DAYS_RE.search(comment or "")
        if m:
            n = 0 if dry_run else _purge_simple(db, table, int(m.group(1)))
            result["purged"][table] = n
            continue
        raise UndeclaredRetention(
            f"`{table}` mentionne RÉTENTION dans son commentaire sous une forme que ce "
            f"module ne reconnait pas. Les trois formes connues sont « RÉTENTION : N "
            f"jours », « RÉTENTION : les défauts RÉSOLUS … », « RÉTENTION : garde "
            f"tout », « bornée par construction » et « TABLE MORTE ». "
            f"Commentaire lu : {body[:160]!r}")

    total = sum(result["purged"].values())
    if total:
        logger.info("telemetrie purgee : %d ligne(s) sur %d table(s)",
                    total, len(result["purged"]))
    return result


def undeclared_tables(db) -> list[str]:
    """Les tables qui declarent une retention SIMPLE sans colonne d'age connue.

    Sert au controle : une declaration ajoutee par une migration future sans sa colonne
    doit se voir avant la nuit ou la purge echoue.
    """
    out: list[str] = []
    for table, comment in declared_retentions(db).items():
        body = comment or ""
        if (_KEEP_RE.search(body) or _BOUNDED_RE.search(body) or _DEAD_RE.search(body)
                or table in _KEEP_EVERYTHING):
            continue
        if _CONDITIONAL_RE.search(body):
            continue
        if _DAYS_RE.search(body) and table not in _AGE_COLUMN:
            out.append(table)
    return out


def purge_summary(result: Optional[dict]) -> str:
    """Une ligne lisible pour le mail du soir."""
    if not result:
        return "rétention : non exécutée"
    purged = result.get("purged") or {}
    total = sum(purged.values())
    return (f"rétention : {total} ligne(s) purgée(s) sur {len(purged)} table(s) · "
            f"{len(result.get('kept') or [])} gardée(s) intégralement · "
            f"{len(result.get('bounded') or [])} bornée(s) par construction · "
            f"{len(result.get('dead') or [])} morte(s)")
