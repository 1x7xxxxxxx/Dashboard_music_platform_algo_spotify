"""Ce que la mise en route demande à l'artiste — et ce qu'elle a cessé de demander.

Type: Test
Uses: os_hints (pur), tenant_identity (pur), credential_guides
Depends on: src/dashboard/utils/os_hints.py, src/utils/tenant_identity.py,
    src/dashboard/content/credential_guides*.py
Persists in: nothing

Trois demandes du 2026-09-04, trois gardes. Elles ont la même forme : la page posait
à l'artiste une question dont elle connaissait déjà la réponse.

  1. **Le sélecteur d'OS** s'affichait en tête de CHAQUE onglet de credentials, au
     dessus du seul champ à remplir — alors que plus aucun des quatre guides ne
     contient d'instruction dépendant du clavier. « Supprime l'instruction adaptée
     macOS quand on en a pas besoin : ici pas de commande avec le clavier. » Le garde
     ne vérifie PAS son absence (ce serait figer le contenu d'aujourd'hui) : il
     vérifie la RÈGLE — le sélecteur suit les jetons, dans les deux sens.

  2. **`act=`** : « on ne peut pas récupérer nous-même le n° act ? Précise si on doit
     rentrer act_n° ou uniquement le n°, c'est confus. » On ne peut pas le récupérer
     — le token est celui de la plateforme, et lister les comptes qu'il voit
     exposerait ceux des autres locataires. Mais on peut accepter l'URL entière, ce
     qui supprime le découpage à la main ET la question du préfixe.

  3. **Le guide dit où coller**, pas « ci-dessous ». Le guide est rendu SOUS le
     formulaire depuis 2026-08-30 ; « colle-le ci-dessous » désignait donc le statut
     du DAG. Une direction relative ne survit pas au déplacement du bloc qu'elle
     désigne, et le PDF n'a ni dessus ni dessous.
"""
from __future__ import annotations

import pytest

from src.dashboard.content.credential_guides import CREDENTIAL_GUIDES
from src.dashboard.content.credential_guides_en import CREDENTIAL_GUIDES_EN
from src.dashboard.content.credential_guides_st import _needs_os_selector
from src.dashboard.utils.os_hints import has_os_tokens
from src.utils.tenant_identity import (
    malformed_meta_accounts,
    normalise_meta_account,
)


def _all_guides():
    return [("fr", g) for g in CREDENTIAL_GUIDES] + \
           [("en", g) for g in CREDENTIAL_GUIDES_EN]


# ── 1. Le sélecteur d'OS suit les jetons ────────────────────────────────────

def test_has_os_tokens_ignores_a_token_that_renders_the_same_on_both():
    """Un jeton dont les deux rendus sont identiques ne justifie pas un choix.

    C'est la moitié subtile de la règle : proposer « Windows / macOS » pour obtenir
    deux fois la même phrase est un contrôle qui ne change rien, exactement ce que la
    remarque visait.
    """
    assert has_os_tokens("appuie sur {{COPY}}") is True
    assert has_os_tokens("rien de particulier") is False
    assert has_os_tokens("") is False
    # `{{NOPE}}` n'est pas dans la table : inconnu ⇒ pas de sélecteur.
    assert has_os_tokens("{{NOPE}}") is False


def test_the_os_selector_follows_the_guides_content_in_both_directions():
    """Un guide sans jeton ⇒ pas de sélecteur. Avec jeton ⇒ sélecteur.

    Les deux sens comptent. Sans le second, retirer le sélecteur « parce qu'il ne
    sert plus » reviendrait à recréer le défaut d'origine — un artiste sur Mac lisant
    `Ctrl+U` sans aucun moyen de corriger — le jour où un guide redemande un
    raccourci.
    """
    for lang, guide in _all_guides():
        expected = has_os_tokens(
            guide.intro or "", guide.note or "", guide.admin_note or "",
            *[s.text or "" for s in (guide.steps or ())],
            *[f.note or "" for f in (guide.fields or ())],
        )
        assert _needs_os_selector(guide) is expected, (
            f"{lang}/{guide.key}: le sélecteur d'OS et le contenu du guide ne disent "
            "pas la même chose"
        )


def test_the_scope_covers_the_intro_not_only_the_steps():
    """Le prédicat lit la MÊME prose que le rendu.

    Un prédicat qui ne regarderait que `steps` laisserait un raccourci dans l'intro
    sans son sélecteur — le défaut d'origine, à l'envers. C'est la leçon
    « la portée d'un garde est le défaut », appliquée au prédicat lui-même.
    """
    from src.dashboard.content.credential_guides import CredStep, PlatformCred

    only_in_intro = PlatformCred(
        key="x", title="X", icon="x", intro="fais {{FIND}} sur la page",
        portal_url="https://example.test", steps=(CredStep("rien"),), fields=(),
    )
    assert _needs_os_selector(only_in_intro), (
        "un raccourci dans l'intro doit suffire à faire apparaître le sélecteur"
    )


# ── 2. `act=` : l'URL entière suffit, le préfixe est indifférent ─────────────

@pytest.mark.parametrize("typed", [
    "https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=123456789012345&business_id=9",
    "adsmanager.facebook.com/adsmanager/manage/campaigns?business_id=9&act=123456789012345",
    "act_123456789012345",
    "123456789012345",
    "  123456789012345  ",
])
def test_every_shape_the_guide_promises_yields_the_same_account(typed):
    """Le guide dit « les deux marchent » et « l'URL entière convient ». Preuve."""
    assert normalise_meta_account(typed) == "act_123456789012345"


def test_a_url_without_act_is_refused_rather_than_guessed():
    """Pas d'`act=` ⇒ pas de compte. Jamais un identifiant inventé.

    Un lien de Business Manager porte `business_id=…`, que le guide désigne
    justement comme la confusion à éviter. Le rattraper en enregistrant ce
    numéro-là donnerait une ligne qui a l'air remplie et ne collectera jamais rien —
    pire qu'un refus, parce que toutes les surfaces qui comptent des lignes la
    liraient comme « connecté ».
    """
    bm_link = "https://business.facebook.com/settings/ad-accounts?business_id=99999"
    assert malformed_meta_accounts({"account_id": bm_link}), (
        "un lien sans act= doit être refusé, pas transformé en compte publicitaire"
    )


def test_business_id_is_never_mistaken_for_the_ad_account():
    """Le motif exige le nom de paramètre complet, pas la sous-chaîne « act »."""
    assert normalise_meta_account(
        "https://x.test/?business_id=123456789012345") != "act_123456789012345"
    assert normalise_meta_account("https://x.test/?contact=42") != "act_42"


# ── 3. Le guide dit OÙ coller ───────────────────────────────────────────────

def test_no_guide_step_points_below_itself():
    """« ci-dessous » / « below » ne désigne plus rien depuis que le guide est sous
    le formulaire — et n'a jamais rien désigné dans le PDF."""
    offenders = []
    for lang, guide in _all_guides():
        for i, step in enumerate(guide.steps, 1):
            text = (step.text or "").lower()
            if "ci-dessous" in text or "paste it below" in text:
                offenders.append(f"{lang}/{guide.key} étape {i}")
    assert not offenders, (
        "Ces étapes envoient l'artiste « ci-dessous », où se trouve le statut du "
        f"DAG et non le formulaire : {offenders}. Nomme la page et l'encadré — "
        "c'est la seule formulation qui reste vraie dans le PDF."
    )


# ── 4. Le guide est À CÔTÉ du champ, donc il ne dit plus où est le champ ─────

def test_the_guide_never_describes_where_the_reader_already_is():
    """Depuis le 2026-09-04 le guide est la colonne de DROITE du formulaire.

    Trois formulations en trois jours pour la même étape, chacune décrivant OÙ
    coller, chacune devenue fausse ou redondante quand le formulaire a bougé :

      « Colle-le ci-dessous »          → dessous, c'est le statut du DAG ;
      « page Credentials API → Spotify,
        encadré Saisir tes identifiants » → exact, et on le dit à quelqu'un qui est
                                            déjà dessus, le champ à sa gauche.

    Une étape doit nommer le CHAMP — la seule chose à savoir, et la seule qui ne
    bouge pas d'un rendu à l'autre. Elle reste vraie à l'écran ET dans le PDF, qui
    n'a ni « dessous » ni « à côté ».
    """
    located = []
    for lang, guide in _all_guides():
        for i, step in enumerate(guide.steps, 1):
            text = (step.text or "").lower()
            for phrase in ("en haut de cet onglet", "at the top of this tab",
                           "encadré 👉 saisir", "box 👉 enter",
                           "page 🔑 credentials api →", "page 🔑 api credentials →"):
                if phrase in text:
                    located.append(f"{lang}/{guide.key} étape {i} : {phrase!r}")
    assert not located, (
        "Ces étapes situent le formulaire pour quelqu'un qui l'a sous les yeux :\n  "
        + "\n  ".join(located)
        + "\n\nNomme le champ, pas l'endroit."
    )


def test_the_tab_renders_the_guide_beside_the_form_and_open():
    """Deux colonnes, et le guide déplié — sinon la capture reste à ouvrir.

    La capture du menu Partager est dans le guide depuis le matin du 2026-09-04, et
    la remarque du soir était « il n'y a toujours pas le screen » : personne ne
    déplie un pavé pour aller chercher une image pendant qu'il remplit un champ.
    Une consigne qu'il faut ouvrir pour lire n'est pas à côté de l'action.
    """
    import ast
    from pathlib import Path as _Path

    render = (_Path(__file__).resolve().parents[1] / "src" / "dashboard" / "views"
              / "credentials" / "_render.py")
    src = render.read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "_render_platform_tab")
    body = ast.get_source_segment(src, fn) or ""

    assert "st.columns" in body, (
        "l'onglet ne rend plus le formulaire et son guide côte à côte — le guide "
        "retomberait sous le formulaire, replié, là où deux artistes ne l'ont pas vu"
    )
    call = next((n for n in ast.walk(fn)
                 if isinstance(n, ast.Call)
                 and getattr(n.func, "id", "") == "render_credential_guide_for"), None)
    assert call is not None, "le guide n'est plus rendu dans l'onglet de saisie"
    expanded = next((k.value for k in call.keywords if k.arg == "expanded"), None)
    assert isinstance(expanded, ast.Constant) and expanded.value is True, (
        "le guide de l'onglet n'est plus déplié : il redevient un pavé à ouvrir, "
        "et la capture d'écran redevient invisible"
    )


def test_the_standalone_guide_list_stays_collapsed():
    """L'autre appelant garde des pavés repliés — quatre guides ouverts sont un mur.

    Le défaut serait de généraliser `expanded=True` « par cohérence ». Les deux
    surfaces ne posent pas la même question : dans l'onglet, le guide accompagne UN
    champ ; sur la page qui liste les quatre, il faut pouvoir choisir.
    """
    import inspect

    from src.dashboard.content.credential_guides_st import render_credential_guide_for

    sig = inspect.signature(render_credential_guide_for)
    assert sig.parameters["expanded"].default is False, (
        "le guide est déplié PAR DÉFAUT : la page qui en liste quatre deviendrait "
        "un mur. C'est l'appelant qui décide, pas la fonction."
    )
