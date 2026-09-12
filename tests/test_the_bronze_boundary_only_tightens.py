"""Aucune surface ne lit le bronze directement — et le compte ne peut que baisser.

Type: Test
Uses: pytest, ast
Depends on: src/dashboard/views/, src/dashboard/utils/pdf_exporter/, src/api/routers/
Persists in: nothing

La règle, et pourquoi elle a besoin d'un garde
----------------------------------------------
ADR-019 pose la frontière : le **bronze** est ce que les collecteurs écrivent, tel que
reçu ; les surfaces d'affichage lisent l'**argent** ou l'**or**, jamais le bronze. Une
lecture directe du bronze, c'est une règle métier recopiée une fois de plus — et le
constat central de la séance du 2026-09-10 est qu'une règle recopiée finit par diverger :
le total de vues YouTube avait TROIS définitions vivantes, dont deux fausses.

Une règle écrite que rien ne vérifie dérive. C'est observé six fois dans ce dépôt, et
c'est pourquoi cette règle-ci arrive avec son compteur.

Pourquoi un CLIQUET et pas une interdiction
--------------------------------------------
Mesuré le 2026-09-10 : **124 couples (surface, table de bronze)** sur 35 surfaces.
Interdire d'un coup rendrait le garde rouge en permanence, donc ignoré, donc inutile —
et un balayage mécanique pour l'éteindre est précisément ce qui a déjà failli donner à
chaque administrateur les données d'un autre locataire (ADR-007).

Le garde gèle donc le nombre du jour et n'autorise qu'une chose : qu'il **baisse**.
Chaque définition qui monte en couche or le fait descendre. C'est le même mécanisme que
le cliquet des gardes textuels, qui a déjà fait passer sa liste de 32 à 21.

Ce que le prédicat ne juge PAS
-------------------------------
Les tables opérationnelles — authentification, facturation, journaux, métadonnées,
credentials, artefacts ML. Elles ne portent pas de métrique métier : les lire depuis une
vue est normal, et les compter ici ferait du bruit qui masquerait le signal.
"""
from __future__ import annotations

import ast
import re
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Journal du plafond, parce qu'un nombre qui bouge sans raison écrite est un
# nombre qu'on finira par relever sans raison :
#
#   124  gelé le 2026-09-10, sur une portée qui ne nommait que `views/` et
#        `pdf_exporter/` — donc FAUX : `csv_exporter.py` n'y était pas.
#   105  après les migrations 107-109 et leurs repointages, sur cette portée-là.
#   132  portée élargie à tout `src/dashboard` : +27 couples qui vivaient dans des
#        fichiers que personne ne regardait. Le chiffre MONTE et c'est un progrès.
#   110  `csv_exporter.py` déclaré : 21 couples qui ne sont pas une dette, c'est
#        un export de lignes brutes, et c'est ce qu'il promet.
#   108  `setup_completion.py` déclaré le 2026-09-12, en même temps que ses cinq
#        étapes de mise en route. Il posait 3 couples de plus (mapping, playlists
#        S4A) pour répondre « déjà fait ? », jamais « combien » — et le cliquet
#        avait raison de le signaler : c'est en le regardant qu'on a vérifié que
#        rien n'y calcule de quantité.
#
# À partir d'ici, il ne peut que descendre.
_CEILING = 108

# Les surfaces qui montrent des chiffres à quelqu'un.
# ⚠️ LA PORTÉE ÉTAIT L'ANGLE MORT. Elle ne nommait que `pdf_exporter` sous
# `src/dashboard/utils`, donc `csv_exporter.py` — qui EXPORTE du bronze à un
# utilisateur, la définition même d'une surface — n'y était pas, ni
# `setup_completion.py`, ni `kpi_helpers.py`. Élargie le 2026-09-12, le jour où le
# cliquet voisin (`test_the_metrics_layer_only_grows.py`) s'est fait prendre sur
# exactement la même omission.
_SURFACES = ("src/dashboard/views", "src/dashboard/utils", "src/api/routers")

# La PORTE, et un catalogue de traduction. Ni l'une ni l'autre n'est une surface :
# `platform_timeseries` a pour travail de lire le bronze et d'en faire la règle
# (ADR-022), et `i18n_catalog/` ne contient que des chaînes traduites — un nom de
# table y apparaît dans une phrase, jamais dans une requête.
_NOT_A_SURFACE = ("src/dashboard/utils/platform_timeseries.py",
                  "src/dashboard/utils/i18n_catalog/")

# Les surfaces DÉCLARÉES : elles lisent le bronze, et c'est leur travail.
#
# `csv_exporter.py` est un `SELECT * FROM <table>` par table, **zéro agrégat** —
# vérifié par le test ci-dessous, pas par une lecture rapide. Un export « toutes
# mes lignes » EST la couche bronze remise au locataire : lui faire lire les vues
# or lui rendrait des agrégats à la place de ses données. C'est exactement le
# contraire de ce qu'il promet.
#
# La déclaration est quantifiée pour la même raison que celle des axes : une
# exemption qui survit à ce qu'elle exemptait devient du budget.
_DECLARED_BRONZE_SURFACES: dict[str, str] = {
    "src/dashboard/utils/csv_exporter.py":
        "export ZIP « toutes mes lignes » : un SELECT * par table, aucun agrégat. "
        "La couche bronze remise au locataire, ce qui est sa définition.",
    "src/dashboard/utils/setup_completion.py":
        "état de MISE EN ROUTE : il demande « ce locataire a-t-il déjà fait X ? », "
        "jamais « combien ». Chaque lecture est un EXISTS — pas même un nombre à "
        "réduire en booléen — et rien n'en atteint un écran. Monter ces "
        "existences en couche or créerait des vues dont le seul travail serait "
        "`COUNT(*) > 0` — une indirection qui n'empêche aucune divergence, puisqu'il "
        "n'y a pas de règle à diverger.",
}

# Ce qui n'est pas une métrique métier : on ne le juge pas.
_OPERATIONAL = re.compile(
    r"^(saas_|active_|login_|admin_|gdpr_|subscription_|promo_|referral_|"
    r"etl_|monitoring_|app_error|csv_upload|usage_|tenant_platform|"
    r"data_revisions|schema_migrations|artist_credentials|ml_|algo_lifecycle)")

_CREATE_TABLE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:public\.)?[\"']?([a-z_][a-z0-9_]*)", re.I)
_FROM = re.compile(r"\b(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*)", re.I)


def _bronze_tables() -> set[str]:
    sql = (REPO / "init_db.sql").read_text(encoding="utf-8", errors="ignore")
    for f in sorted((REPO / "migrations").glob("*.sql")):
        sql += "\n" + f.read_text(encoding="utf-8", errors="ignore")
    return {t.lower() for t in _CREATE_TABLE.findall(sql)
            if not _OPERATIONAL.match(t.lower())}


def _direct_reads() -> dict[str, set[str]]:
    """{surface: {tables de bronze lues}} — par l'AST, jamais par le texte.

    Les docstrings sont exclues par construction : un garde qui rougit sur
    l'explication de son propre correctif apprend que le rouge est du bruit, et ce
    dépôt s'est fait prendre deux fois le même jour.
    """
    bronze = _bronze_tables()
    out: dict[str, set[str]] = defaultdict(set)
    for root in _SURFACES:
        for f in (REPO / root).rglob("*.py"):
            rel = f.relative_to(REPO).as_posix()
            if any(rel == x or rel.startswith(x) for x in _NOT_A_SURFACE):
                continue
            if rel in _DECLARED_BRONZE_SURFACES:
                continue
            try:
                tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
            except SyntaxError:
                continue
            docs = {d for n in ast.walk(tree)
                    if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                      ast.AsyncFunctionDef))
                    for d in [ast.get_docstring(n, clean=False)] if d}
            for n in ast.walk(tree):
                if not (isinstance(n, ast.Constant) and isinstance(n.value, str)):
                    continue
                if n.value in docs:
                    continue
                for t in _FROM.findall(n.value):
                    if t.lower() in bronze:
                        out[str(f.relative_to(REPO))].add(t.lower())
    return out


def test_the_declared_bronze_surfaces_still_read_bronze_and_still_do_not_aggregate() -> None:
    """Une déclaration se vérifie dans les DEUX sens, sinon c'est du budget.

    Le jour où `csv_exporter.py` se met à sommer, sa ligne ici couvre le nouvel
    agrégat sans que personne l'ait décidé. Et le jour où il cesse de lire le
    bronze, la ligne est un plafond de 21 offert à autre chose.

    Mutation record — 2026-09-12 : un `SUM(spend)` ajouté à une requête de
    `csv_exporter.py`, ce test le nomme ; la déclaration pointée sur un fichier
    qui ne lit aucune table de bronze, il le nomme aussi.
    """
    bronze = _bronze_tables()
    for rel, reason in _DECLARED_BRONZE_SURFACES.items():
        path = REPO / rel
        assert path.is_file(), f"{rel} est déclaré mais n'existe plus — {reason}"
        src = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src)
        literals = [n.value for n in ast.walk(tree)
                    if isinstance(n, ast.Constant) and isinstance(n.value, str)]
        read = {t.lower() for lit in literals for t in _FROM.findall(lit)
                if t.lower() in bronze}
        assert read, (
            f"{rel} est déclaré comme lecteur de bronze mais n'en lit plus aucune "
            "table. La déclaration est devenue un plafond offert à autre chose.")
        # `COUNT` est volontairement HORS de cette liste : c'est le seul agrégat
        # qu'une question d'existence puisse porter, et c'est ce que
        # `setup_completion` fait. `SUM`, `AVG`, `MIN`, `MAX` produisent une
        # QUANTITÉ — dès qu'une surface déclarée en calcule une, sa raison écrite
        # ne tient plus et sa déclaration devient du budget.
        aggregating = [lit[:80] for lit in literals
                       if re.search(r"\b(SUM|AVG|MIN|MAX)\s*\(", lit, re.I)
                       and any(t.lower() in bronze for t in _FROM.findall(lit))]
        assert not aggregating, (
            f"{rel} est déclaré « aucune quantité » et en calcule maintenant "
            f"{len(aggregating)} sur une table de bronze. La raison écrite ne tient "
            f"plus : {aggregating[:2]}")


def test_the_bronze_boundary_never_loosens() -> None:
    reads = _direct_reads()
    total = sum(len(v) for v in reads.values())

    assert total <= _CEILING, (
        f"{total} couples (surface, table de bronze) contre un plafond de {_CEILING}. "
        "Une surface d'affichage lit une table brute de plus qu'hier : c'est une règle "
        "métier recopiée une fois de plus, et une règle recopiée finit par diverger "
        "(ADR-019). Passer par la couche or, ou expliquer ici pourquoi ce cas n'en "
        "relève pas.\nLes surfaces les plus chargées :\n"
        + "\n".join(f"  {len(v):2}  {k}"
                    for k, v in sorted(reads.items(), key=lambda kv: -len(kv[1]))[:8]))


def test_the_ceiling_is_not_slack() -> None:
    """Un plafond très au-dessus du réel n'empêche rien.

    Si la dette descend nettement sous le plafond, c'est le plafond qu'il faut
    descendre — sinon le garde rend du budget à la prochaine régression sans que
    personne l'ait décidé.
    """
    total = sum(len(v) for v in _direct_reads().values())
    assert total >= _CEILING - 12, (
        f"{total} couples pour un plafond de {_CEILING} : la marge est devenue du "
        f"budget. Descendre `_CEILING` à {total} dans le même changement que la "
        "définition qui vient de monter en couche or.")


def test_the_predicate_sees_something() -> None:
    """Non-vacuité : un prédicat qui ne trouve rien satisferait le cliquet."""
    bronze = _bronze_tables()
    assert len(bronze) > 40, f"seulement {len(bronze)} tables de bronze reconnues"
    for expected in ("s4a_song_timeline", "youtube_video_stats", "soundcloud_tracks_daily"):
        assert expected in bronze, f"{expected} n'est plus vue comme du bronze"
