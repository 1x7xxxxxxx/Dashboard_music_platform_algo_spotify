"""Guard: une liste vide dit POURQUOI elle est vide — mesuré, pas supposé.

Type: Utility
Uses: ast, src.utils.meta_campaign_diagnosis
Triggers: pytest
Persists in: nothing

Error class `empty-list-blames-the-most-common-cause`.

Le 2026-09-06, un artiste dont Meta était branché — pastille verte, sonde OK,
224 lignes d'insights, collecte lancée vingt minutes plus tôt et retournée
`success` avec 879 lignes — a lu sur l'onglet Mapping :

    « Aucune campagne. Connecte Meta Ads dans 🔑 Credentials API, puis lance
      🚀 Lancer TOUTES les collectes dans la barre latérale. »

Les deux gestes demandés étaient faits. Le message n'avait rien mesuré : il
énonçait la cause la plus fréquente d'une liste vide comme si c'était la seule.

Il y en avait cinq, et deux ne demandent aucun geste. La vraie, ce soir-là :
`meta_campaigns` a pour clé de conflit `campaign_id` SEUL — délibérément, sa clé
primaire porte quinze clés étrangères et un upsert ne transfère jamais la
propriété d'une ligne. Deux profils déclarant le MÊME compte publicitaire se
partagent donc les identifiants, et le second n'en reçoit aucun.
"""
from __future__ import annotations

import ast
import functools
import pathlib

import pytest

from src.utils.meta_campaign_diagnosis import (
    CAMPAIGNS_ELSEWHERE,
    NEVER_RAN,
    NO_CAMPAIGN_AT_ALL,
    NO_IDENTITY,
    RUN_FAILED,
    SANDBOX_SHARES_ACCOUNT,
    diagnose_empty_campaigns,
)

_VIEW = pathlib.Path("src/dashboard/views/meta_mapping/_campaigns.py")


@functools.lru_cache(maxsize=1)
def _tree() -> ast.Module:
    return ast.parse(_VIEW.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "identity,status,insights,sandbox,expected",
    [
        (False, None,        0,   False, NO_IDENTITY),
        (False, "success", 224,   False, NO_IDENTITY),   # l'identité prime sur tout
        (True,  None,        0,   False, NEVER_RAN),
        (True,  "failed",    0,   False, RUN_FAILED),
        (True,  "success",   0,   False, NO_CAMPAIGN_AT_ALL),
        # LE CAS RÉEL du 2026-09-06 : la collecte a réussi ET des chiffres sont
        # arrivés, donc l'API répond pour ce compte — mais aucune campagne n'est
        # rattachée à ce profil.
        (True,  "success", 224,   False, CAMPAIGNS_ELSEWHERE),
        # LE CAS RÉEL du 2026-09-08, et le seul qui puisse encore se produire : deux
        # VRAIS locataires sont bloqués à la saisie par le garde d'identité ; le bac
        # à sable en est exempté par construction, donc il déclare toujours le compte
        # du profil principal et n'obtient jamais une campagne.
        (True,  "success", 224,   True,  SANDBOX_SHARES_ACCOUNT),
        # Le drapeau ne fabrique pas une cause : sans lignes d'insights, la question
        # reste « ce compte a-t-il des campagnes », pas « à qui sont-elles ».
        (True,  "success",   0,   True,  NO_CAMPAIGN_AT_ALL),
    ],
)
def test_each_cause_is_distinguished(identity, status, insights, sandbox, expected):
    assert diagnose_empty_campaigns(
        identity_present=identity, last_run_status=status, insight_rows=insights,
        is_sandbox=sandbox,
    ) == expected


def test_the_view_asks_the_diagnosis_everywhere_it_says_empty():
    """Les TROIS surfaces qui annonçaient une liste vide doivent la mesurer.

    Il y en avait trois, avec trois textes différents dont deux sous la MÊME clé
    i18n `meta_mapping.no_campaigns` — une clé, deux sens, et l'anglais n'en
    traduisait qu'un. Aucune ne peut rester sur un message écrit d'avance.
    """
    fn = next(n for n in ast.walk(_tree())
              if isinstance(n, ast.FunctionDef) and n.name == "render_campaign_tab")
    calls = [n for n in ast.walk(fn)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_empty_campaigns_message"]
    assert len(calls) >= 3, (
        f"seulement {len(calls)} surface(s) demandent le diagnostic. Les trois — "
        "suggestions vides, backlog vide, saisie manuelle sans campagne — "
        "annonçaient une liste vide, et chacune accusait l'artiste d'un geste "
        "qu'il avait déjà fait."
    )


def test_the_accusing_sentence_is_gone():
    """Le texte d'origine nommait deux gestes déjà faits, et une table interne."""
    src = _VIEW.read_text(encoding="utf-8")
    for banned, why in [
        ("Connecte Meta Ads dans", "demande de connecter ce qui est déjà connecté"),
        ("Lancez d'abord le DAG", "demande de lancer un DAG que l'artiste ne peut pas lancer"),
        ("dans `meta_campaigns`", "nomme une table interne à l'artiste"),
    ]:
        assert banned not in src, f"{banned!r} : {why}"


def test_a_success_needs_something_to_succeed_on():
    """« Toutes les campagnes sont traitées » sur zéro campagne est un succès vide.

    L'artiste l'a lu juste au-dessus du message qui lui demandait de connecter
    Meta : deux affirmations contradictoires sur le même écran.
    """
    fn = next(n for n in ast.walk(_tree())
              if isinstance(n, ast.FunctionDef) and n.name == "render_campaign_tab")
    for node in ast.walk(fn):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "success"
                and "auto_done" in ast.unparse(node)):
            break
    else:
        pytest.fail("le message `auto_done` a disparu — garde à repointer")

    guarded = [n for n in ast.walk(fn)
               if isinstance(n, ast.If)
               and "_load_campaigns" in ast.unparse(n.test)
               and "auto_done" in ast.unparse(n.body)]
    assert guarded, (
        "`auto_done` n'est pas conditionné à l'existence d'au moins une campagne : "
        "il annonce que tout est traité alors que rien ne l'a été."
    )
