"""Hypeddit et le revenu : deux questions que personne ne leur posait.

Type: Test
Uses: ast, psycopg2, a live Postgres
Depends on: v_hypeddit_daily, v_artist_monthly_revenue, v_sacem_monthly, src/**
Persists in: nothing

Why this exists
---------------
Le tableau `plateforme × famille` de `.claude/dev-docs/gold-coverage.md` a mesuré
que **Hypeddit n'était couvert par aucune famille de forme plateforme** et que le
revenu ne l'était par aucune des deux ci-dessous. Ce sont les deux sources les plus
récentes de la couche or, et les moins gardées — la page Hypeddit n'a été
repointée sur `v_hypeddit_daily` que le 2026-09-12.

Deux questions, et elles ne se posent pas de la même façon selon la forme de la
mesure :

**1. Quantité ou compteur ?** Hypeddit compte des VISITES par jour et le revenu des
EUROS par mois. Ce sont des quantités : elles se somment, et zéro y veut dire
« rien ce jour-là ». Les traiter comme des compteurs — report en avant, croissance
dérivée des niveaux — inventerait des visites qui n'ont pas eu lieu. C'est la
symétrie exacte du défaut inverse, celui qui a coûté un facteur 151 sur YouTube :
**la même erreur se fait dans les deux sens, et une seule des deux avait un garde.**

Vérifié sur la donnée : `hypeddit_daily_stats.visits` descend à 0 (min 0, max
7 828) — impossible pour un compteur — et `v_artist_monthly_revenue` porte des
montants NÉGATIFS (les charges SACEM), ce qu'aucun compteur ne fait.

**2. Le locataire.** La règle transverse du dépôt : toute lecture des données d'un
locataire porte `WHERE artist_id = %s`. Hypeddit était la seule plateforme dont
aucun garde ne le vérifiait.

Mutation record — 2026-09-12 : `hypeddit_daily_stats` ajouté aux cibles de report
en avant (`ZERO_RESET_TARGETS`) → le test le nomme ; une lecture de
`v_hypeddit_daily` sans `artist_id` ajoutée à une vue → le test la nomme.
"""
from __future__ import annotations

import ast
import os
import re
import socket
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
_DB_HOST, _DB_PORT = "127.0.0.1", 5433

# Les relations de QUANTITÉ — celles qui se somment. Nommées ici pour que le
# tableau `plateforme × famille` les voie : une case s'y remplit quand un garde lit
# la relation dans un littéral SQL, jamais quand il prononce son nom.
_QUANTITY_SQL = {
    "Hypeddit": "SELECT SUM(visits), MIN(visits) FROM v_hypeddit_daily "
                "WHERE artist_id IS NOT NULL",
    "Revenu": "SELECT SUM(revenue_eur), MIN(revenue_eur) FROM v_artist_monthly_revenue "
              "WHERE artist_id IS NOT NULL",
    "Revenu SACEM": "SELECT SUM(amount), MIN(amount) FROM v_sacem_monthly "
                    "WHERE artist_id IS NOT NULL",
}

_TENANT_RELATIONS = ("hypeddit_daily_stats", "v_hypeddit_daily",
                     "v_artist_monthly_revenue", "v_sacem_monthly")

_FROM = re.compile(r"\b(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)", re.I)


def _dsn() -> dict | None:
    if os.environ.get("DATABASE_URL"):
        return {"dsn": os.environ["DATABASE_URL"]}
    try:
        with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
            pass
    except OSError:
        return None
    return {
        "host": _DB_HOST, "port": _DB_PORT,
        "dbname": os.environ.get("DATABASE_NAME", "spotify_etl"),
        "user": os.environ.get("DATABASE_USER", "postgres"),
        "password": os.environ.get("DATABASE_PASSWORD") or os.environ.get("DB_PASSWORD", ""),
    }


_CONN = _dsn()


@pytest.mark.skipif(_CONN is None, reason="No Postgres — la forme se lit dans la donnée")
@pytest.mark.parametrize("source", sorted(_QUANTITY_SQL), ids=sorted(_QUANTITY_SQL))
def test_these_sources_really_are_quantities_and_not_counters(source) -> None:
    """La preuve par la DONNÉE, pas par l'intention : un compteur ne redescend pas.

    Sans cette vérification, « Hypeddit est une quantité » est une opinion écrite
    dans un commentaire, et c'est exactement le genre d'opinion qui se périme quand
    la source change de sens sans prévenir.
    """
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**_CONN)
    try:
        with conn.cursor() as cur:
            cur.execute(_QUANTITY_SQL[source])
            total, low = cur.fetchone() or (None, None)
    finally:
        conn.rollback()
        conn.close()

    if total is None:
        pytest.skip(f"{source} n'a aucune donnée ici — rien à caractériser")
    assert low is not None and low <= 0, (
        f"{source} : la valeur minimale est {low}, strictement positive sur toute "
        "la série. C'est la signature d'un COMPTEUR, pas d'une quantité — et si "
        "c'en est devenu un, il doit rejoindre `v_platform_levels` et cesser d'être "
        "sommé. Se tromper de forme a coûté un facteur 151 sur YouTube ; l'erreur "
        "inverse inventerait des visites qui n'ont pas eu lieu.")


def test_no_quantity_source_is_treated_as_a_counter() -> None:
    """Elles ne doivent PAS figurer parmi les cibles de report en avant.

    `ZERO_RESET_TARGETS` est la liste des compteurs dont un retour à zéro est
    arithmétiquement impossible. Y mettre une quantité du jour produit 93 alertes
    sur 1 254 jours — mesuré — et un détecteur qui crie 93 fois n'est plus lu.
    """
    import sys
    sys.path.insert(0, str(_ROOT))
    from src.utils.value_monitor import ZERO_RESET_TARGETS

    counters = {t for t, *_ in ZERO_RESET_TARGETS}
    quantities = {"hypeddit_daily_stats", "imusician_monthly_revenue",
                  "distrokid_monthly_revenue", "sacem_statement", "s4a_song_timeline"}
    wrong = sorted(counters & quantities)
    assert not wrong, (
        f"table(s) de quantités traitées comme des compteurs : {wrong}. Un zéro y "
        "veut dire « rien ce jour-là », pas « collecte ratée ».")


def test_every_read_of_these_relations_names_its_tenant() -> None:
    """La règle transverse, sur la seule plateforme qu'aucun garde ne couvrait.

    Hypeddit est arrivé tard et sa page n'a été repointée sur la couche or que le
    2026-09-12. Une lecture sans `artist_id` y rendrait les chiffres d'un autre
    artiste — la classe que la migration 064 a payée sur YouTube.
    """
    offenders = []
    for root in ("src/dashboard", "src/api", "src/utils"):
        for path in sorted((_ROOT / root).rglob("*.py")):
            if "__pycache__" in path.parts or "i18n_catalog" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            # LA BRANCHE FLOTTE EST LÉGITIME, et la reconnaître structurellement est
            # la moitié du prédicat. Le dépôt écrit partout :
            #
            #     if artist_id is not None:  <requête scopée>
            #     else:                      <requête flotte, admin>
            #
            # Une lecture sans `artist_id` dans cette seconde branche n'est pas un
            # défaut, c'est la vue admin. La première version de ce test nommait
            # quatre sites de ce genre — un garde qui crie sur le cas normal est un
            # garde qu'on désactive.
            parent = {}
            for node in ast.walk(tree):
                for child in ast.iter_child_nodes(node):
                    parent[id(child)] = node

            def _under_a_tenant_branch(node) -> bool:
                cur, child = parent.get(id(node)), node
                while cur is not None:
                    if isinstance(cur, ast.If) and "artist_id" in ast.dump(cur.test):
                        return True
                    # LA SECONDE FORME DU MÊME IDIOME. `kpi_helpers._q` prend
                    # `(sql_scopé, sql_flotte, colonnes)` et choisit selon
                    # `artist_id is not None`. La branche vit donc dans le HELPER,
                    # pas autour du littéral — et le littéral flotte est, par
                    # construction, celui qui suit un littéral scopé sur la même
                    # relation. Reconnaître l'appariement est la seule façon de ne
                    # pas crier sur l'idiome que ce dépôt emploie partout.
                    if isinstance(cur, ast.Call) and child in cur.args:
                        pos = cur.args.index(child)
                        if pos > 0:
                            first = cur.args[0]
                            if (isinstance(first, ast.Constant)
                                    and isinstance(first.value, str)
                                    and "artist_id" in first.value
                                    and set(_FROM.findall(first.value))
                                    & set(_FROM.findall(text))):
                                return True
                    child, cur = cur, parent.get(id(cur))
                return False

            docs = {id(n.body[0].value) for n in ast.walk(tree)
                    if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                      ast.AsyncFunctionDef))
                    and n.body and isinstance(n.body[0], ast.Expr)
                    and isinstance(n.body[0].value, ast.Constant)}
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if id(node) in docs:
                        continue
                    text = node.value
                elif isinstance(node, ast.JoinedStr):
                    text = "".join(v.value if isinstance(v, ast.Constant) else "{}"
                                   for v in node.values)
                else:
                    continue
                if not any(r in _FROM.findall(text) for r in _TENANT_RELATIONS):
                    continue
                if "artist_id" in text or _under_a_tenant_branch(node):
                    continue
                offenders.append(
                    f"{path.relative_to(_ROOT).as_posix()}:{node.lineno} — lit "
                    f"{[r for r in _FROM.findall(text) if r in _TENANT_RELATIONS]} "
                    "sans nommer son locataire")
    assert not offenders, (
        "Une lecture de données de locataire sans `artist_id`, HORS d'une branche "
        "flotte explicite. C'est la classe que la migration 064 a payée sur "
        "YouTube — deux artistes bêta ont vu leurs données disparaître.\n\n"
        "Si c'est une vue admin, elle s'écrit dans le `else` d'un "
        "`if artist_id …`, comme partout ailleurs dans ce dépôt : la forme dit "
        "l'intention, et un test peut la lire.\n\n"
        + "\n".join(sorted(set(offenders))))


def test_the_scan_actually_sees_these_relations() -> None:
    """Non-vacuité : zéro contrevenant sur zéro lecture est vrai et ne dit rien."""
    seen = 0
    for root in ("src/dashboard", "src/api", "src/utils"):
        for path in (_ROOT / root).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            seen += sum(1 for r in _TENANT_RELATIONS if r in text)
    assert seen >= 5, (
        f"seulement {seen} mention(s) des relations Hypeddit et revenu — le "
        "balayage ne les atteint plus, et le test est vert à vide.")
