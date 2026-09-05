"""Instagram et Meta Ads partagent un onglet — et la résolution ne dépend pas de lui.

Type: Test
Uses: live Postgres, ast
Depends on: views/credentials/_registry.py, _render.py, router.py
Persists in: —

Instagram a eu son propre onglet pendant une heure le 2026-09-05. Il est revenu dans
« 📱 Meta Ads / Insta » : sa configuration est liée à celle de Meta Ads — même ligne de
stockage, même jeton, même app — et deux onglets pour une seule configuration se
cherchent.

**Ce que l'épisode a laissé, et que ce fichier garde**, c'est le défaut qu'il a révélé :
la résolution du lien Instagram vivait dans la branche `if platform_key == 'meta'`. Le
jour où Instagram a eu son onglet, elle a cessé de tourner, l'URL est arrivée telle
quelle au contrôle de forme, et l'artiste a lu « Instagram Business Account ID
invalide : chiffres uniquement » sur un lien parfaitement valide.

C'est la même leçon que `_TAB_FOR_PLATFORM` le même soir : **déplacer un champ sans
déplacer ce qui le traite laisse un traitement qui ne s'applique plus.** Un test qui
n'aurait porté que sur « le champ est dans le bon onglet » ne l'aurait pas vu.
"""
import ast
from pathlib import Path

_RENDER = Path(__file__).resolve().parents[1] / "src/dashboard/views/credentials/_render.py"


def test_the_two_platforms_share_one_row():
    """Ce qui est gardé est le partage de la LIGNE, jamais le nombre d'onglets.

    Ce test exigeait « Instagram n'est pas un onglet ». Le 2026-09-05 au soir, la
    mesure a tranché l'inverse : `business_discovery` collecte un compte tiers sans
    aucun partage Meta, donc les deux configurations sont bien indépendantes et
    Instagram a repris son onglet. Un garde ancré sur une DISPOSITION suit les
    allers-retours de la disposition ; ancré sur l'invariant, il survit aux deux.

    L'invariant, lui, n'a pas bougé d'un cran : les deux identités s'écrivent dans
    la MÊME ligne `artist_credentials`, donc un enregistrement d'un côté ne doit
    jamais effacer l'autre — c'est ce que `SHARED_ROWS` et `merge_into_row` tiennent.
    """
    from src.dashboard.views.credentials._core import SHARED_ROWS
    from src.dashboard.views.credentials._registry import PLATFORMS
    from src.dashboard.views.credentials.router import platform_destination
    from src.utils.tenant_identity import storage_platform

    assert storage_platform("instagram") == storage_platform("meta") == "meta", (
        "les deux plateformes n'écrivent plus dans la même ligne : si c'est "
        "voulu, `SHARED_ROWS` et `merge_into_row` n'ont plus lieu d'être")
    assert "meta" in SHARED_ROWS, (
        "la ligne partagée n'est plus déclarée : un enregistrement d'un onglet "
        "REMPLACERAIT `extra_config` et effacerait l'identité de l'autre")

    owners = [k for k, info in PLATFORMS.items()
              if any(f["key"] == "ig_user_id" for f in info.get("fields", []))]
    assert owners == ["instagram"], (
        f"`ig_user_id` est saisissable depuis {owners} — une identité à deux "
        "endroits est une identité qu'on oublie de déplacer")
    assert platform_destination("instagram") == "tab:instagram"


def test_the_instagram_resolution_does_not_depend_on_the_tab():
    """LE défaut de l'épisode, gardé par sa forme et non par son symptôme.

    La résolution doit être conditionnée par la VALEUR (« un lien a-t-il été collé
    ? »), jamais par l'onglet. Sinon elle re-cesse de tourner au prochain
    déplacement, et le message d'erreur accusera de nouveau un lien valide.
    """
    fn = next(n for n in ast.walk(ast.parse(_RENDER.read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "_handle_save")

    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "instagram_user_id_from_handle"]
    assert calls, "`_handle_save` ne résout plus le lien Instagram"

    # Aucun `if platform_key == …` ne doit ENGLOBER cet appel.
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        mentions_tab = any(
            isinstance(c, ast.Compare)
            and getattr(c.left, "id", "") == "platform_key"
            for c in ast.walk(node.test)
        )
        if not mentions_tab:
            continue
        inside = [n for n in ast.walk(node) if isinstance(n, ast.Call)
                  and getattr(n.func, "id", "") == "instagram_user_id_from_handle"]
        assert not inside, (
            "la résolution Instagram est de nouveau enfermée dans une branche qui "
            "teste l'onglet : elle cessera de tourner au prochain déplacement du "
            "champ, et un lien valide sera refusé comme « chiffres uniquement »")


def test_a_throttle_is_named_as_temporary():
    """« Meta n'a pas répondu » se lit « mon compte ne marche pas ».

    Un throttle est passager et l'artiste n'a rien à corriger. Les codes sont les
    mêmes que ceux que `collectors/_meta_retry.py` reconnaît — deux couches, un seul
    vocabulaire.
    """
    from src.utils.meta_graph import MetaGraphError

    for code in (4, 17, 32, 613):
        err = MetaGraphError(code, None, "brut")
        assert err.is_throttled, f"le code {code} n'est plus lu comme une limitation"
        assert "réessaie" in err.explanation.lower(), (
            f"le message du code {code} ne dit pas que c'est temporaire")
    assert not MetaGraphError(190, None, "x").is_throttled
