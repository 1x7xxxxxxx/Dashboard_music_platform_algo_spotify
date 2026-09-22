"""Chaque livrable de la prestation déclare QUI fait le travail.

Type: Test
Uses: src.dashboard.utils.service_offer, ast (aucune base, aucun Streamlit)
Depends on: app.py (pages routables), stripe_schema.PLAN_CAPABILITIES
Persists in: nothing

⚠️ CE GARDE FERME UN TROU CONNU, ET IL EST NÉ D'UN DÉFAUT RÉEL.

Le 2026-09-21, la carte de l'abonnement Premium vendait « 🎬 Génération de créatives
vidéo (60+ par campagne) ». **Rien dans l'arbre ne produit de vidéo** — ni ffmpeg,
ni moviepy, ni aucun module de rendu. La promesse a tenu dix-sept jours.

`tests/test_the_plan_pitch_matches_the_gate.py:215` l'interdit désormais dans un
PLAN. Mais il ne regarde que `_PITCH` : jusqu'au 2026-09-22, **rien n'empêchait la
même promesse d'entrer dans le panneau de prestation**, dont la seule contrainte
mécanique était que les puces soient traduites.

Or l'interdire partout serait faux. Le propriétaire produit RÉELLEMENT des
créatives — à la main. La distinction que ce dépôt a écrite
(`database/stripe_schema.py:104-108`) est la bonne :

    ce que le CODE fait      → l'abonnement, et ça doit exister dans l'arbre
    ce que l'HUMAIN fait     → la prestation, et ça n'a rien à prouver dans le code

La propriété gardée ici n'est donc **pas** « interdire des mots » — ça condamnerait
le travail humain, qui est vrai. Elle est :

> **Chaque livrable déclare son agent. Un livrable `outil` doit nommer une page
> routable ou une capacité qui EXISTE, et ne peut porter aucun verbe de production.
> Un livrable `humain` doit porter un sujet — une première personne — et aucun
> vocabulaire d'automaticité.**

Ce que ce garde NE couvre PAS
------------------------------
(1) La VÉRACITÉ d'un engagement humain : que le propriétaire envoie vraiment son
export le lundi, aucun test ne peut le savoir. Le garde impose qu'il soit écrit
comme un engagement personnel, pas comme une fonction — c'est tout, et c'est déjà
ce qui manquait. (2) Le rendu : qu'une vue cache la pastille d'agent lui est
invisible. (3) Les autres surfaces de prix, gardées ailleurs.
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

from src.dashboard.utils.service_offer import (  # noqa: E402
    CLES_PRIX,
    LEVIERS,
    OPTIONS,
    Livrable,
    grille_complete,
)

# Le logiciel de ce dépôt LIT et AFFICHE ; il ne produit rien. Fait vérifié le
# 2026-09-21 (ni ffmpeg, ni moviepy, ni génération d'image nulle part), et
# re-vérifié le 2026-09-22 avant d'écrire l'offre.
_VERBES_DE_PRODUCTION = re.compile(
    r"génér|genere|génère|produi|fabriqu|crée\b|créat.{0,12}(?:automat|générée)", re.I)

# Emprunté à `tests/test_a_reward_is_not_promised_as_automatic.py:69` — on ne
# réécrit pas un prédicat qui existe, on le réutilise.
_VERBES = r"(?:appliqu|crédit|credit|envoy|débit|debit)"
_AUTOMATIQUE = re.compile(
    rf"(ser(?:a|ont)\s+{_VERBES}"
    rf"|{_VERBES}\w*\s+automatiquement"
    rf"|automatiquement\s+{_VERBES}"
    r"|automatically\s+(?:applied|credited|sent)"
    r"|will\s+be\s+(?:applied|credited|sent))", re.I)

# Un engagement humain porte un sujet. « Je », « J'», « Chaque lundi, je … ».
_PREMIERE_PERSONNE = re.compile(r"\b(?:je|j')\b", re.I)

_MONTANT = re.compile(r"€|\bEUR\b", re.I)


def _routable_pages() -> set[str]:
    """Les pages qu'un `?page=…` atteint — reprend le prédicat de l'autre garde."""
    tree = ast.parse((_ROOT / "src" / "dashboard" / "app.py").read_text(encoding="utf-8"))
    out: set[str] = set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.Compare)
                and isinstance(n.left, ast.Name) and n.left.id == "page"
                and len(n.comparators) == 1
                and isinstance(n.comparators[0], ast.Constant)
                and isinstance(n.comparators[0].value, str)):
            out.add(n.comparators[0].value)
    return out


def _capacites() -> set[str]:
    from src.database.stripe_schema import PLAN_CAPABILITIES

    return {c for lot in PLAN_CAPABILITIES.values() for c in lot}


def _tous_livrables() -> list[Livrable]:
    return [liv for opt in OPTIONS for liv in opt.livrables]


# ── Les contrôles ────────────────────────────────────────────────────────────

def test_every_deliverable_declares_an_agent():
    for liv in _tous_livrables():
        assert liv.agent in {"humain", "outil"}, (
            f"{liv.cle} : agent={liv.agent!r}. Sans agent, une ligne ne dit pas qui "
            "livre — et c'est exactement ainsi qu'un travail humain se déguise en "
            "fonction du produit."
        )


def test_a_tool_deliverable_names_something_that_exists():
    """LE contrôle anti-promesse-fausse."""
    atteignables = _routable_pages() | _capacites()
    for liv in _tous_livrables():
        if liv.agent != "outil":
            continue
        assert liv.ancre, f"{liv.cle} : livrable « outil » sans ancre nommée"
        assert liv.ancre in atteignables, (
            f"{liv.cle} vend « {liv.ancre} », qui n'est ni une page routable ni une "
            f"capacité déclarée. Atteignables : {sorted(atteignables)[:8]}…"
        )


def test_a_tool_deliverable_claims_no_production():
    """Le logiciel lit et affiche. Il ne produit rien — vérifié dans l'arbre."""
    for liv in _tous_livrables():
        if liv.agent != "outil":
            continue
        assert not _VERBES_DE_PRODUCTION.search(liv.texte), (
            f"{liv.cle} attribue une PRODUCTION au logiciel : « {liv.texte[:70]} ». "
            "Rien dans l'arbre ne génère d'image ni de vidéo (vérifié le "
            "2026-09-21). Si c'est un humain qui le fait, l'agent est « humain »."
        )


def test_no_tool_deliverable_speaks_in_the_first_person():
    """⚠️ TROUVÉ PAR UNE MUTATION DE CE GARDE, le 2026-09-22.

    J'ai basculé l'engagement du lundi — « Chaque lundi, **je** t'envoie ton export
    commenté » — de `humain` à `outil`, en gardant son texte. Le garde est resté
    VERT : `export_csv` est une page routable, et le texte ne porte aucun verbe de
    production. Les quatre contrôles « humain » ne s'exécutaient pas, puisque
    l'agent n'était plus « humain ».

    Un geste personnel pouvait donc être rebaptisé fonction du produit sans que
    rien ne le dise — c'est-à-dire la moitié du défaut que ce fichier existe pour
    fermer, prise dans l'autre sens.

    La propriété qui manquait est simple : **le logiciel ne dit pas « je ».**
    """
    for liv in _tous_livrables():
        if liv.agent != "outil":
            continue
        assert not _PREMIERE_PERSONNE.search(liv.texte), (
            f"{liv.cle} est déclaré « outil » et parle à la première personne : "
            f"« {liv.texte[:70]} ». Un logiciel ne dit pas « je » — si c'est un "
            "geste humain, l'agent doit être « humain », et les contrôles qui vont "
            "avec doivent s'appliquer."
        )


def test_a_human_deliverable_carries_a_subject():
    """« Je », pas une voix passive. Un engagement sans sujet se lit comme une fonction."""
    for liv in _tous_livrables():
        if liv.agent != "humain":
            continue
        assert _PREMIERE_PERSONNE.search(liv.texte), (
            f"{liv.cle} : « {liv.texte[:70]} » n'a pas de sujet. Un engagement "
            "humain s'écrit à la première personne, sinon il sonne comme une "
            "fonction du produit — le défaut exact du 2026-09-21."
        )


def test_a_human_deliverable_is_not_disguised_as_automatic():
    for liv in _tous_livrables():
        if liv.agent != "humain":
            continue
        assert not _AUTOMATIQUE.search(liv.texte), (
            f"{liv.cle} promet un automatisme : « {liv.texte[:70]} ». Aucun code ne "
            "l'exécute ; c'est un geste, et il doit se lire comme tel."
        )


def test_no_deliverable_carries_a_price():
    """Enns p. 16 : « keep your value drivers bundled and not à la carte ».

    Découper un service en parties tarifées permet la comparaison directe et tire
    les prix vers le bas. Les livrables se NOMMENT pour justifier le prix du lot.
    """
    for liv in _tous_livrables():
        assert not _MONTANT.search(liv.texte), (
            f"{liv.cle} porte un montant : « {liv.texte[:70]} ». Seule l'OPTION a un "
            "prix — c'est une propriété du schéma, pas une consigne de style."
        )
    assert not hasattr(Livrable, "prix"), "le schéma d'un livrable ne porte pas de prix"


def test_three_options_cheapest_first():
    assert len(OPTIONS) == 3, f"{len(OPTIONS)} options — Enns p. 29 en demande trois"
    assert [o.cle_prix for o in OPTIONS] == list(CLES_PRIX), (
        "l'ordre des options ne suit plus celui des clés de prix"
    )


def test_each_option_grows_in_scope():
    """La différence est de PÉRIMÈTRE, pas de qualité.

    Trois fois la même chose en plus gros n'est pas trois options : chaque colonne
    doit contenir strictement plus de livrables que la précédente.
    """
    tailles = [len(o.livrables) for o in OPTIONS]
    assert tailles == sorted(tailles) and len(set(tailles)) == 3, (
        f"périmètres : {tailles}. Ils doivent croître strictement."
    )


def test_the_grid_hides_until_all_three_prices_are_set():
    assert not grille_complete({})
    assert not grille_complete({CLES_PRIX[0]: "450"})
    assert not grille_complete({c: "" for c in CLES_PRIX})
    assert grille_complete({c: "450" for c in CLES_PRIX})


def test_the_levers_cost_nothing_and_are_named():
    assert len(LEVIERS) >= 3, "moins de trois leviers : l'offre n'a rien à offrir"
    for cle, texte in LEVIERS:
        assert cle.startswith("service.levier."), f"clé i18n inattendue : {cle}"
        assert texte.strip()


# ── Non-vacuité : le garde se prouve sur la forme EXACTE du défaut ───────────

def test_the_detector_sees_the_defect_it_was_written_for():
    """La ligne qui a menti dix-sept jours, réinjectée telle quelle."""
    faux = Livrable("outil", "meta_creatives", "service.liv.faux",
                    "🎬 Génération de créatives vidéo (60+ par campagne)")
    assert _VERBES_DE_PRODUCTION.search(faux.texte), (
        "le détecteur ne voit pas « Génération de créatives vidéo » attribuée au "
        "logiciel — c'est pourtant le défaut qui a fait écrire ce fichier"
    )


def test_the_corrected_form_does_not_redden():
    """La réciproque. Sans elle, corriger le défaut ferait échouer son propre garde."""
    vrai = Livrable("humain", None, "service.liv.vrai",
                    "Je produis les créatives et je les décline par hook")
    assert vrai.agent == "humain"
    assert _PREMIERE_PERSONNE.search(vrai.texte)
    assert not _AUTOMATIQUE.search(vrai.texte)
    # le verbe de production est LÉGITIME ici : c'est un humain qui produit
    assert _VERBES_DE_PRODUCTION.search(vrai.texte), (
        "le cas de test ne prouve rien : il ne contient pas de verbe de production"
    )


def test_the_first_person_detector_catches_the_relabelled_gesture():
    """Non-vacuité du contrôle ci-dessus, sur la mutation qui l'a fait écrire."""
    deguise = Livrable("outil", "export_csv", "service.liv.deguise",
                       "Chaque lundi, je t'envoie ton export commenté")
    assert deguise.agent == "outil"
    assert _PREMIERE_PERSONNE.search(deguise.texte), (
        "le détecteur ne voit pas la première personne dans un livrable « outil » — "
        "c'est le trou que la mutation du 2026-09-22 a révélé"
    )


@pytest.mark.parametrize("texte", [
    "CSV envoyé automatiquement chaque semaine",
    "Ton export sera envoyé chaque lundi",
    "Your export will be sent every Monday",
])
def test_the_automatic_detector_sees_a_disguised_gesture(texte):
    assert _AUTOMATIQUE.search(texte), f"non détecté : {texte!r}"


@pytest.mark.parametrize("texte", [
    "Chaque lundi, je t'envoie ton export commenté",
    "Je produis les créatives et je les décline par hook",
])
def test_an_honest_gesture_is_not_flagged(texte):
    """Le faux positif à écarter : « je t'envoie » n'est pas « sera envoyé »."""
    assert not _AUTOMATIQUE.search(texte), (
        f"« {texte} » est signalé comme un automatisme — le prédicat condamne le "
        "travail humain, qui est précisément ce qu'on vend ici"
    )
