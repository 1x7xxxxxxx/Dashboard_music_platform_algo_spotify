"""Garde : un reçu d'effacement RGPD distingue l'échec de l'absence.

Type: Utility
Uses: ast, pathlib, psycopg2 (optionnel)
Triggers: pytest
Persists in: nothing

Classe `an-identifier-that-is-referenced-but-never-declared`, vue sur la surface qui
coûte le plus cher : l'effacement RGPD.

Ce qui a été mesuré le 2026-09-18
----------------------------------
`_GDPR_PLATFORM_TABLES` (`src/dashboard/views/admin.py`) porte **33 noms de tables**.
**11 n'existent dans aucune base** — la base locale en compte 122, aucune ne s'appelle
`s4a_spotify_data`, `soundcloud_stats_daily`, `instagram_posts`, `meta_creative_assets`,
`meta_creative_targeting`, `meta_ads_api_raw`, `meta_custom_conversions`,
`apple_top_content`, `hypeddit_overview`, `ml_training_features` ni `imusician_revenues`.

`_erase_artist_gdpr` bouclait dessus, le `DELETE` levait, et le gestionnaire écrivait
`deleted[table] = -1` — avec ce commentaire : « *table may not exist in all deployments
OR not in _ALLOWED_TABLES* ». Donc **trois choses très différentes portaient la même
valeur** :

* ce nom n'a jamais désigné une table ;
* cette table n'est pas dans l'allowlist ;
* **l'effacement a ÉCHOUÉ, et des données personnelles peuvent subsister.**

Le troisième cas est celui qu'on veut voir. Il était noyé dans un tiers de bruit, et le
résultat est sérialisé dans `gdpr_erasure_log`, c'est-à-dire dans la preuve qu'on
produirait si on nous la demandait.

Ce que ce fichier tient
-----------------------
1. Le reçu a un vocabulaire : un échec ne peut pas s'écrire comme une absence.
2. Les noms de la liste existent, ou la liste dit lesquels ne sont là que pour mémoire.

Ce qu'il ne tient PAS, et il faut le dire : il ne juge pas si la liste est COMPLÈTE.
Elle porte 22 noms valides pour une base qui en compte 122 — combien de tables portent
de la donnée personnelle est une autre question, et elle n'a pas de réponse mécanique.
"""
from __future__ import annotations

import ast
import os
import socket
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
_ADMIN = _ROOT / "src" / "dashboard" / "views" / "admin.py"


def _liste_gdpr() -> list[str]:
    tree = ast.parse(_ADMIN.read_text(encoding="utf-8"))
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(
                getattr(t, "id", "") == "_GDPR_PLATFORM_TABLES" for t in n.targets):
            return [e.value for e in ast.walk(n.value)
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return []


def test_the_list_was_really_found() -> None:
    """Non-vacuité : sans extraction, tout le reste est vert pour rien."""
    noms = _liste_gdpr()
    assert len(noms) > 20, (
        f"seulement {len(noms)} nom(s) extrait(s) de `_GDPR_PLATFORM_TABLES` — "
        "l'extraction a raté sa cible et les tests ci-dessous n'affirment rien.")


def _valeurs_ecrites() -> set[str]:
    """Les valeurs littérales que la boucle d'effacement pose dans `deleted[table]`."""
    tree = ast.parse(_ADMIN.read_text(encoding="utf-8"))
    out: set[str] = set()
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Assign) and len(n.targets) == 1):
            continue
        cible = n.targets[0]
        if not (isinstance(cible, ast.Subscript)
                and getattr(cible.value, "id", "") == "deleted"):
            continue
        v = n.value
        if isinstance(v, ast.Constant):
            out.add(repr(v.value))
        elif isinstance(v, ast.JoinedStr):
            out.add("".join(p.value for p in v.values if isinstance(p, ast.Constant)))
        else:
            out.add("<calculé>")
    return out


def test_a_failure_cannot_be_written_as_an_absence() -> None:
    """L'échec et l'absence n'ont pas le droit de partager une valeur.

    Le prédicat ne cherche pas `-1` : il vérifie que la boucle écrit **au moins trois**
    formes distinctes, et qu'aucune n'est un entier négatif — le fourre-tout d'avant.
    Un garde écrit sur la valeur `-1` serait vert le jour où quelqu'un choisit `-2`.
    """
    valeurs = _valeurs_ecrites()
    assert len(valeurs) >= 3, (
        f"la boucle d'effacement n'écrit que {len(valeurs)} forme(s) de valeur "
        f"({sorted(valeurs)}). Trois issues existent — absente, non-allowlistée, "
        "ÉCHEC — et les confondre rend le reçu inutilisable comme preuve.")
    negatifs = [v for v in valeurs if v.lstrip("'\"").startswith("-")
                and v.lstrip("'\"").lstrip("-").rstrip("'\"").isdigit()]
    assert not negatifs, (
        f"{negatifs} : un entier négatif est revenu dans le reçu d'effacement. Il "
        "portait jusqu'au 2026-09-18 trois sens à la fois, dont « des données "
        "personnelles peuvent subsister ». Écrire ce que c'est, pas un code.")
    assert any("ÉCHEC" in v or "FAIL" in v.upper() for v in valeurs), (
        f"aucune des valeurs écrites ({sorted(valeurs)}) ne nomme un ÉCHEC. C'est le "
        "seul des trois cas qui demande une action.")


def test_every_named_table_exists_or_is_declared_historical() -> None:
    """Les noms de la liste désignent une table, ou la prose dit qu'ils sont là pour mémoire."""
    s = socket.socket()
    s.settimeout(1)
    try:
        s.connect(("127.0.0.1", 5433))
    except OSError:
        pytest.skip("Postgres 5433 injoignable — « cette table existe-t-elle » ne se "
                    "lit pas dans le code")
    finally:
        s.close()
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(host="127.0.0.1", port=5433, dbname="spotify_etl",
                            user="postgres", password=os.getenv("DB_PASSWORD", "postgres"),
                            connect_timeout=3)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public'")
            reelles = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()
    assert len(reelles) > 50, f"seulement {len(reelles)} table(s) lues — catalogue suspect"

    mortes = [n for n in _liste_gdpr() if n not in reelles]
    texte = _ADMIN.read_text(encoding="utf-8")
    non_documentees = [n for n in mortes if n not in texte.split("for table in")[0]
                       or texte.count(n) < 2]
    assert not non_documentees, (
        f"{sorted(non_documentees)} sont dans `_GDPR_PLATFORM_TABLES` et n'existent pas "
        f"({len(reelles)} tables réelles), sans être nommés dans la prose qui explique "
        "pourquoi on les garde. Un nom mort dans un reçu d'effacement est du bruit là "
        "où on cherche une preuve — soit il est retiré, soit la raison de le garder est "
        "écrite à côté.")
