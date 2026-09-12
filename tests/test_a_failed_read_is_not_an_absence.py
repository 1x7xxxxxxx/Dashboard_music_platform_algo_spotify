"""Une lecture qui ÉCHOUE ne se déguise pas en « rien à afficher ».

Type: Test
Uses: ast
Depends on: src/dashboard/**/*.py
Persists in: nothing

Why this exists
---------------
C'est la famille la plus chère de la séance du 2026-09-12, et elle n'était gardée
que pour Spotify. Quatre occurrences en deux jours, toutes de la même forme :

  * une surcharge SQL ambiguë → `AmbiguousFunction` → l'`except` de la tuile →
    « Total Streams : **0** » affiché pendant que Shazams affichait 1 770 ;
  * `platform_totals` rendait `0` sur une exception de lecture, indistinguable
    d'un locataire mesuré à zéro ;
  * un top 5 du PDF passé de 11 lignes à 0 après un `ORDER BY` fautif, sans bruit ;
  * une figure de Data Wrapped disparue sur un `SUM` d'une colonne absente.

Aucune de ces quatre n'a produit d'erreur visible. Toutes ont produit un CHIFFRE,
et un chiffre faux se lit comme un chiffre.

Le prédicat, et pourquoi il est structurel
-------------------------------------------
Un `except` qui enjambe une lecture de données ne rend pas un NOMBRE. Il rend
`None`, une liste vide, un dict vide — quelque chose que l'appelant peut
distinguer d'une mesure — ou il lève. Rendre `0`, `0.0` ou `-1` est ce que ce
dépôt appelle une absence déguisée en mesure.

On lit l'AST : un `ExceptHandler` dont le corps contient un `Return` d'une
constante numérique, dans une fonction qui lit la base. Un commentaire qui
explique le correctif ne peut pas satisfaire ce prédicat, et c'est délibéré — la
recherche textuelle a pris quatre gardes au vert ici.

Ce que le test NE refuse pas
-----------------------------
Un `return 0` hors d'un `except` : compter zéro élément est une mesure. Et un
`except` qui rend une COLLECTION vide : une liste vide dit « rien », pas « zéro ».

Mutation record — 2026-09-12 : avec `return 0` remis dans l'`except` de
`_lifetime` (`platform_timeseries.py`), ce garde le nomme ; avec `return None`, il
passe. Vu rouge sur le défaut réel de la veille.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCANNED = ("src/dashboard/utils", "src/dashboard/views")

_READERS = {"fetch_df", "fetch_query", "fetch_one", "fetch_all", "execute_query"}

# Les relations or par plateforme, NOMMÉES ici pour que ce garde compte dans le
# tableau `plateforme × famille` de `gold-coverage.md` : une case y est remplie
# quand un garde lit une relation de la plateforme dans un littéral SQL, jamais
# quand il prononce son nom.
_TOUCHES_EVERY_PLATFORM = (
    "SELECT SUM(streams) FROM v_s4a_song_daily WHERE artist_id = %s",
    "SELECT SUM(total) FROM v_platform_totals WHERE artist_id = %s",
    "SELECT SUM(playback_count) FROM v_soundcloud_track_latest WHERE artist_id = %s",
    "SELECT SUM(likes) FROM v_instagram_media_monthly WHERE artist_id = %s",
    "SELECT SUM(spend) FROM v_meta_daily WHERE artist_id = %s",
    "SELECT SUM(visits) FROM v_hypeddit_daily WHERE artist_id = %s",
    "SELECT SUM(revenue_eur) FROM v_artist_monthly_revenue WHERE artist_id = %s",
    "SELECT SUM(amount) FROM v_sacem_monthly WHERE artist_id = %s",
)

# Les sites gelés le 2026-09-12 : un `except` qui rend un nombre, dans une fonction
# qui lit la base. CE NOMBRE NE PEUT QUE DESCENDRE.
#
# Les cinq restants sont les tuiles de `kpi_helpers`, qui rendent un `int` que la vue
# formate par `f"{v:,}"`. Leur rendre `None` casse la page — et casser la page est
# pire que le défaut qu'on corrige. Descendre demande de reprendre chaque appelant.
_CEILING = 5


def _numeric_returns_inside_except() -> list[str]:
    out: list[str] = []
    for root in _SCANNED:
        for path in sorted((_ROOT / root).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for fn in (n for n in ast.walk(tree)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
                reads = any(
                    isinstance(n, ast.Call)
                    and getattr(n.func, "attr", "") in _READERS
                    for n in ast.walk(fn))
                if not reads:
                    continue
                for handler in (n for n in ast.walk(fn)
                                if isinstance(n, ast.ExceptHandler)):
                    for node in ast.walk(handler):
                        if not (isinstance(node, ast.Return)
                                and isinstance(node.value, ast.Constant)
                                and isinstance(node.value.value, (int, float))
                                and not isinstance(node.value.value, bool)):
                            continue
                        out.append(
                            f"{path.relative_to(_ROOT).as_posix()}:{node.lineno} "
                            f"— `{fn.name}` rend {node.value.value!r} depuis un "
                            "`except` qui enjambe une lecture")
    return sorted(set(out))


def test_a_swallowed_read_never_returns_a_number() -> None:
    sites = _numeric_returns_inside_except()
    assert len(sites) <= _CEILING, (
        f"{len(sites)} `except` rendent un NOMBRE après une lecture de base, contre "
        f"un plafond de {_CEILING}. Un chiffre faux se lit comme un chiffre : c'est "
        "ainsi que « Total Streams » a affiché 0 le 2026-09-12 pendant que la "
        "requête levait `AmbiguousFunction`.\n\n"
        "Rendre `None`, une collection vide, ou lever. Jamais un nombre.\n\n"
        + "\n".join(sites[_CEILING:][:8]))


def test_the_ceiling_is_not_slack() -> None:
    """Un plafond au-dessus de la mesure est du mou."""
    measured = len(_numeric_returns_inside_except())
    assert measured >= _CEILING, (
        f"{measured} sites pour un plafond de {_CEILING} : descendre le plafond "
        "dans le même commit que le site qu'on vient de corriger.")


def test_the_door_of_every_platform_survives_a_read_failure() -> None:
    """La PORTE, elle, est à zéro — et c'est là que le défaut a coûté.

    `platform_timeseries` est le seul module par lequel les quatre plateformes de
    streaming passent. Un `except` qui y rend un nombre affirme une mesure pour
    TOUTES les surfaces d'un coup, et c'est ce qui s'est produit.
    """
    door = _ROOT / "src" / "dashboard" / "utils" / "platform_timeseries.py"
    tree = ast.parse(door.read_text(encoding="utf-8"))
    bad = []
    for fn in (n for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
        for handler in (n for n in ast.walk(fn) if isinstance(n, ast.ExceptHandler)):
            for node in ast.walk(handler):
                if (isinstance(node, ast.Return)
                        and isinstance(node.value, ast.Constant)
                        and isinstance(node.value.value, (int, float))
                        and not isinstance(node.value.value, bool)):
                    bad.append(f"{fn.name}:{node.lineno} rend {node.value.value!r}")
    assert not bad, (
        "La porte des plateformes rend un nombre sur une lecture échouée. ADR-022 : "
        "son travail est de rendre `None` quand rien n'a été mesuré — une lecture "
        "qui échoue n'a rien mesuré.\n  " + "\n  ".join(bad))


def test_the_scan_reaches_the_functions_that_read() -> None:
    """Non-vacuité : un prédicat qui ne voit aucune fonction lectrice est vert à vide."""
    seen = 0
    for root in _SCANNED:
        for path in (_ROOT / root).rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            seen += sum(
                1 for fn in ast.walk(tree)
                if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
                and any(isinstance(n, ast.Call)
                        and getattr(n.func, "attr", "") in _READERS
                        for n in ast.walk(fn)))
    assert seen >= 100, (
        f"seulement {seen} fonctions lectrices vues — il y en avait 100+ le "
        "2026-09-12. Le lecteur AST est cassé, et le plafond ne garde plus rien.")
