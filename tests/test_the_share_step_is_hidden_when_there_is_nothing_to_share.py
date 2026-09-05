"""L'app ne demande pas un geste que Meta rend impossible.

Le 2026-09-05, un artiste a suivi « colle notre numéro dans Attribuer un
partenaire » sur un compte publicitaire que **notre propre Business possède
déjà**. Meta exclut du sélecteur de partenaires le business propriétaire : le
numéro était introuvable. L'app affirmait « il faut partager » sans jamais
regarder si le partage était acquis, alors que trois arêtes Graph le disent.

Deux choses sont gardées ici, et la seconde est celle qui a cassé :

1. Le bloc se TAIT quand l'état est `owned`, `accepted` ou `pending` — et il ne
   se tait pas sur `absent` ni sur `unknown`, parce qu'une lecture ratée ne
   prouve aucune absence de partage (`probe-reads-unreadable-as-absent`).
2. Aucune surface ne nomme l'onglet « Partenaires » d'un COMPTE publicitaire
   comme l'endroit où l'on AJOUTE un partenaire. Cet écran gère l'existant ; son
   champ de recherche filtre la liste. Le chemin qui ajoute passe par les
   partenaires du Business.
"""
import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
_META = _ROOT / "src/dashboard/views/credentials/_platform_meta.py"

# Les surfaces qui parlent du partage à un lecteur — guide, onglet, catalogue.
_SPEAKING = (
    "src/dashboard/views/credentials/_platform_meta.py",
    "src/dashboard/content/credential_guides.py",
    "src/dashboard/content/credential_guides_en.py",
    "src/dashboard/utils/i18n_catalog/credentials.py",
)


@pytest.mark.parametrize("state,speaks", [
    ("owned", False), ("accepted", False), ("pending", False),
    ("absent", True), ("unknown", True),
])
def test_the_block_speaks_only_when_the_share_is_still_owed(monkeypatch, state, speaks):
    """Rendu réel : le numéro n'apparaît que si le partage reste à faire."""
    from streamlit.testing.v1 import AppTest

    src = f"""
import sys; sys.path.insert(0, {str(_ROOT)!r}); sys.path.insert(0, {str(_ROOT / 'src/dashboard')!r})
import src.dashboard.views.credentials._platform_meta as m
m._share_state_cached = lambda account_id: {state!r}
m.render_partner_share_block("567214713853881")
"""
    at = AppTest.from_string(src)
    at.run(timeout=60)
    assert not at.exception, f"le bloc a levé sur l'état {state}"

    from src.dashboard.content.credential_guides import META_BUSINESS_ID
    if not META_BUSINESS_ID:
        pytest.skip("META_BUSINESS_ID absent de cet environnement")

    shown = [c.value for c in at.code]
    assert (META_BUSINESS_ID in shown) is speaks, (
        f"état {state} : le numéro est {'absent' if speaks else 'affiché'} alors "
        f"qu'il devrait être {'affiché' if speaks else 'tu'}"
    )


def test_an_unreadable_state_never_claims_the_share_is_done(monkeypatch):
    """`unknown` doit valoir « je ne sais pas », jamais « c'est fait ».

    La branche muette est un aveu de succès (`✅`). L'y faire tomber sur une
    lecture ratée dirait à l'artiste que son partage est en place alors que rien
    ne l'a vérifié — et il attendrait des chiffres qui ne viendraient pas.

    Ce test est passé sur son propre mutant à la première écriture : sans
    `META_BUSINESS_ID`, `share_state` sort AVANT le moindre appel Graph et rend
    `unknown` pour une tout autre raison. D'où le business id posé ici, et le
    compteur : on exige que la branche d'erreur ait bien été atteinte.
    """
    import src.utils.meta_graph as graph
    import src.utils.meta_partner as mp

    monkeypatch.setenv("META_BUSINESS_ID", "212173878482503")
    calls = []

    def _throttled(path, token=None, **params):
        calls.append(path)
        raise graph.MetaGraphError(4, None, "(#4) Application request limit reached")

    monkeypatch.setattr(mp, "get", _throttled)

    assert mp.share_state("567214713853881") == "unknown"
    assert calls, "la branche d'erreur n'a jamais été atteinte — garde aveugle"


def test_no_surface_calls_the_ad_account_partners_tab_the_place_to_add():
    """Le mauvais écran ne doit revenir dans AUCUNE des quatre surfaces.

    Lu sur le TEXTE volontairement : ce sont des chaînes destinées à un lecteur,
    et c'est le texte qui l'a envoyé au mauvais endroit. Un AST ne dirait rien de
    plus ici — mais on ignore les commentaires, qui expliquent justement l'erreur.
    """
    faulty = []
    for rel in _SPEAKING:
        path = _ROOT / rel
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            text = node.value
            if "settings/ad-accounts" in text:
                faulty.append(f"{rel}:{node.lineno} envoie vers l'écran des comptes")
            if "Attribuer un partenaire" in text or "Assign partner" in text:
                faulty.append(f"{rel}:{node.lineno} nomme le bouton de l'écran de gestion")
    assert not faulty, (
        "l'onglet « Partenaires » d'un compte publicitaire GÈRE les attributions ; "
        "il n'en ajoute pas :\n  " + "\n  ".join(faulty)
    )
