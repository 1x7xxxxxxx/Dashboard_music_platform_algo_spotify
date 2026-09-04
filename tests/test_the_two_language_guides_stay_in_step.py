"""Le guide français et le guide anglais décrivent la MÊME procédure.

Type: Test
Uses: credential_guides (FR), credential_guides_en (EN), le catalogue i18n
Depends on: src/dashboard/content/credential_guides*.py,
    src/dashboard/utils/i18n_catalog/credentials.py
Persists in: nothing

Le défaut, deux fois en deux jours
-----------------------------------
2026-09-04, SoundCloud : le catalogue anglais décrivait encore « affiche le code
source de /discover et cherche `soundcloud:users:` » — une procédure abandonnée la
veille côté français.

Le même jour, Spotify : la source anglaise (`credential_guides_en.py`) portait TROIS
étapes quand le français en avait une seule. Elle était restée à l'ancienne version
tout un lot parce qu'un `str.replace` sans assertion n'avait pas mordu et n'avait rien
dit. Le catalogue de traduction masquait l'écart à l'écran ; le PDF anglais, lui, est
rendu depuis cette source, et portait encore trois étapes.

Trois surfaces pour un guide — la source FR, la source EN, et le catalogue EN que le
rendu PRÉFÈRE aux deux — et rien ne les comparait. Réécrire l'une laisse les autres en
place, et personne ne les relit : elles ne sont jamais rouges.

Ce que ce fichier affirme
-------------------------
Que les trois disent la même PROCÉDURE : même nombre d'étapes, mêmes captures aux
mêmes rangs, même présence ou absence d'intro. Il ne compare pas les mots — c'est une
traduction, elle doit différer — mais la forme, qui ne peut pas différer sans qu'un
des trois soit périmé.
"""
from __future__ import annotations

import pytest

from src.dashboard.content.credential_guides import CREDENTIAL_GUIDES
from src.dashboard.content.credential_guides_en import CREDENTIAL_GUIDES_EN
from src.dashboard.utils.i18n_catalog.credentials import EN

_FR = {g.key: g for g in CREDENTIAL_GUIDES}
_EN = {g.key: g for g in CREDENTIAL_GUIDES_EN}


def test_both_languages_cover_the_same_platforms():
    assert set(_FR) == set(_EN), (
        f"un guide existe dans une langue et pas dans l'autre : "
        f"FR={sorted(_FR)} EN={sorted(_EN)}")
    assert _FR, "aucun guide chargé — ce fichier ne prouverait rien"


@pytest.mark.parametrize("key", sorted(_FR))
def test_the_two_sources_describe_the_same_number_of_steps(key):
    """Un écart de comptage EST un guide périmé — jamais une nuance de traduction."""
    fr, en = _FR[key], _EN[key]
    assert len(fr.steps) == len(en.steps), (
        f"{key} : {len(fr.steps)} étape(s) en français, {len(en.steps)} en anglais. "
        "L'une des deux sources n'a pas suivi la réécriture de l'autre — et le PDF "
        "de chaque langue est rendu depuis SA source, donc l'écart est livré."
    )


@pytest.mark.parametrize("key", sorted(_FR))
def test_the_screenshots_sit_at_the_same_ranks(key):
    """Une capture illustre une étape : elle doit illustrer LA MÊME des deux côtés."""
    fr_shots = [s.screenshot for s in _FR[key].steps]
    en_shots = [s.screenshot for s in _EN[key].steps]
    assert fr_shots == en_shots, (
        f"{key} : les captures ne sont pas aux mêmes rangs.\n  FR {fr_shots}\n  EN "
        f"{en_shots}\nUn lecteur anglophone verrait l'image d'une autre étape.")


@pytest.mark.parametrize("key", sorted(_FR))
def test_an_intro_exists_in_both_languages_or_neither(key):
    """`intro=None` est une décision de rédaction, pas une nuance de langue."""
    assert bool((_FR[key].intro or "").strip()) == bool((_EN[key].intro or "").strip()), (
        f"{key} : une seule des deux langues porte une intro. Elle a été retirée d'un "
        "côté et oubliée de l'autre — le lecteur des deux versions lit deux guides.")


@pytest.mark.parametrize("key", sorted(_FR))
def test_the_catalog_does_not_describe_more_steps_than_the_source(key):
    """Le catalogue est PRÉFÉRÉ à la source : une clé de trop EST le guide anglais.

    `credential_guides_st._render_step` fait `t(f"credentials.guide.{k}.step_{n}",
    step.text)`. Une clé `step_3` survivant à un guide qui n'a plus que deux étapes
    n'est jamais rendue — mais une clé `step_2` survivant à un guide d'UNE étape non
    plus, et c'est le cas dangereux : on croit avoir traduit, la traduction est morte,
    et la seule preuve serait de lire l'écran en anglais.
    """
    n_steps = len(_FR[key].steps)
    orphans = sorted(
        k for k in EN
        if k.startswith(f"credentials.guide.{key}.step_")
        and k.split("step_")[1].split("_")[0].isdigit()
        and int(k.split("step_")[1].split("_")[0]) > n_steps
    )
    assert not orphans, (
        f"{key} n'a que {n_steps} étape(s), et ces traductions décrivent des étapes "
        f"qui n'existent plus : {orphans}. Elles ne sont jamais rendues — donc jamais "
        "relues, et jamais rouges.")
