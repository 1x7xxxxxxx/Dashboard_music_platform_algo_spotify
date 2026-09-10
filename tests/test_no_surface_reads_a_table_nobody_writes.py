"""Une page ne lit pas une table que rien ne remplit, et un diagramme n'en nomme pas.

Type: Test
Uses: pytest, re
Depends on: src/, migrations/, init_db.sql, .claude/dev-docs/architecture.md
Persists in: nothing

Ce qui a été mesuré (2026-09-10)
--------------------------------
`views/airflow_kpi.py` lisait `etl_daily_metrics` pour son panneau de qualité. **Rien
n'écrit cette table dans le dépôt.** Elle a été créée en prod hors de toute migration,
puis rétro-inscrite dans `migrations/062_reconcile_schema_drift.sql` dans le seul but de
faire taire `make schema-check`, et classée « USED-but-undeclared » dans
`.claude/dev-docs/schema-drift-2026-06-13.md:22` **depuis le 2026-06-13**.

Le défaut n'était donc pas ignoré : il était documenté et laissé en l'état, et la seule
trace visible avait été de **faire taire le détecteur qui le signalait**.

Mesuré côté base le même jour : `etl_daily_metrics` **2 lignes**, `etl_run_log`
**2 196** — le registre par exécution qu'écrit `dag_run_logger.py` à chaque collecte,
juste à côté. La page lisait la table vide en ignorant celle qui portait la donnée.

Deuxième moitié : `.claude/dev-docs/architecture.md` nommait `spotify_tracks` et
`spotify_top_tracks` pour le DAG Spotify. Vérifié contre la base : **aucune des deux
n'existe** ; `spotify_api_daily.py` écrit `artists`, `artist_history`, `tracks`,
`track_popularity_history`. Un diagramme qui envoie vers une table fantôme oriente vers
du vide, et rien ne le comparait au schéma.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ARCHITECTURE = REPO / ".claude" / "dev-docs" / "architecture.md"

# Les tables que le schéma canonique déclare : `init_db.sql` + toutes les migrations.
_CREATE = re.compile(
    r"CREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?(?:TABLE|VIEW)\s+"
    r"(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?[\"']?([a-z_][a-z0-9_]*)",
    re.I)

# Les noms qui ressemblent à une table dans les cellules du diagramme mais n'en sont
# pas : familles avec joker, mots de liaison, valeurs de colonnes.
_NOT_A_TABLE = re.compile(r"[*(){}<>]|^all$|^read-only$|^-+$")


def _code_basenames() -> set[str]:
    """Les noms de fichiers Python du dépôt — DAGs et modules.

    Le diagramme les cite dans les mêmes cellules que les tables (`ml_scoring_daily`,
    `algo_knowledge`, `youtube_daily`…). Sans cette exclusion le prédicat rougit sur
    seize noms parfaitement valides, et un garde qui crie sur du juste finit désarmé.
    """
    out = set()
    for d in ("airflow/dags", "src", "airflow/debug_dag"):
        for f in (REPO / d).rglob("*.py"):
            out.add(f.stem.lower())
    # Les CONSTANTES du code sont citées en minuscules dans le diagramme
    # (`ALGO_FEATURE_ZONES` → « algo_feature_zones ») : elles ne sont pas des tables.
    import re as _re
    for f in (REPO / "src").rglob("*.py"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        out |= {m.lower() for m in _re.findall(r"^([A-Z][A-Z0-9_]{3,})\s*[:=]",
                                               text, _re.M)}
    return out


def _canonical_tables() -> set[str]:
    sql = (REPO / "init_db.sql").read_text(encoding="utf-8", errors="ignore")
    for f in sorted((REPO / "migrations").glob("*.sql")):
        sql += "\n" + f.read_text(encoding="utf-8", errors="ignore")
    return {m.lower() for m in _CREATE.findall(sql)}


def _names_in_architecture() -> set[str]:
    """Les identifiants de table cités dans les tableaux du diagramme."""
    out: set[str] = set()
    for line in ARCHITECTURE.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        for cell in line.split("|"):
            for token in re.split(r"[,\s]+", cell.strip()):
                token = token.strip("`\"' .").lower()
                if not token or _NOT_A_TABLE.search(token):
                    continue
                # On ne juge QUE ce qui a la forme d'un nom de table et porte un `_` :
                # sans ça, chaque mot de prose deviendrait un faux positif.
                if re.fullmatch(r"[a-z][a-z0-9_]*_[a-z0-9_]+", token):
                    out.add(token)
    return out


def test_the_architecture_diagram_names_no_phantom_table() -> None:
    """Chaque table citée par le diagramme existe dans le schéma canonique."""
    canonical = _canonical_tables()
    assert canonical, "aucune table lue dans init_db.sql + migrations — garde cassé"

    cited = _names_in_architecture()
    # Ce qui ressemble à une table mais n'en est pas : fichiers, modules, clés.
    known_non_tables = {t for t in cited if t.endswith(("_py", "_sql", "_md", "_yaml"))}
    phantom = sorted(t for t in cited - canonical - known_non_tables
                     if not t.endswith(("_id", "_at", "_date", "_count", "_name",
                                        "_key", "_url", "_log_", "_dag")))

    # Le diagramme cite aussi des noms de DAG, de vues Streamlit et de colonnes ; on ne
    # retient que ce dont on est SÛR que c'était censé être une table, en croisant avec
    # les préfixes des tables réelles.
    prefixes = {t.split("_")[0] for t in canonical}
    code = _code_basenames()
    suspects = [t for t in phantom if t.split("_")[0] in prefixes and t not in code]

    assert not suspects, (
        "le diagramme nomme des tables qui n'existent pas : " + ", ".join(suspects) +
        ". Un diagramme qui envoie vers une table fantôme oriente vers du vide — "
        "`spotify_tracks` et `spotify_top_tracks` y ont survécu jusqu'au 2026-09-10 "
        "alors que le DAG Spotify écrit `artists`, `artist_history`, `tracks` et "
        "`track_popularity_history`."
    )


def test_no_dashboard_view_reads_the_unwritten_metrics_table() -> None:
    """`etl_daily_metrics` n'a aucun écrivain : personne ne doit la lire.

    La règle générale — « toute table lue a un écrivain » — demande un balayage que ce
    garde ne fait pas. Il ferme l'instance mesurée, et il la ferme là où elle faisait
    mal : une page de qualité qui affichait un panneau vide en lisant la mauvaise table
    pendant que `etl_run_log`, à côté, portait 2 196 lignes.
    """
    import ast

    readers = []
    for f in (REPO / "src").rglob("*.py"):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:
            continue
        # Les docstrings sont EXCLUES par construction : ce garde a rougi sur sa propre
        # explication du correctif à sa première exécution — le motif exact que le
        # dépôt catalogue sous « un garde textuel est aveugle ». On ne regarde donc que
        # les chaînes qui ne sont pas la docstring d'un module, d'une classe ou d'une
        # fonction, c'est-à-dire celles qui peuvent réellement partir en SQL.
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc is not None:
                    docstrings.add(doc)
        for node in ast.walk(tree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and "etl_daily_metrics" in node.value
                    and node.value not in docstrings):
                readers.append(f"{f.relative_to(REPO)}:{node.lineno}")
    assert not readers, (
        "lecture de `etl_daily_metrics`, que rien n'écrit dans ce dépôt : "
        + ", ".join(readers) + ". Le registre écrit à chaque collecte est "
        "`etl_run_log` (`src/utils/dag_run_logger.py`).")
