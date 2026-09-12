"""Un filtre de compte publicitaire désigne exactement une colonne.

Type: Test
Uses: ast, psycopg2, a live Postgres
Depends on: src/**/*.py, the deployed schema
Persists in: nothing

Why this exists
---------------
`account_clause()` (`src/dashboard/utils/meta_accounts.py`) rend le fragment
` AND ad_account_id = %s` à coller après `WHERE artist_id = %s`. Il ne rend rien
du tout quand aucun compte n'est choisi — et c'est pour ça que ce défaut a vécu
des semaines sans qu'aucun test ni aucun rendu ne le voie : **un locataire
mono-compte ne l'atteint jamais.** Il ne frappe que les locataires multi-comptes,
c'est-à-dire exactement la population qu'ADR-013 est allé chercher.

Mesuré contre la base le 2026-09-12, cinq requêtes de `meta_creatives.py` et
`meta_ads_overview.py` tombaient dès qu'un compte était choisi, de deux façons :

  * **la colonne n'existe pas.** La migration 106 a fait descendre la jointure
    créative dans `v_meta_creative_daily` et le repointage a été fait colonne par
    colonne sur la liste du SELECT. Personne n'a regardé le WHERE, qui filtrait
    sur `ad_account_id` — absent de la vue.
    `ERROR: column "ad_account_id" does not exist`
  * **la colonne est ambiguë.** `meta_ads`, `meta_adsets` et `meta_campaigns` la
    portent toutes les trois ; un filtre non qualifié sur leur jointure ne
    désigne rien.
    `ERROR: column reference "ad_account_id" is ambiguous`

Les deux sont des 500 en production, pas des chiffres faux. Ils ont été corrigés
en lisant les vues or, qui n'ont qu'une colonne de ce nom — le défaut ne peut
plus se poser sur une lecture de vue. Ce test empêche qu'il revienne par une
jointure neuve.

Pourquoi il lit le CATALOGUE et pas les migrations
--------------------------------------------------
La question est « cette relation a-t-elle cette colonne là où le code tourne »,
et seul le catalogue y répond. Un fichier de migration dit ce que quelqu'un a eu
l'intention d'appliquer. Même raison que
`tests/test_an_upsert_targets_an_index_that_exists.py`.

Ce qu'il ne couvre PAS
----------------------
Le fragment d'un `account_clause(x, "mc.")` est QUALIFIÉ et donc toujours sain.
Ce test le reconnaît quand la liaison est dans le même fichier. Quand le fragment
arrive par un paramètre de fonction (`def _render_fatigue(db, aid, acct="")`), il
ne peut pas voir l'alias : il suppose alors NON qualifié, ce qui est le sens
prudent — un faux positif se voit et se corrige, un faux négatif est un 500.

Mutation record — 2026-09-12 : avec `_QUERY_CREATIVES` remis sur sa quadruple
jointure, ce garde nomme le site et dit « ambigu » ; avec `_QUERY_TS_ALL` remis
sur `v_meta_creative_daily` sans sa colonne (état d'avant la migration 108), il
dit « ne porte pas ad_account_id ». Vu rouge sur les deux formes.
"""
from __future__ import annotations

import ast
import os
import pathlib
import re
import socket

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SCANNED = ("src",)
_COLUMN = "ad_account_id"
_DB_HOST, _DB_PORT = "127.0.0.1", 5433

_FROMJOIN = re.compile(r"\b(?:FROM|JOIN)\s+(?:public\.)?([a-zA-Z_][a-zA-Z0-9_]*)", re.I)


def _dsn() -> dict | None:
    if os.environ.get("DATABASE_URL"):
        return {"dsn": os.environ["DATABASE_URL"]}
    try:
        with socket.create_connection((_DB_HOST, _DB_PORT), timeout=1.5):
            pass
    except OSError:
        return None
    return {
        "host": _DB_HOST,
        "port": _DB_PORT,
        "dbname": os.environ.get("DATABASE_NAME", "spotify_etl"),
        "user": os.environ.get("DATABASE_USER", "postgres"),
        "password": os.environ.get("DATABASE_PASSWORD") or os.environ.get("DB_PASSWORD", ""),
    }


_CONN = _dsn()

pytestmark = pytest.mark.skipif(
    _CONN is None,
    reason=f"No Postgres on {_DB_HOST}:{_DB_PORT} — only the catalogue knows the columns",
)


@pytest.fixture(scope="module")
def carriers() -> frozenset[str]:
    """Les relations — tables ET vues — qui portent `ad_account_id`."""
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(**_CONN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND column_name = %s", (_COLUMN,))
            rows = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()
    assert rows, "aucune relation ne porte ad_account_id — le catalogue n'a rien rendu"
    return frozenset(rows)


def _aliased_names(tree: ast.AST) -> set[str]:
    """Les noms liés à un `account_clause(..., "préfixe.")` — donc qualifiés."""
    out: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call)):
            continue
        fn = getattr(node.value.func, "id", None) or getattr(node.value.func, "attr", None)
        if fn != "account_clause":
            continue
        alias = node.value.args[1] if len(node.value.args) > 1 else None
        for kw in node.value.keywords:
            if kw.arg == "alias":
                alias = kw.value
        if not (isinstance(alias, ast.Constant) and alias.value):
            continue                                   # pas d'alias : non qualifié
        for target in node.targets:
            if isinstance(target, ast.Tuple) and target.elts:
                if isinstance(target.elts[0], ast.Name):
                    out.add(target.elts[0].id)
            elif isinstance(target, ast.Name):
                out.add(target.id)
    return out


def _enclosing_select(text: str, at: int) -> str:
    """La portée SQL du fragment : le `(...)` le plus proche qui contient un FROM.

    Sans ça, `_QUERY_UNCOLLECTED` serait signalé à tort : son fragment vit dans un
    `LEFT JOIN (SELECT … FROM v_meta_daily …)`, dont la seule relation est saine,
    alors que la requête ENGLOBANTE en joint trois qui portent la colonne. Une
    portée trop large invente un défaut, et un livrable qui se trompe coûte plus
    cher qu'un livrable incomplet.
    """
    depth, start = 0, None
    for i in range(at - 1, -1, -1):
        if text[i] == ")":
            depth += 1
        elif text[i] == "(":
            if depth == 0:
                start = i
                break
            depth -= 1
    if start is None:
        return text
    depth = 0
    for j in range(start, len(text)):
        if text[j] == "(":
            depth += 1
        elif text[j] == ")":
            depth -= 1
            if depth == 0:
                inner = text[start + 1:j]
                return inner if _FROMJOIN.search(inner) else text
    return text


def _sql_sites() -> list[tuple[str, int, str]]:
    """(site, texte, marqueur) pour chaque littéral SQL qui reçoit un fragment."""
    out: list[tuple[str, int, str]] = []
    for root in _SCANNED:
        for path in sorted((_ROOT / root).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            aliased = _aliased_names(tree)
            for node in ast.walk(tree):
                text, carries = None, False
                if isinstance(node, ast.JoinedStr):
                    parts = []
                    for value in node.values:
                        if isinstance(value, ast.Constant):
                            parts.append(str(value.value))
                            continue
                        names = {n.id for n in ast.walk(value) if isinstance(n, ast.Name)}
                        hit = {n for n in names if "acct" in n or "account" in n}
                        if hit and not (hit & aliased):
                            carries = True
                            parts.append("\x01")        # la place du fragment
                        else:
                            parts.append("{}")
                    text = "".join(parts)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    text = node.value
                    marker = re.search(r"\{(acct[a-z_]*)\}", text)
                    if marker and marker.group(1) not in aliased:
                        carries = True
                        text = text[:marker.start()] + "\x01" + text[marker.end():]
                if not (text and carries):
                    continue
                if not _FROMJOIN.search(text):
                    continue
                out.append((f"{path.relative_to(_ROOT).as_posix()}:{node.lineno}",
                            node.lineno, text))
    return out


def test_every_account_filter_resolves_to_exactly_one_column(carriers) -> None:
    sites = _sql_sites()
    assert sites, (
        "aucune requête portant un fragment de compte n'a été trouvée — le lecteur "
        "AST est cassé, et ce test ne garde plus rien."
    )

    offenders = []
    for site, _line, text in sites:
        scope = _enclosing_select(text, text.index("\x01"))
        relations = {r for r in _FROMJOIN.findall(scope)}
        holders = sorted(relations & carriers)
        if len(holders) == 1:
            continue
        if not holders:
            offenders.append(
                f"{site} : le filtre porte sur {_COLUMN}, qu'aucune des relations "
                f"lues ({', '.join(sorted(relations)) or 'aucune'}) ne possède. "
                f"→ column \"{_COLUMN}\" does not exist")
        else:
            offenders.append(
                f"{site} : {len(holders)} relations lues portent {_COLUMN} "
                f"({', '.join(holders)}) et le filtre n'est pas qualifié. "
                f"→ column reference \"{_COLUMN}\" is ambiguous")

    assert not offenders, (
        "Un filtre de compte publicitaire ne désigne pas une colonne unique. Ce n'est\n"
        "pas un chiffre faux : la requête LÈVE, donc la page tombe — et seulement pour\n"
        "les locataires multi-comptes, jamais en développement mono-compte.\n\n"
        "Le remède est le même dans les deux cas : lire la vue or. Elle n'a qu'une\n"
        "colonne de ce nom, donc ni absence ni ambiguïté possibles.\n\n"
        + "\n".join(offenders))


def test_the_gold_views_still_carry_the_column(carriers) -> None:
    """Nommer les vues, pour qu'une régression sur elles ne passe pas pour « zéro site ».

    Le test général ci-dessus resterait vert si ces vues perdaient la colonne ET
    que tous leurs lecteurs cessaient de filtrer dessus — un prédicat sans site,
    la forme d'aveuglement que ce dépôt a mesurée cinq fois.
    """
    for view in ("v_meta_creative_daily", "v_meta_adset_daily", "v_meta_daily"):
        assert view in carriers, (
            f"{view} ne porte plus {_COLUMN}. C'est le défaut de la migration 108 : "
            "la vue or a perdu une colonne que ses lecteurs filtrent, et la page "
            "tombe dès qu'un locataire choisit un compte.")
