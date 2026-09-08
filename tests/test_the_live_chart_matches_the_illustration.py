"""Guard: la figure live et l'illustration committée montrent la MÊME chose.

Type: Utility
Uses: ast, src.dashboard.utils.platform_chart
Triggers: pytest
Persists in: nothing

Error class `the-live-chart-drifted-from-its-illustration`.

L'écran de bienvenue montre `assets/examples/dashboard-global.png` tant qu'un artiste
n'a pas de données, puis SA figure dès qu'il en a. Les deux doivent être la même
promesse, sinon la seconde se lit comme une régression — et c'est ce qui a été
signalé le 2026-09-08 : « ce n'est plus le même graphique, tu m'avais fait un plot qui
montre des courbes superposées des différentes plateformes avec différentes
couleurs ».

L'illustration est un `stackplot` aux couleurs `BLUE/ORANGE/AQUA` ; la figure live
était partie sur des lignes qui se croisent, aux couleurs de marque. Deux formes, deux
palettes, une seule promesse.

Ce garde tient les deux moitiés — la FORME (des aires empilées) et la PALETTE (celle
de l'illustration, lue dans le générateur et non recopiée ici, sinon les deux copies
divergent au premier changement).
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from src.dashboard.utils import platform_chart as pc

_GENERATOR = pathlib.Path("tools/dev/make_example_charts.py")
_CHART = pathlib.Path("src/dashboard/utils/platform_chart.py")


def _generator_palette() -> list:
    """Les couleurs de l'illustration, LUES dans son générateur.

    Par AST et non par import : le générateur importe matplotlib et bascule le backend
    au chargement, ce qu'un test n'a pas à déclencher pour lire trois constantes.
    """
    tree = ast.parse(_GENERATOR.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Tuple)
                and [getattr(t, "id", "") for t in node.targets[0].elts][:3]
                == ["BLUE", "ORANGE", "AQUA"]):
            return [c.value for c in node.value.elts][:3]
    pytest.fail("BLUE/ORANGE/AQUA introuvables dans le générateur — garde à repointer")
    return []


def test_the_live_palette_is_the_illustration_palette() -> None:
    """Mêmes couleurs, dans le même ordre — Spotify, YouTube, SoundCloud."""
    expected = _generator_palette()
    got = [pc._PALETTE_LIGHT[k] for k in ("spotify", "youtube", "soundcloud")]
    assert [c.lower() for c in got] == [c.lower() for c in expected], (
        f"la figure live utilise {got}, l'illustration {expected} : l'artiste voit "
        "deux figures différentes pour la même promesse")


def test_the_dark_palette_only_moves_what_the_validator_refused() -> None:
    """Le mode sombre garde la figure reconnaissable — un seul pas bouge.

    La bande de clarté du mode sombre (0,48–0,67) refuse `#eb6834` (YouTube) et
    `#eda100` (Apple, ajoutée le 2026-09-08) ; les deux autres passent tels quels.
    Décaler les quatre « pour l'harmonie » ferait de la figure sombre une autre figure.
    """
    light, dark = pc._PALETTE_LIGHT, pc._PALETTE_DARK
    moved = sorted(k for k in light if light[k].lower() != dark[k].lower())
    assert moved == ["apple", "youtube"], (
        f"le mode sombre déplace {moved} — seuls l'orange et l'ambre ont été refusés "
        "par le validateur, le reste doit rester identique")


def test_the_form_is_a_stack_not_overlapping_lines() -> None:
    """`stackgroup` est ce qui distingue une aire empilée de lignes superposées.

    Lu sur la STRUCTURE : une recherche de texte trouverait ce mot dans cette
    docstring, et le cliquet du dépôt refuse les gardes textuels.
    """
    tree = ast.parse(_CHART.read_text(encoding="utf-8"))
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "render_platform_chart")
    kwargs = {kw.arg for call in ast.walk(fn) if isinstance(call, ast.Call)
              for kw in call.keywords if kw.arg}
    assert "stackgroup" in kwargs, (
        "la figure n'empile plus : elle trace des lignes superposées, ce qui répond à "
        "« laquelle est la plus haute » et non à « combien au total, et qui y "
        "contribue » — la question de l'accueil")
    assert "fillcolor" in kwargs, "une aire empilée sans remplissage n'est pas une aire"


def test_a_missing_day_cuts_ONLY_the_platform_that_is_missing() -> None:
    """Un trou appartient à la plateforme qui l'a, et à elle seule.

    Les tranches étaient COMMUNES : un jour sans collecte YouTube coupait aussi
    Spotify. Mesuré le 2026-09-08 sur l'artiste 1, au pas hebdomadaire : **19 semaines**
    de Spotify effacées, dont **13** dont YouTube était le seul responsable, et **0**
    où Spotify manquait lui-même. L'artiste l'a lu comme « un gros trou dans les
    données de S4A » — S4A n'a aucun trou.

    Le jour non mesuré reste coupé POUR SA PLATEFORME : l'aire s'y interrompt, on ne la
    compte pas pour zéro.
    """
    span = list(range(6))
    aligned = {"spotify": [1, 2, 3, 4, 5, 6],
               "soundcloud": [1, 1, None, None, 2, 2]}
    segments = pc._segments(span, aligned, ["spotify", "soundcloud"])
    assert segments["spotify"] == [[0, 1, 2, 3, 4, 5]], (
        f"Spotify est coupé par le trou d'une AUTRE plateforme : {segments['spotify']}")
    assert segments["soundcloud"] == [[0, 1], [4, 5]], (
        f"le trou de SoundCloud ne coupe pas son aire : {segments['soundcloud']}")


def test_a_platform_with_no_point_takes_no_colour() -> None:
    """Une plateforme muette ne consomme pas une couleur qu'une autre porte ailleurs."""
    span = list(range(3))
    aligned = {"spotify": [1, 2, 3], "youtube": [None, None, None]}
    segments = pc._segments(span, aligned, ["spotify"])
    assert segments == {"spotify": [[0, 1, 2]]}, (
        "une plateforme sans aucun point ne doit pas casser la bande des autres")


# ── Une source récente ne coûte pas l'historique des autres ─────────────────

def _shape(span_len: int, measured_last: dict) -> dict:
    """Des séries alignées où chaque plateforme n'est mesurée que sur ses N derniers pas."""
    return {k: [None] * (span_len - n) + [1] * n for k, n in measured_last.items()}


def test_a_recent_platform_does_not_cost_the_others_their_history() -> None:
    """La forme RÉELLE du bac à sable au 2026-09-08, pas un cas d'école.

    Spotify y est mesuré 87 jours sur 90, YouTube 2 et SoundCloud 4 — parce qu'ils
    viennent d'être branchés. Une bande empilée exige que toutes les plateformes soient
    connues le même jour ; si « pas encore collectée » comptait comme « on ne sait
    pas », les 2 jours de YouTube effaceraient les 87 de Spotify et la page n'aurait
    **aucune** figure. C'est ce qui s'est produit après le déploiement du matin.

    Avant sa première mesure, une plateforme n'a rien apporté à ce qu'on peut montrer :
    zéro y est la bonne valeur, et seuls les trous À L'INTÉRIEUR de sa plage coupent.
    """
    span = list(range(90))
    aligned = _shape(90, {"spotify": 87, "youtube": 2, "soundcloud": 4})
    order, _thin = pc.stackable(span, aligned)
    assert set(order) == {"spotify", "youtube", "soundcloud"}, (
        f"une plateforme récente est écartée de la pile : {order}")
    covered = sum(len(seg) for seg in pc._segments(span, aligned, order)["spotify"])
    assert covered >= 85, (
        f"la bande ne couvre que {covered} jours sur 90 : les plateformes branchées "
        "récemment effacent l'historique des autres")


def test_a_hole_inside_a_platform_range_still_cuts() -> None:
    """L'autre moitié : dans sa plage, un jour non mesuré reste inconnu."""
    span = list(range(6))
    aligned = {"spotify": [1, 1, 1, 1, 1, 1],
               "youtube": [None, 1, None, 1, 1, 1]}   # plage = 1..5, trou en 2
    order, _ = pc.stackable(span, aligned)
    segments = pc._segments(span, aligned, order)["youtube"]
    assert [0, 1] in segments and all(2 not in seg for seg in segments), (
        f"le trou interne n'a pas coupé l'aire de YouTube : {segments}")


def test_a_sparse_platform_is_drawn_now_that_its_holes_are_its_own() -> None:
    """La règle de couverture a disparu, et c'est un correctif, pas un relâchement.

    Elle écartait YouTube (**24 jours mesurés sur 195**) et SoundCloud (**12 sur 74**)
    de TOUTES les vues de l'artiste 1 — mesuré le 2026-09-08, et c'est exactement la
    plainte « je ne vois que Spotify ». Elle existait parce qu'un trou coupait la bande
    de tout le monde ; depuis que les tranches sont par plateforme, une source
    clairsemée ne coûte plus rien aux autres, et l'écarter ne protège plus personne.
    """
    span = list(range(40))
    aligned = {"spotify": [1] * 40,
               "youtube": [None] * 10 + [1] + [None] * 28 + [1]}   # 2 mesures sur 30
    order, thin = pc.stackable(span, aligned)
    assert order == ["spotify", "youtube"] and not thin, (
        f"une plateforme clairsemée est encore écartée : empilées={order}, "
        f"écartées={sorted(thin)}")


def test_a_single_reading_draws_no_area_and_says_so() -> None:
    """Le seul seuil qui reste est une contrainte de FORME, pas un jugement.

    Sous un point isolé il n'y a pas de surface : la tracer ne montrerait rien, et une
    plateforme absente sans explication se lit comme une panne — la leçon de la matrice
    d'état.
    """
    span = list(range(40))
    aligned = {"spotify": [1] * 40, "youtube": [None] * 39 + [1]}
    order, thin = pc.stackable(span, aligned)
    assert order == ["spotify"] and "youtube" in thin, (
        f"empilées={order}, écartées={sorted(thin)}")
    phrase = pc.t_too_thin(*thin["youtube"])
    assert "1" in phrase, f"la phrase ne dit pas combien de mesures : {phrase}"


def test_a_platform_dropped_by_the_step_is_named(monkeypatch) -> None:
    """Assez de jours, aucun seau assez rempli — le cas YouTube au pas annuel.

    Ses 24 jours se répartissent sur deux années civiles dont aucune n'atteint la
    moitié : un total annuel bâti sur 15 jours sur 163 serait ~10× trop bas. Elle
    disparaît alors de ce pas, et le dire est la seule façon que ça ne ressemble pas à
    une panne.
    """
    phrase = pc.t_too_coarse("🎬 YouTube", "year")
    assert "YouTube" in phrase and "année" in phrase, phrase


# ── L'identité ne repose jamais sur la seule couleur ────────────────────────

def test_the_labels_are_on_the_bands_not_in_a_legend_box() -> None:
    """Le relief exigé par le validateur, et le correctif de « la légende est masquée ».

    La palette porte un avertissement de contraste ; le validateur impose alors
    « visible labels or a table view ». La table sous la figure a été retirée le
    2026-09-08 (« inutile ») — l'étiquette directe est donc le SEUL relief restant, et
    la retirer laisserait l'identité d'une aire à sa seule couleur.

    C'est aussi ce qui règle « la légende est masquée, c'est assez moche » : la légende
    horizontale était ancrée dans la marge où vit le titre sur deux lignes, et les deux
    se recouvraient. Une étiquette collée à sa bande n'a rien à recouvrir.
    """
    tree = ast.parse(_CHART.read_text(encoding="utf-8"))
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "render_platform_chart")
    kwargs = {kw.arg for call in ast.walk(fn) if isinstance(call, ast.Call)
              for kw in call.keywords if kw.arg}
    assert "annotations" in kwargs, (
        "la figure n'a plus d'étiquette posée sur les bandes : l'identité d'une aire "
        "ne repose plus que sur sa couleur, ce que l'avertissement de contraste du "
        "validateur interdit")
    assert "showlegend" in kwargs, (
        "la boîte de légende n'est plus explicitement éteinte — elle revient dans la "
        "marge du titre, qu'elle recouvre")


def test_the_labels_are_spaced_in_the_margin_not_stuck_to_the_bands() -> None:
    """Ancrées à la FIGURE, à des hauteurs distinctes — sinon elles se recouvrent.

    La première version les posait au milieu de leur aire : dès qu'une bande devient
    fine, deux étiquettes se superposent. Vu au rendu le 2026-09-08 sur « Depuis le
    début », où YouTube et SoundCloud pèsent quelques écoutes contre plusieurs milliers.

    Le garde exerce la fonction plutôt que de lire le fichier : `annotations=` peut
    être passé avec n'importe quoi.
    """
    span = list(range(10))
    aligned = {"spotify": [1000] * 10, "youtube": [1] * 10, "soundcloud": [1] * 10}
    order, _ = pc.stackable(span, aligned)
    labels = pc.margin_labels(order, ink="#000")
    assert len(labels) == len(order), "une plateforme empilée sans étiquette"
    assert {a["yref"] for a in labels} == {"paper"}, (
        "les étiquettes suivent l'épaisseur des bandes : elles se recouvriront")
    ys = sorted(a["y"] for a in labels)
    gaps = [round(b - a, 6) for a, b in zip(ys, ys[1:])]
    assert gaps and min(gaps) > 0.1, (
        f"les étiquettes sont trop proches ({gaps}) — elles se chevaucheront")


def test_the_daily_table_is_gone_and_nothing_still_calls_it() -> None:
    """Retirée le 2026-09-08 (« inutile »), et retirée VRAIMENT.

    Une fonction morte laissée en place finit par cacher une conséquence vivante —
    classe `dead-code-can-hide-a-live-consequence`, mesurée dans ce dépôt le 2026-09-06.
    """
    # Lu sur la STRUCTURE : le cliquet `test_a_guard_reads_structure_not_text` refuse
    # une comparaison de chaînes au texte source, et il a raison ici comme ailleurs —
    # ce fichier NOMME `render_daily_table` deux fois dans sa propre documentation.
    gone = {"render_daily_table"}

    assert not hasattr(pc, next(iter(gone))), (
        "`render_daily_table` est encore définie alors que plus rien ne l'appelle")

    home_tree = ast.parse(pathlib.Path("src/dashboard/views/home.py")
                          .read_text(encoding="utf-8"))
    called = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
              for n in ast.walk(home_tree) if isinstance(n, ast.Call)}
    imported = {a.name for n in ast.walk(home_tree)
                if isinstance(n, ast.ImportFrom) for a in n.names}
    assert not (called | imported) & gone, (
        "l'accueil appelle ou importe une fonction supprimée")


# ── Les trois lectures d'une même donnée ────────────────────────────────────

def test_the_cumulative_mode_only_adds_up_what_was_measured() -> None:
    """« Cumulé » est la forme de l'illustration : des bandes qui montent.

    Un trou n'y remet PAS le cumul à zéro et n'invente pas de valeur — la courbe
    s'interrompt, et le total reprend où il en était. Remettre à zéro dessinerait une
    chute d'écoutes qui n'a pas eu lieu ; combler inventerait une mesure.
    """
    aligned = {"spotify": [10, 5, None, 7]}
    got = pc._as_mode(aligned, ["spotify"], "cumulative")
    assert got["spotify"] == [10, 15, None, 22], got["spotify"]


def test_the_share_mode_makes_a_tiny_platform_visible() -> None:
    """La raison MESURÉE de ce mode : Spotify pèse 99,74 % du total de l'artiste 1.

    À l'échelle linéaire, YouTube (0,22 %) et SoundCloud (0,04 %) sont sous le pixel —
    « je ne vois que Spotify » n'était pas un bug d'affichage, c'était l'échelle, et
    aucune disposition empilée ne les rend visibles ensemble. Une part de 100 % le fait
    par construction.
    """
    aligned = {"spotify": [9974], "youtube": [22], "soundcloud": [4]}
    order = ["spotify", "youtube", "soundcloud"]
    got = pc._as_mode(aligned, order, "share")
    assert round(sum(got[k][0] for k in order), 3) == 100.0
    assert got["youtube"][0] > 0.2, (
        "une plateforme minuscule reste minuscule en part : le mode ne sert à rien")


def test_absolute_mode_changes_nothing() -> None:
    """« Par période » est la donnée telle quelle — aucune transformation cachée."""
    aligned = {"spotify": [1, None, 3]}
    assert pc._as_mode(aligned, ["spotify"], "absolute") is aligned


def test_every_mode_is_offered_and_named() -> None:
    """Un mode sans libellé est un mode qu'on ne choisit pas."""
    assert set(pc.MODES) == {"cumulative", "absolute", "share", "facets"}
    for key, label in pc.MODES.items():
        assert label.strip(), key


def test_the_smallest_platform_is_visible_in_at_least_one_mode() -> None:
    """La plainte « je ne vois que Spotify » a une réponse mesurable, et une seule.

    Sur l'artiste 1 : Spotify 99,74 %, YouTube 0,22 %, SoundCloud 0,04 %. Empilé ou en
    part, 0,26 % occupe 0,26 % de la hauteur — le mode « part » a d'abord été présenté
    comme la solution et il ne l'était pas ; il a fallu REGARDER la figure pour le
    voir. Les petits multiples donnent à chaque plateforme son propre cadre.

    Le garde suit la structure, pas le libellé : c'est `make_subplots` — une facette
    par plateforme — qui est la promesse, pas le mot « échelle » dans un menu.
    """
    src = _CHART.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_render_facets")
    called = {getattr(n.func, "id", "") or getattr(n.func, "attr", "")
              for n in ast.walk(fn) if isinstance(n, ast.Call)}
    assert "make_subplots" in called, (
        "le mode « chacune à son échelle » ne fait pas de petits multiples — une seule "
        "figure ne peut pas porter trois ordres de grandeur")
    rows = [n for n in ast.walk(fn)
            if isinstance(n, ast.keyword) and n.arg == "rows"]
    assert rows, "les facettes ne sont pas indexées par plateforme"
    assert "facets" in pc.MODES, "le mode n'est pas proposé"


# ── Un seau partiel ne se fait pas passer pour un seau plein ────────────────

def test_a_partial_bucket_is_unknown_not_full() -> None:
    """Une semaine mesurée un jour sur sept était tracée comme une semaine pleine.

    Elle sous-estime alors d'un facteur ~7, et rien ne le disait — **38 %** des
    semaines YouTube et **31 %** des semaines SoundCloud étaient dans ce cas sur
    l'artiste 1 au 2026-09-08.

    La conversion cumul → quotidien ne rattrape rien : un delta n'est calculé qu'entre
    deux jours CONSÉCUTIFS, donc les jours sautés ne sont pas reportés sur le suivant.
    """
    import datetime as dt
    mon = dt.date(2026, 1, 5)                       # un lundi
    full = [(mon + dt.timedelta(days=i), 10) for i in range(7)]
    thin = [(mon + dt.timedelta(days=7), 10)]       # 1 jour de la semaine suivante
    tail = [(mon + dt.timedelta(days=14 + i), 10) for i in range(7)]
    out = pc._aggregate({"youtube": full + thin + tail}, "week")["youtube"]
    keys = [d for d, _ in out]
    assert mon in keys and mon + dt.timedelta(days=14) in keys, keys
    assert mon + dt.timedelta(days=7) not in keys, (
        "une semaine mesurée 1 jour sur 7 est tracée comme une semaine pleine : "
        f"{out}")


def test_the_bucket_floor_matches_the_measured_distributions() -> None:
    """Le plancher est calibré sur les distributions RÉELLES, pas choisi d'instinct.

    C'est la leçon du plancher de 30 lignes/jour écrit à l'aveugle, qui rendait un
    détecteur aveugle à deux locataires sur trois. Ce sont les jours-par-semaine
    mesurés sur l'artiste 1 le 2026-09-08 qui sont épinglés ici — pas la constante,
    qu'on peut changer sans rien apprendre.
    """
    import datetime as dt
    mon = dt.date(2026, 1, 5)

    def weeks(day_counts: list) -> int:
        rows = []
        for w, n in enumerate(day_counts):
            rows += [(mon + dt.timedelta(days=7 * w + i), 5) for i in range(n)]
        return len(pc._aggregate({"youtube": rows}, "week")["youtube"])

    # youtube : 1,1,1,1,2,2,2,3,5,6 jours — aucune semaine à 7
    assert weeks([1, 1, 1, 1, 2, 2, 2, 3, 5, 6]) == 2, (
        "le plancher ne garde plus les 2 seules semaines YouTube à moitié mesurées")
    # soundcloud : 1,1,2,3,5
    assert weeks([1, 1, 2, 3, 5]) == 1, "la distribution SoundCloud a changé de verdict"
    # spotify : 7 jours partout — aucune semaine perdue
    assert weeks([7] * 12) == 12, "le plancher mange des semaines PLEINES"


def test_a_series_already_at_the_bucket_grain_escapes_the_floor() -> None:
    """Apple produit un total par ANNÉE : 1 « jour » mesuré sur 365, et c'est complet.

    Lui appliquer le plancher supprimerait chacun de ses points. La mesure est entière,
    c'est l'unité qui diffère — et `STEP_ONLY` est ce qui le dit.
    """
    import datetime as dt
    rows = [(dt.date(y, 1, 1), 900) for y in (2024, 2025, 2026)]
    out = pc._aggregate({"apple": rows}, "year")["apple"]
    assert len(out) == 3, f"le plancher a mangé les relevés annuels d'Apple : {out}"


# ── Le sous-titre compte des quantités, jamais des cumuls ───────────────────

def _subtitle(monkeypatch, series: dict, **kw) -> str:
    """Rend la figure pour de vrai et rend le texte de son titre.

    Par EFFET, et pas en lisant quelle variable la fonction utilise : c'est le nombre
    affiché qui était faux, et c'est lui qu'il faut lire.
    """
    import streamlit as st_mod
    captured = {}
    monkeypatch.setattr(st_mod, "plotly_chart",
                        lambda fig, **k: captured.setdefault("fig", fig))
    monkeypatch.setattr(st_mod, "caption", lambda *a, **k: None)
    assert pc.render_platform_chart(series, title="T", key="t", **kw)
    return captured["fig"].layout.title.text


def test_the_subtitle_sums_quantities_not_cumulative_values(monkeypatch) -> None:
    """En mode cumulé, additionner les points somme des cumuls — et c'est énorme.

    Mesuré au rendu du 2026-09-08 : **16 568 594 écoutes** annoncées pour un artiste qui
    en a 163 102. Faux d'un facteur 89, sur la vue par DÉFAUT, et aucun test ne le
    voyait — il a fallu regarder la figure. `aligned` est la série après `_as_mode` ;
    seule `aligned_raw` porte des quantités, la seule forme qu'on ait le droit de
    sommer.
    """
    import datetime as dt
    day = dt.date(2026, 1, 1)
    series = {"spotify": [(day + dt.timedelta(days=i), 10) for i in range(10)]}

    for mode in ("cumulative", "absolute"):
        text = _subtitle(monkeypatch, series, step="day", mode=mode)
        digits = "".join(c for c in text.split("écoutes")[0] if c.isdigit())
        assert digits.endswith("100"), (
            f"mode {mode} : le sous-titre annonce {digits} au lieu de 100 — "
            "il additionne des cumuls")


# ── Un pas qui ne dessine rien descend, au lieu de rendre une page muette ───

def test_a_step_that_yields_one_bucket_falls_back(monkeypatch) -> None:
    """« Cumulé · par année · cette année » ne montrait AUCUNE plateforme.

    Signalé au rendu le 2026-09-08. Reproduit : le pas annuel sur une période d'un an
    rend **un seul point** par plateforme, et sous un point isolé il n'y a pas de
    surface. Les séries se voyaient déjà refuser une aire à moins de deux mesures
    (`_MIN_POINTS`) ; la même contrainte de forme n'était pas appliquée à l'AXE, et la
    figure sortait vide sans rien dire.

    On descend au pas immédiatement plus fin — mesuré : la même période porte alors 24
    points sur les trois plateformes — et on le DIT, parce qu'un réglage ignoré en
    silence se lit comme une panne.
    """
    import datetime as dt
    import streamlit as st_mod

    figs, caps = {}, []
    monkeypatch.setattr(st_mod, "plotly_chart", lambda fig, **k: figs.setdefault("f", fig))
    monkeypatch.setattr(st_mod, "caption", lambda txt, **k: caps.append(txt))

    since, until = dt.date(2026, 1, 1), dt.date(2026, 6, 30)
    series = {"spotify": [(since + dt.timedelta(days=i), 10) for i in range(180)]}
    assert pc.render_platform_chart(series, title="T", since=since, until=until,
                                    step="year", mode="cumulative", key="k")
    drawn = [len(t.x) for t in figs["f"].data]
    assert drawn and max(drawn) >= 2, (
        f"la figure ne porte que {drawn} point(s) : une aire d'un point ne dessine rien")
    assert any("Par année" in c for c in caps), (
        f"le pas a été changé sans le dire : {caps}")


def test_a_step_that_works_is_never_changed(monkeypatch) -> None:
    """L'autre moitié : on ne descend que quand il le faut.

    Sans ce cas, un repli systématique passerait le test précédent et retirerait à
    l'utilisateur le pas qu'il a choisi.
    """
    import datetime as dt
    import streamlit as st_mod

    figs, caps = {}, []
    monkeypatch.setattr(st_mod, "plotly_chart", lambda fig, **k: figs.setdefault("f", fig))
    monkeypatch.setattr(st_mod, "caption", lambda txt, **k: caps.append(txt))

    since = dt.date(2023, 1, 1)
    series = {"spotify": [(since + dt.timedelta(days=i), 10) for i in range(1000)]}
    assert pc.render_platform_chart(series, title="T", since=since,
                                    until=since + dt.timedelta(days=999),
                                    step="year", mode="cumulative", key="k")
    assert not any("Par année" in c for c in caps), (
        f"le pas annuel tenait sur 3 années et a quand même été changé : {caps}")
