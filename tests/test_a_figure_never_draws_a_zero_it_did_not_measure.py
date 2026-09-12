"""Aucune figure ne dessine un zéro là où elle n'a pas mesuré.

Type: Test
Uses: pytest, plotly (via platform_chart), ast
Depends on: src/dashboard/utils/platform_chart.py, les vues qui tracent une série
Persists in: nothing

Pourquoi ce garde existe
------------------------
Demandé le 2026-09-12 : « est-ce que sur le graphique de l'accueil, on peut faire en
sorte de ne pas visualiser 0 mais genre (absence de data) quand on a pas importé le
csv de spotify des derniers jours ».

La figure coupait déjà la bande de la plateforme absente — c'est `known()`, réglé le
2026-09-10. Mais Plotly EMPILE par `stackgroup`, et un `stackgroup` infère **zéro**
pour la trace qui n'a pas de point à cet index : le TOTAL empilé redescendait donc,
et se lisait comme une chute d'écoutes. Le seul rattrapage était une phrase sous la
figure (`t_missing`), c'est-à-dire du texte contre un pixel — et le texte perd.

Ce que ce fichier tient, en deux temps :

  1. **La figure de l'accueil.** Sur le produit cartésien des périodes, des pas et
     des modes, aucun `y` remis à Plotly ne vaut `0` à un index que `known()` déclare
     non mesuré, et une bande hachurée couvre cet index. Les `y` sont lus sur la
     figure RÉELLE, jamais recalculés — recalculer serait écrire une seconde fois la
     règle qu'on prétend vérifier.

  2. **Les autres figures.** Un cliquet AST sur les `fillna(0)` en contexte temporel,
     gelé à la mesure du jour. La liste ne peut que raccourcir : chaque entrée est un
     site examiné, et un site nouveau doit être justifié avant d'y entrer.

Journal de mutation — 2026-09-12
--------------------------------
* `unmeasured_spans` rendant `[]` → le test de la hachure rougit en nommant le mode.
* le `or 0` remis sur le `y` de la pile → le test du zéro rougit en nommant l'index.
Les deux messages ont été lus, pas seulement le code de sortie.
"""
from __future__ import annotations

import ast
import datetime as _d
import pathlib

import pytest

from src.dashboard.utils import platform_chart as pc

_ROOT = pathlib.Path(__file__).resolve().parent.parent


# ── 1. La figure de l'accueil ───────────────────────────────────────────────

def _series():
    """Spotify complète, YouTube mesurée puis INTERROMPUE au milieu.

    Le trou est au milieu, jamais au bord : avant la première mesure, zéro est
    VRAI — la plateforme n'était pas encore collectée — et un garde qui confondrait
    les deux exigerait de hachurer toute la préhistoire de chaque source.
    """
    days = [_d.date(2026, 1, 1) + _d.timedelta(days=i) for i in range(90)]
    return days, {
        "spotify": [(d, 100 + i) for i, d in enumerate(days)],
        # mesurée les 30 premiers jours, puis les 20 derniers : 40 jours de trou
        "youtube": [(d, 5) for i, d in enumerate(days) if i < 30 or i >= 70],
    }


def _figure(monkeypatch, *, mode: str, step, only=None):
    import streamlit as st_mod
    captured: dict = {}
    monkeypatch.setattr(st_mod, "plotly_chart",
                        lambda fig, **k: captured.setdefault("fig", fig))
    monkeypatch.setattr(st_mod, "caption", lambda *a, **k: None)
    monkeypatch.setattr(st_mod, "info", lambda *a, **k: None)
    days, series = _series()
    drawn = pc.render_platform_chart(
        series, since=days[0], until=days[-1], step=step, mode=mode, only=only,
        title="T", key="t")
    return captured.get("fig") if drawn else None


_MODES = ("cumulative", "absolute", "share", "facets")
_STEPS = (None, "day", "week", "month", "year")


@pytest.mark.parametrize("mode", _MODES)
@pytest.mark.parametrize("step", _STEPS)
def test_no_trace_carries_a_zero_where_nothing_was_measured(monkeypatch, mode, step):
    """Un zéro dessiné affirme « aucune écoute ». On n'a pas mesuré, c'est autre chose.

    Le test lit les `y` de chaque trace de plateforme et croise avec sa propre
    couverture : si une trace porte un `0` à un index alors qu'elle porte aussi des
    valeurs de part et d'autre, ce zéro a été fabriqué.
    """
    fig = _figure(monkeypatch, mode=mode, step=step)
    if fig is None:
        pytest.skip(f"rien de traçable en mode={mode} pas={step}")
    offenders = []
    for tr in fig.data:
        if getattr(tr, "legendgroup", None) == "__unmeasured__":
            continue                      # la hachure est un rectangle, pas une série
        ys = list(tr.y or [])
        seen = [i for i, v in enumerate(ys) if v is not None]
        if not seen:
            continue
        first, last = seen[0], seen[-1]
        # Entre sa première et sa dernière mesure, un zéro n'est crédible que si la
        # plateforme a vraiment fait zéro — or aucune série de cette mise en scène
        # ne vaut zéro. Tout zéro strictement à l'intérieur est donc inventé.
        inner_zeros = [i for i in range(first + 1, last)
                       if ys[i] == 0]
        if inner_zeros:
            offenders.append(f"{tr.name}: zéro dessiné aux index {inner_zeros[:5]}")
    assert not offenders, (
        f"mode={mode} pas={step} — la figure dessine un zéro qu'elle n'a pas mesuré.\n"
        "Plotly infère 0 pour une trace sans point dans un `stackgroup` ; il faut "
        "lui rendre `None`, pas `v or 0`.\n" + "\n".join(offenders))


@pytest.mark.parametrize("mode", _MODES)
def test_the_hover_carrier_covers_every_unmeasured_day(monkeypatch, mode):
    """Au pas du JOUR le compte est connu : 40 jours de trou, 40 colonnes à couvrir.

    L'invariant relatif du test voisin ne dit pas COMBIEN ; celui-ci le dit, au seul
    pas où la mise en scène le détermine. Une colonne ratée retombe sur le « 0 »
    inféré par la pile, c'est-à-dire exactement le défaut qu'on corrige.
    """
    fig = _figure(monkeypatch, mode=mode, step="day")
    if fig is None:
        pytest.skip(f"rien de traçable en mode={mode}")
    xs = {x for tr in fig.data
          if getattr(tr, "legendgroup", None) == "__unmeasured__"
          and getattr(tr, "fill", None) != "toself"
          for x in (tr.x or [])}
    assert len(xs) == 40, (
        f"{len(xs)} jours couverts par le porteur de survol au lieu de 40 — "
        "YouTube est non mesurée du 31ᵉ au 70ᵉ jour de la mise en scène.")


@pytest.mark.parametrize("mode", _MODES)
@pytest.mark.parametrize("step", ("day", "week"))
def test_the_gap_is_covered_by_a_hatched_band(monkeypatch, mode, step):
    """Couper la bande ne suffit pas : il faut DIRE que le trou en est un.

    Sans la hachure, la pile redescend au niveau des plateformes présentes et se lit
    comme une chute. C'est le rattrapage que `t_missing` faisait en prose, et la
    prose perd contre un pixel.
    """
    fig = _figure(monkeypatch, mode=mode, step=step)
    if fig is None:
        pytest.skip(f"rien de traçable en mode={mode} pas={step}")
    # DEUX RÔLES DANS LE MÊME GROUPE DE LÉGENDE, et il faut les distinguer.
    #
    # Le groupe `__unmeasured__` porte la BANDE (un rectangle `fill="toself"` avec un
    # motif) et, depuis le 2026-09-12, le PORTEUR DE SURVOL (des marqueurs invisibles,
    # un par pas non mesuré). Ils partagent le groupe pour qu'un clic de légende les
    # bascule ensemble — cacher la hachure sans cacher son infobulle laisserait une
    # étiquette flotter sur rien.
    #
    # Ce test exige donc les deux, séparément : la bande se VOIT, le porteur se
    # SURVOLE. Une seule assertion sur « toutes les traces du groupe ont un motif »
    # rougissait sur le porteur, qui n'en a légitimement aucun.
    group = [tr for tr in fig.data
             if getattr(tr, "legendgroup", None) == "__unmeasured__"]
    hatched = [tr for tr in group if getattr(tr, "fill", None) == "toself"]
    assert hatched, (
        f"mode={mode} pas={step} — YouTube a 40 pas non mesurés au MILIEU de sa "
        "plage et aucune bande hachurée ne les couvre. L'absence redevient "
        "indiscernable d'un zéro.")
    for tr in hatched:
        assert tr.fillpattern.shape, (
            "la bande est posée sans motif : un rectangle transparent ne se voit "
            "pas. ⚠️ `add_vrect` (une SHAPE) ne supporte pas `fillpattern` — "
            "vérifié sur plotly 5.24.1 et 6.5.2 ; c'est pourquoi c'est une trace.")

    carrier = [tr for tr in group if getattr(tr, "fill", None) != "toself"]
    assert carrier, (
        f"mode={mode} pas={step} — la hachure se voit mais ne se SURVOLE pas. Un "
        "rectangle n'a que quatre coins : en `hovermode=\"x unified\"` il ne "
        "contribue à aucune colonne entre les deux, et l'artiste qui survole un trou "
        "lit « 0 » — le chiffre qu'on a justement cessé de dessiner.")
    # L'INVARIANT EST RELATIF AU PAS, pas un nombre absolu. Les 40 jours non mesurés
    # de la mise en scène font 40 colonnes au pas JOUR et 5 seaux au pas SEMAINE ;
    # un seuil écrit pour le premier rougit sur le second sans qu'aucun défaut
    # existe. C'est `un-seuil-écrit-d-instinct`, pris sur mon propre garde.
    #
    # Ce qui est vrai à tous les pas : le porteur couvre au moins un point, et
    # AUCUN de ses points ne tombe hors d'une bande hachurée — sinon il annoncerait
    # « pas de donnée » là où la figure en trace une.
    xs = [x for tr in carrier for x in (tr.x or [])]
    assert xs, "le porteur de survol n'a aucun point"
    windows = [(min(tr.x), max(tr.x)) for tr in hatched]
    stray = [x for x in xs if not any(lo <= x <= hi for lo, hi in windows)]
    assert not stray, (
        f"{len(stray)} point(s) du porteur de survol tombent HORS des bandes "
        f"hachurées (p.ex. {stray[0]}) : il annoncerait « pas de donnée » sur un pas "
        "que la figure trace.")
    assert all("<extra></extra>" in (tr.hovertemplate or "") for tr in carrier), (
        "le porteur de survol affiche encore la boîte de nom de trace à côté de son "
        "message — deux étiquettes pour un seul fait.")


@pytest.mark.parametrize("step", ("day", "week", "month"))
def test_a_platform_collected_late_says_so_without_erasing_the_others(monkeypatch, step):
    """Une plateforme branchée tard ne montre pas trois ans de zéro muet.

    Signalé le 2026-09-12 : « pourquoi je n'ai pas de data pour youtube et
    soundcloud depuis le début cumulé par mois, ça a l'air de commencer en novembre
    et décembre 2025 ». C'était VRAI — la collecte YouTube démarre le 2025-11-29 —
    et c'est précisément ce que la figure ne disait pas : elle traçait la plateforme
    depuis 2023 avec `y=None`, que `stackgroup` rend à zéro, puis un saut à 99 594.

    ⚠️ CE N'EST PAS LA HACHURE QUI PORTE CE FAIT, et la première version de ce garde
    exigeait le contraire. La hachure est pleine hauteur : elle affirme quelque chose
    de TOUTES les plateformes à la fois. Mesuré sur l'artiste 1 avant livraison —
    SoundCloud démarrant le 2026-03-31, **1 185 jours sur 1 350** passaient sous les
    hachures, dont les trois années où Spotify est mesurée chaque jour. La figure
    aurait affirmé qu'on n'avait rien mesuré depuis 2023 : une plateforme arrivée
    tard effaçait l'historique d'une ancienne, exactement ce que `known()` avait été
    écrite pour empêcher.

    Le fait est INDIVIDUEL, donc il se dit individuellement : une trace de survol au
    nom de la plateforme sur sa seule préhistoire. Et parce qu'un fait qui ne se lit
    qu'au survol ne se lit pas — la remarque ci-dessus a été écrite en REGARDANT la
    figure — une note sous la figure nomme la date de départ.

    ⚠️ `known()` n'est pas en cause et ne doit pas bouger : elle pilote les BANDES,
    et la changer supprimerait l'aire au lieu de l'expliquer.
    """
    import streamlit as st_mod
    captured: dict = {}
    notes: list = []
    monkeypatch.setattr(st_mod, "plotly_chart",
                        lambda fig, **k: captured.setdefault("fig", fig))
    monkeypatch.setattr(st_mod, "caption", lambda *a, **k: notes.append(str(a[0])))
    monkeypatch.setattr(st_mod, "info", lambda *a, **k: None)

    days = [_d.date(2024, 1, 1) + _d.timedelta(days=i) for i in range(400)]
    late = days[300]          # la seconde plateforme n'existe qu'au dernier quart
    series = {"spotify": [(x, 10) for x in days],
              "youtube": [(x, 3) for x in days if x >= late]}
    assert pc.render_platform_chart(series, since=days[0], until=days[-1], step=step,
                                    mode="cumulative", key="late")
    fig = captured["fig"]

    # 1. Le survol NOMME la plateforme et sa préhistoire.
    pre = [tr for tr in fig.data
           if "pas encore collect" in (getattr(tr, "hovertemplate", "") or "")]
    assert pre, (
        f"pas={step} — rien ne se survole avant la 1ʳᵉ mesure de YouTube. Les points "
        "y valent `None`, donc l'infobulle groupée n'affiche AUCUNE ligne pour eux : "
        "« j'ai pas de data pour youtube » est la lecture exacte de ce silence.")
    assert all("YouTube" in str(tr.name) for tr in pre), (
        f"pas={step} — la trace de préhistoire ne porte pas le nom de sa plateforme, "
        f"donc sa ligne n'apparaît pas au bon endroit : {[tr.name for tr in pre]}")
    covered = sorted(x for tr in pre for x in (tr.x or []))
    assert covered and covered[0] <= days[0], (
        f"pas={step} — le survol ne remonte pas au début de la fenêtre.")

    # 2. Il S'ARRÊTE à la première mesure — sinon il nierait ce que la figure trace.
    # LE PORTEUR DE SURVOL PORTE LE MÊME NOM QUE LA BANDE — c'est fait pour : sa
    # ligne doit apparaître au bon endroit dans l'infobulle groupée. Il faut donc
    # l'exclure ici sur autre chose que le nom, sinon « le premier point tracé »
    # devient le premier point INVISIBLE et l'assertion se compare à elle-même.
    drawn = sorted({x for tr in fig.data
                    if "YouTube" in str(tr.name) and tr not in pre
                    for x, y in zip(tr.x or [], tr.y or []) if y is not None})
    assert drawn, "la plateforme tardive n'est pas tracée du tout"
    assert max(covered) < drawn[0], (
        f"pas={step} — le survol « pas encore collectée » déborde jusqu'au "
        f"{max(covered)} alors que la figure trace un point dès le {drawn[0]}.")

    # 3. La note se LIT sans survoler.
    note = next((n for n in notes if "mesurée depuis" in n), None)
    assert note, (
        f"pas={step} — aucune note ne dit depuis quand YouTube est mesurée. "
        f"Notes rendues : {notes}")
    # 3 bis. ET ELLE NOMME UN SEAU, PAS UN JOUR QU'ON N'A PAS MESURÉ. `span[i]` est
    # le DÉBUT du seau : au pas mois, une première mesure du 30/11 y devient
    # « 01/12 ». Écrire cette date invente un jour — même piège qu'un seuil écrit
    # au pas jour et relu au pas semaine, ici sur un libellé.
    shaped = {"day": "/", "week": "semaine du", "month": str(late.year)}[step]
    assert shaped in note, (
        f"pas={step} — la note dit « {note} », qui ne se lit pas comme un {step}. "
        "Un début de seau présenté comme une date affirme une mesure qu'on n'a pas "
        "faite.")
    if step == "month":
        assert "/" not in note, (
            f"pas=month — la note écrit une date pleine (« {note} ») alors que le "
            "seau vaut un mois entier : le jour qu'elle nomme est le 1er du mois, "
            "pas celui de la mesure.")

    # 4. Et SURTOUT : la préhistoire d'une plateforme ne hachure pas la fenêtre
    #    entière. Spotify est mesurée dès le premier pas — rien n'est « non mesuré ».
    hatched = [tr for tr in fig.data
               if getattr(tr, "legendgroup", None) == "__unmeasured__"
               and getattr(tr, "fill", None) == "toself"]
    assert not hatched, (
        f"pas={step} — {len(hatched)} bande(s) hachurée(s) alors que Spotify est "
        "mesurée tous les jours de la fenêtre. Une hachure pleine hauteur affirme "
        "que PERSONNE ne mesurait ; l'unionner avec la préhistoire d'une plateforme "
        "tardive efface l'historique des autres (1 185 jours sur 1 350, artiste 1).")


def test_the_window_never_starts_before_the_first_measurement():
    """Pourquoi la préhistoire n'est PAS une affaire de hachure — le fait, épinglé.

    On a voulu hachurer « les pas où personne n'avait encore commencé ». Ce cas ne
    se produit jamais : `_window` fait partir le `span` du premier jour mesuré
    TOUTES plateformes confondues, donc au moins une plateforme a sa première mesure
    à l'indice 0. Le paramètre `before_first` aurait été du code correct que rien
    n'atteint — la forme que ce dépôt paie le plus souvent.

    Ce test tient le fait plutôt que la constante : si `_window` cesse un jour de
    borner ainsi (une fenêtre qui respecte `since` même sans donnée), il rougit, et
    c'est ce jour-là qu'une hachure de préhistoire redeviendrait une question.
    """
    days = [_d.date(2024, 1, 1) + _d.timedelta(days=i) for i in range(400)]
    series = {"spotify": [(x, 10) for x in days if x >= days[200]],
              "youtube": [(x, 3) for x in days if x >= days[300]]}
    span, aligned = pc._window(series, None, days[0], days[-1])
    assert span and span[0] == days[200], (
        f"la fenêtre commence le {span[0] if span else None}, pas au premier jour "
        f"mesuré ({days[200]}) : un pas antérieur à TOUTE mesure existe désormais, "
        "et la figure l'y dessine en zéro muet.")
    firsts = [pc._measured_range(aligned[k])[0] for k in aligned]
    assert min(f for f in firsts if f is not None) == 0, (
        "aucune plateforme ne mesure au premier pas de la fenêtre — l'intersection "
        "« personne ne regardait » est redevenue non vide.")


def test_the_facets_do_not_hatch_a_platform_own_prehistory(monkeypatch):
    """En petits multiples, chaque facette vit sur SA plage.

    Y hachurer « avant la première mesure » hachurerait du vide : la facette de
    YouTube n'a pas à expliquer qu'elle ne montre rien là où elle n'a rien à
    montrer. C'est le seul mode où `before_first=False`, et sans ce test la
    distinction disparaîtrait au premier nettoyage.
    """
    import streamlit as st_mod
    captured: dict = {}
    monkeypatch.setattr(st_mod, "plotly_chart",
                        lambda fig, **k: captured.setdefault("fig", fig))
    monkeypatch.setattr(st_mod, "caption", lambda *a, **k: None)

    days = [_d.date(2024, 1, 1) + _d.timedelta(days=i) for i in range(400)]
    series = {"spotify": [(x, 10) for x in days],
              "youtube": [(x, 3) for x in days if x >= days[300]]}
    assert pc.render_platform_chart(series, since=days[0], until=days[-1], step="day",
                                    mode="facets", key="late")
    hatched = [tr for tr in captured["fig"].data
               if getattr(tr, "legendgroup", None) == "__unmeasured__"
               and getattr(tr, "fill", None) == "toself"]
    assert not hatched, (
        "les facettes hachurent la préhistoire d'une plateforme. Chacune a son "
        "propre cadre : il n'y a rien à expliquer là où il n'y a rien à comparer.")


def test_only_one_legend_entry_names_the_absence(monkeypatch):
    """Une bande par trou, UNE entrée de légende. Sinon la légende compte les trous."""
    fig = _figure(monkeypatch, mode="absolute", step="day")
    assert fig is not None
    shown = [tr for tr in fig.data
             if getattr(tr, "legendgroup", None) == "__unmeasured__"
             and tr.showlegend]
    assert len(shown) == 1, (
        f"{len(shown)} entrées de légende pour l'absence — il en faut une, quel que "
        "soit le nombre d'intervalles non mesurés.")


def test_the_share_mode_does_not_inflate_the_platforms_that_are_present(monkeypatch):
    """Une part calculée sur un sous-ensemble est FAUSSE, pas approximative.

    Au pas où YouTube manque, Spotify comptait pour 100 % — ce qui affirme que
    YouTube a fait zéro. Le pas entier devient inconnu.
    """
    fig = _figure(monkeypatch, mode="share", step="day")
    assert fig is not None
    # Par ABSCISSE, jamais par position dans la liste : une plateforme est découpée
    # en tranches, donc ses traces ne portent que ses propres pas. Comparer deux
    # listes d'indices comparerait deux axes différents — la première version de ce
    # test le faisait et accusait une figure correcte.
    drawn: dict = {}
    for tr in fig.data:
        if getattr(tr, "legendgroup", None) == "__unmeasured__":
            continue
        for x, y in zip(tr.x or [], tr.y or []):
            if y is not None:
                drawn.setdefault(x, []).append((tr.name, y))
    assert drawn, "aucune part tracée"
    wrong = [(x, parts) for x, parts in drawn.items()
             if abs(sum(v for _, v in parts) - 100.0) > 0.5]
    assert not wrong, (
        f"{len(wrong)} pas où la somme des parts ne fait pas 100 % — par exemple "
        f"{wrong[0]}.\nUne part calculée sur les plateformes PRÉSENTES compte les "
        "absentes pour zéro : les présentes se partagent 100 % et rien ne le dit. "
        "Le pas entier doit devenir inconnu.")
    # Et l'invariant doit MORDRE : il faut bien qu'il y ait des pas non dessinés,
    # sinon « toutes les parts font 100 % » serait vrai d'une figure sans trou.
    assert len(drawn) < 90, (
        f"{len(drawn)} pas dessinés sur 90 alors qu'une plateforme en manque 40 : "
        "le mode part renseigne des pas qu'il ne peut pas connaître.")


# ── 2. Le cliquet sur les autres figures ────────────────────────────────────

# LE PRÉDICAT NE CHERCHE PAS « UN `fillna(0)` », IL CHERCHE LA CLASSE.
#
# La première version comptait tous les `.fillna(0)` des vues : **23 sur 11
# fichiers**, dont aucun n'était le défaut. Ils remplissent des CATÉGORIES — un
# pays sans dépense, un titre sans like, une probabilité ML absente — où zéro est
# une réponse et pas une invention. Un cliquet qui compte 23 sites sains pour en
# garder 4 apprend surtout que le rouge est du bruit.
#
# La classe est plus étroite et elle se nomme : **une trame ÉLARGIE sur un
# calendrier complet, puis bouchée avec des zéros**. Élargie se lit dans l'arbre —
# `pd.date_range` ou `reindex` — et c'est ce couple-là qui fabrique des jours qui
# n'ont jamais été mesurés. Sans l'élargissement, `fillna(0)` ne touche que des
# lignes qui existent.
#
# Granularité : la FONCTION. C'est grossier — `_show_meta_ads` fait 600 lignes et
# mélange une frise et trois Paretos — mais une granularité plus fine demanderait
# de suivre la variable d'une trame à travers ses réaffectations, et un prédicat
# qu'on ne sait pas écrire juste vaut moins qu'un plafond honnête.
#
# Les trois sites, MESURÉS le 2026-09-12 et lus un par un :
#
#   meta_ads_overview._show_meta_ads (6) — la frise quotidienne est corrigée
#       (réindexée, `NaN`, `connectgaps=False`). Les six restants sont les Paretos
#       pays / placement / âge : des catégories, pas des jours.
#   meta_creatives._render_creative_timeline (1) — c'est le PLANCHER DE SEAU, le
#       modèle que les autres copient : `_measured.reindex(...).fillna(0) >= 3.5`
#       marque les seaux trop peu mesurés pour être tracés. Le zéro y signifie
#       « zéro jour mesuré », ce qui est exactement vrai.
#   _tab_budget_roi._show_tab_budget_roi (2) — la valeur alimente un `cumsum`, pas
#       un axe : un jour sans dépense n'ajoute rien, et `NaN` effacerait toute la
#       suite de la courbe.
_WIDEN_AND_FILL: dict[str, int] = {
    "src/dashboard/views/meta_ads_overview.py:_show_meta_ads": 6,
    "src/dashboard/views/meta_creatives.py:_render_creative_timeline": 1,
    "src/dashboard/views/trigger_algo/_tab_budget_roi.py:_show_tab_budget_roi": 2,
}

_SCANNED = ("src/dashboard/views", "src/dashboard/utils")


def _widen_and_fill() -> dict[str, int]:
    """Par fonction : celles qui élargissent une trame ET la bouchent avec des zéros.

    Par AST, jamais par texte. Un `grep` compterait les mentions dans les
    commentaires — dont ceux qui EXPLIQUENT le correctif : documenter ferait rougir
    le garde, et la seule façon de le calmer serait d'arrêter de documenter. Ce
    dépôt a payé cette leçon le 2026-08-03.
    """
    out: dict[str, int] = {}
    for root in _SCANNED:
        for path in sorted((_ROOT / root).rglob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for fn in ast.walk(tree):
                if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                widens = any(
                    isinstance(n, ast.Call)
                    and getattr(n.func, "attr", "") in ("date_range", "reindex")
                    for n in ast.walk(fn))
                if not widens:
                    continue
                fills = sum(
                    1 for n in ast.walk(fn)
                    if isinstance(n, ast.Call)
                    and getattr(n.func, "attr", "") == "fillna"
                    and len(n.args) == 1
                    and isinstance(n.args[0], ast.Constant)
                    and n.args[0].value == 0)
                if fills:
                    out[f"{path.relative_to(_ROOT)}:{fn.name}"] = fills
    return out


def test_no_new_figure_fills_a_widened_calendar_with_zero() -> None:
    """Le cliquet. Il ne peut que descendre.

    Cinq fonctions élargissaient-et-bouchaient le 2026-09-12 au matin ; trois le
    soir, toutes trois justifiées ci-dessus. Ajouter un site suppose de le lire et
    de l'écrire là-haut, pas de monter un chiffre.
    """
    found = _widen_and_fill()
    new = {f: n for f, n in found.items() if f not in _WIDEN_AND_FILL}
    assert not new, (
        f"nouvelle(s) fonction(s) qui élargissent une trame puis la bouchent : "
        f"{new}.\nUn jour fabriqué par `date_range`/`reindex` puis rempli de zéro "
        "affirme « il ne s'est rien passé » là où la vérité est « on ne sait pas ». "
        "Laisser `NaN` et couper la série (`connectgaps=False`) — ou, si le zéro est "
        "juste (un `cumsum`, un compte de jours mesurés), l'écrire dans "
        "`_WIDEN_AND_FILL` avec sa raison.")
    grown = {f: (n, _WIDEN_AND_FILL[f]) for f, n in found.items()
             if n > _WIDEN_AND_FILL[f]}
    assert not grown, (
        f"le cliquet a été franchi (trouvé, plafond) : {grown}. Il ne monte pas.")


def test_the_ceiling_names_functions_that_still_exist() -> None:
    """Un plafond sans site élargit la règle en silence."""
    found = _widen_and_fill()
    stale = sorted(f for f in _WIDEN_AND_FILL if f not in found)
    assert not stale, (
        f"plafond(s) sans site : {stale}. Soit la fonction a disparu, soit ses "
        "`fillna(0)` ont été retirés — dans les deux cas l'entrée doit sortir, "
        "sinon elle autorise un retour silencieux.")


def test_the_fixed_sites_did_not_come_back() -> None:
    """Les cinq figures corrigées le 2026-09-12, nommées une par une.

    Le cliquet ci-dessus dirait seulement « rien de nouveau » si l'une d'elles
    reperdait son correctif d'une autre manière — un `or 0`, un `.fillna(0.0)` sur
    une ligne réécrite. Ces cinq-là ont coûté une lecture chacune ; elles sont
    nommées pour que la régression porte leur nom.
    """
    # Le COMPTE, pas la présence. La première version cherchait la chaîne
    # `_measured(` dans `pdf_charts` : elle y reste tant qu'une seule des quatre
    # courbes l'utilise, et la mutation qui en cassait une est restée VERTE. Un
    # marqueur partagé par plusieurs sites ne garde aucun d'eux.
    fixed = {
        # fichier -> (ce qu'on compte dans l'arbre, combien de fois)
        "src/dashboard/views/meta_x_spotify.py": ("connectgaps", 2),
        "src/dashboard/views/meta_ads_overview.py": ("connectgaps", 2),
        "src/dashboard/views/hypeddit.py": ("connectgaps", 1),
        # les 3 séries du PDF : audience S4A (×2) et YouTube (×2)
        "src/dashboard/utils/pdf_charts.py": ("_measured", 4),
    }
    short = []
    for path, (name, expected) in fixed.items():
        tree = ast.parse((_ROOT / path).read_text(encoding="utf-8"))
        if name == "_measured":
            seen = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call)
                       and getattr(n.func, "id", "") == "_measured")
        else:
            seen = sum(1 for n in ast.walk(tree) if isinstance(n, ast.keyword)
                       and n.arg == "connectgaps")
        if seen < expected:
            short.append(f"{path}: {seen} `{name}` au lieu de {expected}")
    assert not short, (
        "figure(s) qui ont reperdu leur correctif d'absence :\n" + "\n".join(short)
        + "\nChacune traçait un jour non mesuré comme un zéro avant le 2026-09-12.")
