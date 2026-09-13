"""La figure dit ce qui précède notre première mesure, et que c'est définitif.

Type: Test
Uses: pytest, ast
Depends on: src/dashboard/utils/platform_chart_notes.py, src/dashboard/utils/platform_chart.py
Persists in: nothing

Ce qui a été demandé, et le défaut derrière (2026-09-13)
--------------------------------------------------------
« qu'on ne montre pas qu'on n'a pas accès aux datas historiques de soundcloud et
spotify ».

L'accueil déployait **quatre** surfaces d'absence pour YouTube et SoundCloud — la
bande hachurée « ▨ Aucune mesure », le survol « pas encore collectée », la note des
écoutes non traçables, la note de démarrage tardif — pour **0,4 % du signal**
(ADR-025), et aucune ne disait la seule chose utile : que cet historique est
**définitivement** hors de portée. ADR-024 l'a établi — ces plateformes ne rendent
qu'un compteur à vie, aucune API ni aucun export CSV ne redonne le détail par jour.

L'écran exhibait donc une impuissance au lieu de la nommer.

Les deux moitiés du fait, et pourquoi elles sont séparées
---------------------------------------------------------
`render_collection_start_note` dit **depuis quand** (« 🎬 YouTube mesurée depuis
29/11/25 »). `render_counter_history_note`, juste après, dit **combien précède** et
**pourquoi ce sera toujours le cas**. Les deux lisent `cumulative`, déjà en main :
aucune requête neuve, et le plafond de 13 allers-terours de l'accueil est intact.

Ce que ce garde exige
---------------------
1. la note NOMME les deux nombres, et ils sont **dérivés des niveaux**, pas écrits ;
2. elle se TAIT quand il n'y a rien à dire — un premier niveau à zéro veut dire que
   la plateforme est prise depuis son origine. Lui inventer une antériorité serait
   le symétrique exact du défaut qu'on corrige, et c'est la mutation qui a été vue
   rouge avant d'écrire ce fichier ;
3. elle est RÉELLEMENT APPELÉE par la figure — vérifié par `ast`, pas par une
   recherche de texte : trois gardes de ce dépôt ont été pris au vert sur la prose
   de leur propre correctif le 2026-09-04.
"""
from __future__ import annotations

import ast
import datetime as _d
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent


@pytest.fixture()
def said(monkeypatch):
    """Ce que la note a réellement écrit à l'écran."""
    import src.dashboard.utils.platform_chart_notes as notes

    out: list[str] = []
    monkeypatch.setattr(notes.st, "caption",
                        lambda text, *a, **k: out.append(str(text)))
    return out


_LABELS = {"youtube": "🎬 YouTube", "soundcloud": "☁️ SoundCloud"}


def _levels(youtube_first: int, soundcloud_first: int) -> dict:
    """Des niveaux cumulés plausibles : un premier relevé, puis un plus récent."""
    d0, d1 = _d.date(2025, 11, 29), _d.date(2026, 9, 12)
    return {"youtube": [(d0, youtube_first), (d1, youtube_first + 304)],
            "soundcloud": [(d0, soundcloud_first), (d1, soundcloud_first + 86)]}


def test_the_note_names_what_precedes_our_first_measurement(said) -> None:
    """Les nombres viennent des NIVEAUX, et les deux plateformes sont nommées."""
    from src.dashboard.utils.platform_chart_notes import render_counter_history_note

    render_counter_history_note(_levels(118_032, 23_403), _LABELS)

    assert len(said) == 1, f"attendu UNE note, obtenu {len(said)} : {said}"
    text = said[0]
    # L'espace fine insécable est le séparateur de milliers du dépôt.
    assert "118 032" in text, (
        f"l'antériorité YouTube n'est pas dans la note : {text!r}")
    assert "23 403" in text, (
        f"l'antériorité SoundCloud n'est pas dans la note : {text!r}")
    assert "🎬 YouTube" in text and "☁️ SoundCloud" in text, (
        f"une plateforme à compteur n'est pas nommée : {text!r}")


def test_the_numbers_are_read_from_the_levels_not_written(said) -> None:
    """Changer les niveaux change la note — sinon le nombre serait une constante.

    Sans cette assertion, une note qui écrirait « 118 032 » en dur passerait le test
    précédent. C'est la forme que ce dépôt appelle un prédicat sans site.
    """
    from src.dashboard.utils.platform_chart_notes import render_counter_history_note

    render_counter_history_note(_levels(7, 9), _LABELS)

    assert said and "7" in said[0] and "9" in said[0], (
        f"la note ne suit pas les niveaux qu'on lui passe : {said!r}")
    assert "118" not in said[0], (
        f"la note porte un nombre qui ne vient pas de ses données : {said[0]!r}")


@pytest.mark.parametrize("levels, why", [
    ({}, "aucune plateforme à compteur"),
    ({"youtube": []}, "une plateforme sans le moindre relevé"),
    ({"youtube": [(_d.date(2025, 11, 29), 0), (_d.date(2026, 9, 12), 304)]},
     "une plateforme prise depuis son origine — premier niveau à ZÉRO"),
])
def test_the_note_says_nothing_when_there_is_nothing_to_say(said, levels, why) -> None:
    """L'absence d'antériorité ne s'affiche pas comme une antériorité de zéro.

    ⚠️ C'EST LA MUTATION QUI A ÉTÉ VUE ROUGE. En remplaçant le prédicat
    `if before and before > 0` par un `if True`, le troisième cas rend « **0**
    écoutes précèdent notre première mesure » — une phrase qui affirme un manque
    inexistant, sur la surface même qui existe pour distinguer l'absence du zéro.
    """
    from src.dashboard.utils.platform_chart_notes import render_counter_history_note

    render_counter_history_note(levels, _LABELS)

    assert said == [], f"la note parle alors qu'il y a {why} : {said!r}"


def test_only_the_platforms_with_prior_history_are_named(said) -> None:
    """Une plateforme prise depuis l'origine n'entre pas dans la phrase."""
    from src.dashboard.utils.platform_chart_notes import render_counter_history_note

    levels = _levels(118_032, 23_403)
    levels["soundcloud"] = [(_d.date(2025, 12, 16), 0),
                            (_d.date(2026, 9, 12), 86)]
    render_counter_history_note(levels, _LABELS)

    assert len(said) == 1
    assert "🎬 YouTube" in said[0]
    assert "☁️ SoundCloud" not in said[0], (
        "SoundCloud est nommée alors qu'elle n'a aucune antériorité : "
        f"{said[0]!r}")


def test_the_figure_actually_calls_the_note() -> None:
    """Une note que rien n'appelle est du texte correct que rien n'atteint.

    Par `ast` et non par `in source` : un commentaire citant l'appel satisfait une
    recherche de texte, et `test_a_guard_reads_structure_not_text` a déjà attrapé
    cette forme deux fois dans la même séance.
    """
    tree = ast.parse((_ROOT / "src" / "dashboard" / "utils"
                      / "platform_chart.py").read_text(encoding="utf-8"))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "render_counter_history_note" in called, (
        "`platform_chart` n'appelle pas `render_counter_history_note` : la note "
        "existe mais aucune figure ne la rend.")


def test_the_dead_no_op_is_gone() -> None:
    """`MISSING_HISTORY` bouclait sur un dict vide à chaque rendu de l'accueil.

    Elle n'a pas été recyclée pour porter la note : son contrat était « nomme ce qui
    n'a PAS de série », et YouTube comme SoundCloud en ont une. La remplir aurait
    écrit le contraire du code d'à côté.
    """
    import src.dashboard.utils.platform_chart_notes as notes
    import src.dashboard.utils.platform_timeseries as pts

    assert not hasattr(pts, "MISSING_HISTORY"), (
        "`MISSING_HISTORY` est revenue : un dict vide dont une fonction fait le "
        "tour à chaque rendu.")
    assert not hasattr(notes, "render_missing_history_note"), (
        "`render_missing_history_note` est revenue — le no-op que la note "
        "remplace.")
