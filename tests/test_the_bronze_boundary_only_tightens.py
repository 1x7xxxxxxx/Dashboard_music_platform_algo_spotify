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

# Gelé le 2026-09-10. CE NOMBRE NE PEUT QUE DESCENDRE.
_CEILING = 124

# Les surfaces qui montrent des chiffres à quelqu'un.
_SURFACES = ("src/dashboard/views", "src/dashboard/utils/pdf_exporter", "src/api/routers")

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
