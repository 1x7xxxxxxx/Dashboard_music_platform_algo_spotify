"""Chaque plateforme se rapproche de la couche or, jamais l'inverse.

Type: Test
Uses: ast
Depends on: src/dashboard/views, src/dashboard/utils/pdf_exporter, src/api/routers
Persists in: nothing

Pourquoi ce garde existe
------------------------
Reis & Housley appellent ça une **metrics layer** (*Fundamentals of Data
Engineering*, p. 482) : l'endroit — et le seul — où la logique métier est maintenue
et calculée. ADR-019 en est la version locale : la couche or est une FRONTIÈRE.

Inventaire du 2026-09-11, agrégats (`SUM`/`AVG`) posés sur une table de fait depuis
une surface d'affichage, hors couche or :

    YouTube        0      ← repointée ce soir
    SoundCloud     0      ← repointée ce soir
    Hypeddit       1
    Revenu         1
    Apple          2
    Instagram      3
    Meta Ads      22
    Spotify S4A   33

Mesuré le même jour : **ces surfaces s'accordent aujourd'hui** — S4A rend 165 065 par
quatre chemins, Instagram 1 525 par deux. Ce n'est donc pas une liste de défauts,
c'est une liste de RISQUES. Rien ne fait qu'elles s'accordent encore demain, et le
dépôt connaît le prix : trois définitions incompatibles du total YouTube coexistaient
avant la migration 097, et deux surfaces se contredisaient d'un facteur 887 le soir
même de ce comptage.

Ce que ce cliquet tient, et pourquoi c'est cette forme
------------------------------------------------------
Il ne demande pas de tout réécrire — ADR-007 : pas de risque contre un bénéfice nul.
Il demande une seule chose : **le compte ne remonte jamais.** Une nouvelle page qui
agrège un fait elle-même est refusée ; une page qu'on repointe fait descendre le
plafond. Les deux plateformes à zéro ne peuvent plus régresser du tout.

C'est la même mécanique que `test_the_bronze_boundary_only_tightens`, à une maille
plus fine : celui-là compte des couples (surface, table), celui-ci compte des
AGRÉGATS par plateforme — donc il voit une deuxième façon de totaliser la même
métrique dans un fichier qui lisait déjà la table.
"""
from __future__ import annotations

import ast
import pathlib
import re
from collections import defaultdict

_ROOT = pathlib.Path(__file__).resolve().parent.parent
# ⚠️ LE PÉRIMÈTRE ÉTAIT L'ANGLE MORT, et il a certifié « huit plateformes à zéro »
# le 2026-09-12 alors que DOUZE agrégats vivaient hors de lui.
#
# Il ne nommait que `views/`, `pdf_exporter/` et `api/routers/`. Or `kpi_helpers.py`
# alimente CHAQUE tuile du produit et `pdf_charts.py` DESSINE les figures : ce sont
# des surfaces d'affichage au même titre qu'une vue, et elles agrégeaient onze et une
# fois respectivement. Un cliquet à zéro sur un périmètre trop étroit affirme une
# propriété fausse — c'est la forme de défaut que ce fichier existe pour interdire,
# retournée contre lui-même.
#
# `src/dashboard/utils` entre donc en entier, moins la PORTE.
_SURFACES = ("src/dashboard/views", "src/dashboard/utils", "src/api/routers")

# `platform_timeseries` est LA PORTE, pas une surface : son travail est précisément de
# lire les faits et d'en faire la règle. L'exempter n'est pas une faveur, c'est la
# définition — et si un jour elle affiche quelque chose, c'est elle qu'il faut couper
# en deux, pas cette liste qu'il faut allonger.
_DOORS = ("src/dashboard/utils/platform_timeseries.py",)

# La couche or : les vues SQL, et les fonctions qui sont la porte unique d'une règle.
_GOLD_VIEWS = frozenset({
    "v_platform_totals", "v_artist_monthly_revenue", "v_meta_spend_totals",
    "v_platform_levels", "v_s4a_song_daily", "v_meta_daily",
    "v_meta_creative_daily", "v_instagram_media_monthly", "v_hypeddit_daily",
    "v_soundcloud_track_latest",
})

# Les tables de FAIT, par plateforme. Une surface qui les agrège elle-même recopie
# une règle métier.
_FACTS: dict[str, tuple[str, ...]] = {
    "Spotify S4A": ("s4a_song_timeline", "s4a_audience", "s4a_songs_global"),
    "YouTube":     ("youtube_video_stats", "youtube_channel_history"),
    "SoundCloud":  ("soundcloud_tracks_daily",),
    "Apple":       ("apple_songs_performance", "apple_songs_history"),
    "Instagram":   ("instagram_daily_stats", "instagram_media"),
    # `meta_insights_performance` est entrée le 2026-09-12, et son absence était le
    # défaut : la tuile « Dépenses » y sommait 6 165,65 € pour 3 087,82 € réels, et
    # `\b` fait que `meta_insights\b` ne matche PAS `meta_insights_performance`.
    # Une liste de faits incomplète rend le cliquet vert sur le défaut qu'il vise.
    "Meta Ads":    ("meta_insights", "meta_insights_performance_day",
                    "meta_insights_performance"),
    "Hypeddit":    ("hypeddit_daily_stats",),
    "Revenu":      ("imusician_monthly_revenue", "distrokid_monthly_revenue",
                    "sacem_statement"),
}

# Le plafond, gelé le 2026-09-11. IL NE MONTE JAMAIS — le baisser est le travail.
_CEILING: dict[str, int] = {
    "Spotify S4A": 0,
    "Meta Ads":    0,
    "Instagram":   0,
    "Apple":       0,
    "Hypeddit":    0,
    "Revenu":      0,
    "YouTube":     0,
    "SoundCloud":  0,
}

# Mutation record — 2026-09-12 : avec `SUM(likes_count) FROM soundcloud_tracks_daily`
# remis dans `kpi_helpers.py`, ce cliquet nomme `kpi_helpers.py:414` et échoue sur
# SoundCloud ; repointé sur `v_soundcloud_track_latest`, il passe. C'est la première
# fois qu'il est vu rouge sur un fichier de `src/dashboard/utils` — sa portée ne
# l'atteignait pas jusqu'à ce jour-là, et c'était le défaut.
_AGG = re.compile(r"\b(SUM|AVG)\s*\(", re.I)


def _sites() -> dict[str, list[str]]:
    """{plateforme: [fichier:ligne]} — les agrégats hors couche or.

    Par AST, et les docstrings sont exclues : ce dépôt a pris trois gardes au vert
    sur le commentaire expliquant leur propre correctif.
    """
    out: dict[str, list[str]] = defaultdict(list)
    for root in _SURFACES:
        for path in sorted((_ROOT / root).rglob("*.py")):
            if path.relative_to(_ROOT).as_posix() in _DOORS:
                continue
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            docs = {d for n in ast.walk(tree)
                    if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                      ast.AsyncFunctionDef))
                    for d in [ast.get_docstring(n, clean=False)] if d}
            for node in ast.walk(tree):
                text = None
                if isinstance(node, ast.JoinedStr):
                    text = "".join(v.value if isinstance(v, ast.Constant) else "{}"
                                   for v in node.values)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    text = node.value
                if not text or text in docs or not _AGG.search(text):
                    continue
                if any(v in text for v in _GOLD_VIEWS):
                    continue                        # lit la couche or : c'est le but
                for platform, tables in _FACTS.items():
                    if any(re.search(rf"\bfrom\s+{t}\b", text, re.I) for t in tables):
                        rel = path.relative_to(_ROOT).as_posix()
                        out[platform].append(f"{rel}:{node.lineno}")
    return out


def test_no_platform_gains_a_metric_computed_outside_the_gold_layer() -> None:
    sites = _sites()
    grown = []
    for platform, ceiling in sorted(_CEILING.items()):
        found = sites.get(platform, [])
        if len(found) > ceiling:
            extra = found[ceiling:]
            grown.append(
                f"{platform} : {len(found)} agrégats contre un plafond de {ceiling}.\n"
                + "\n".join(f"      {s}" for s in extra[:6]))
    assert not grown, (
        "Une surface calcule une métrique que la couche or définit déjà, ou en "
        "invente une deuxième définition. Aujourd'hui les deux s'accordent ; rien ne "
        "le garantit demain — c'est ainsi que trois totaux YouTube incompatibles ont "
        "coexisté avant la migration 097.\n\n"
        "Lis une vue `v_*` de la couche or, ou passe par `platform_timeseries` — la "
        "PORTE, le seul module exempté ici. `kpi_helpers` n'en est pas une : il est "
        "scanné depuis le 2026-09-12, et il portait onze de ces agrégats.\n\n"
        + "\n".join(grown))


def test_the_clean_platforms_stay_clean() -> None:
    """LES HUIT plateformes sont à zéro. Il n'y a plus d'exception à nommer.

    Chronologie, parce qu'elle dit ce qui a marché : YouTube et SoundCloud le
    2026-09-11, après trois défauts qui se contredisaient entre eux. Apple le
    2026-09-12, quand sa règle — une sélection gloutonne d'intervalles — est
    descendue en PL/pgSQL (102, 103). Spotify le même jour, de 33 à 0, avec le grain
    TITRE (105). Puis Meta, Instagram, Hypeddit et le revenu (106).

    Le geste a été le même huit fois, et il ne s'invente pas à chaque fois : COMPTER
    les agrégats, voir quelle MAILLE ils réclament, écrire la vue qui la porte,
    repointer, et vérifier qu'aucun chiffre n'a bougé. Le comptage est ce qui dit où
    aller ; le plafond est ce qui empêche de revenir.

    À zéro partout, ce test dit une chose simple : plus aucune surface d'affichage
    n'agrège une table de fait. Toute nouvelle qui le ferait est refusée ici, nommée,
    avec le fichier et la ligne.
    """
    sites = _sites()
    for platform in sorted(_FACTS):
        found = sites.get(platform, [])
        assert not found, (
            f"{platform} agrège de nouveau une table de fait hors de la couche or :\n"
            + "\n".join(f"   {s}" for s in found)
            + "\n\nC'est la plateforme dont la définition du total avait divergé trois "
              "fois. Elle passe par `platform_timeseries`.")


def test_the_ceiling_names_every_platform_that_has_facts() -> None:
    """Un plafond manquant rend une plateforme invisible au cliquet.

    Ajouter une plateforme aux faits sans lui donner de plafond la dispenserait de la
    règle en silence — la forme d'exemption que ce dépôt paie le plus cher.
    """
    missing = sorted(set(_FACTS) - set(_CEILING))
    assert not missing, f"plateforme(s) sans plafond : {missing}"
    stale = sorted(set(_CEILING) - set(_FACTS))
    assert not stale, f"plafond(s) pour une plateforme qui n'a plus de fait : {stale}"


def test_the_ceiling_is_not_slack() -> None:
    """Un plafond très au-dessus du réel ne garde rien.

    Si quelqu'un retire dix agrégats sans baisser le plafond, le cliquet autorise dix
    régressions gratuites. Il doit donc être SERRÉ : égal au compte réel.
    """
    sites = _sites()
    slack = {p: (c, len(sites.get(p, []))) for p, c in _CEILING.items()
             if c > len(sites.get(p, []))}
    assert not slack, (
        "Des plafonds sont au-dessus du compte réel — autant de régressions "
        f"autorisées sans rien dire : {slack}. Baisse-les à la valeur mesurée.")
