"""SoundCloud : un seul geste demandé, et le même mot partout pour le dire.

Type: Test
Uses: credential_guides (FR/EN), le catalogue i18n, _registry, platform_value
Depends on: src/dashboard/content/credential_guides*.py,
    src/dashboard/views/credentials/_registry.py,
    src/dashboard/content/platform_value.py,
    src/dashboard/views/soundcloud.py, views/credentials/_render.py
Persists in: nothing

Le défaut, signalé le 2026-09-04
--------------------------------
« C'est bizarre, tu demandes de saisir l'URL d'artiste et tu me demandes mon User ID
numérique… »

Les deux étaient vrais — à des moments différents. Le champ accepte le LIEN, et
`_save_credentials` le résout en identifiant numérique avant l'écriture, si bien que
la colonne ne contient que des chiffres. Le libellé du champ nommait donc ce que la
BASE stocke ; le guide juste à côté nommait ce qu'on demande de coller. Un artiste ne
lit pas deux moments : il lit un formulaire, et il y a lu deux consignes qui se
contredisent.

Quatre surfaces disaient la même chose de quatre façons — le libellé du champ, la
note du guide, `PlatformValue.need` sur la page de mise en route, et la traduction
anglaise. La quatrième était pire que fausse : le catalogue EN décrivait encore
l'ancienne procédure, abandonnée côté français le 2026-09-03 — chercher
`soundcloud:users:` dans le code source de /discover. Et le rendu PRÉFÈRE la
traduction à la source, donc un lecteur anglophone recevait un guide qu'aucun
francophone ne lisait plus.

Ce que ce fichier affirme
-------------------------
Que ces quatre surfaces demandent la MÊME chose, sans jamais réclamer un identifiant
numérique. Le prédicat porte sur la demande, pas sur une formulation : on peut
réécrire les phrases, pas redemander un numéro.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.dashboard.content.credential_guides import CREDENTIAL_GUIDES
from src.dashboard.content.credential_guides_en import CREDENTIAL_GUIDES_EN
from src.dashboard.content.platform_value import BY_KEY
from src.dashboard.utils.i18n_catalog.credentials import EN
from src.dashboard.views.credentials._registry import PLATFORMS

_ROOT = Path(__file__).resolve().parents[1]

# Ce qu'on ne demande PLUS à un artiste, dans les deux langues.
_ASKS_A_NUMBER = ("user id numérique", "numeric user id", "identifiant numérique",
                  "soundcloud:users:")


def _sc_guides():
    return [("fr", next(g for g in CREDENTIAL_GUIDES if g.key == "soundcloud")),
            ("en", next(g for g in CREDENTIAL_GUIDES_EN if g.key == "soundcloud"))]


def test_the_field_asks_for_the_link_not_the_number():
    """Le libellé du champ nomme ce qu'on colle, pas ce que la base stocke."""
    fields = PLATFORMS["soundcloud"]["fields"]
    assert len(fields) == 1, "SoundCloud ne demande qu'une valeur ; sinon ce test ment"
    label = fields[0]["label"].lower()
    assert not any(bad in label for bad in _ASKS_A_NUMBER), (
        f"le champ s'appelle {fields[0]['label']!r} — il réclame un numéro alors que "
        "le guide dit de coller un lien, et que c'est le lien que le code résout"
    )
    assert "lien" in label or "link" in label or "profil" in label or "profile" in label
    assert fields[0]["example"].startswith("https://soundcloud.com/"), (
        "l'exemple du champ n'est pas un lien de profil : le placeholder redonnerait "
        "la consigne que le libellé vient de retirer"
    )


def test_the_setup_page_asks_for_the_same_thing():
    """`PlatformValue.need` est lu sur la page de mise en route, AVANT le formulaire.

    C'est la première fois qu'un artiste lit ce qu'on lui demandera. Une promesse
    différente de celle du champ crée l'écart exactement là où il coûte le plus.
    """
    need = BY_KEY["soundcloud"].need.lower()
    assert not any(bad in need for bad in _ASKS_A_NUMBER), (
        f"la page de mise en route annonce « {BY_KEY['soundcloud'].need} » et le "
        "formulaire demande un lien"
    )


@pytest.mark.parametrize("lang,attr", [("fr", "note"), ("en", "note")])
def test_the_guide_field_note_asks_for_the_same_thing(lang, attr):
    guide = dict(_sc_guides())[lang]
    note = (guide.fields[0].note or "").lower()
    assert not any(bad in note for bad in _ASKS_A_NUMBER), (
        f"{lang} : la note du champ parle encore d'un identifiant numérique"
    )


def test_the_english_catalog_does_not_outlive_its_source():
    """Le rendu préfère la traduction : une clé périmée EST le guide anglais.

    C'est le défaut le plus discret des quatre. Rien ne relie une clé de catalogue à
    la version du guide qu'elle traduit, donc réécrire la source française laisse
    l'anglaise en place — et personne ne la relit, puisqu'elle n'est jamais rouge.
    """
    stale = {k: v for k, v in EN.items()
             if k.startswith("credentials.guide.soundcloud.")
             and any(bad in str(v).lower() for bad in _ASKS_A_NUMBER)}
    assert not stale, (
        "Ces traductions décrivent une procédure SoundCloud abandonnée :\n  "
        + "\n  ".join(f"{k} = {v!r}" for k, v in stale.items())
        + "\n\nLe rendu les préfère à `credential_guides_en.py` : c'est ce que lit "
          "un artiste anglophone."
    )


def test_the_guide_has_no_intro_repeating_its_two_steps():
    """« Une seule chose à fournir : le lien… » annonçait l'étape 1 et la note du champ.

    Un guide de deux lignes n'a pas besoin d'un résumé. Retiré le 2026-09-04 ; le
    garde existe pour qu'il ne revienne pas au prochain passage de relecture.
    """
    for lang, guide in _sc_guides():
        assert not (guide.intro or "").strip(), (
            f"{lang} : le guide SoundCloud a de nouveau une intro — elle redit ses "
            f"deux étapes ({guide.intro!r})")
    assert "credentials.guide.soundcloud.intro" not in EN, (
        "la traduction de l'intro survit à l'intro : elle réapparaîtrait seule, en "
        "anglais, ce qui est exactement le défaut que le test au-dessus ferme")


def test_an_optional_guide_field_is_optional_in_BOTH_renderers():
    """Le PDF et l'écran rendent le même objet ; l'un le supposait complet.

    `make guide` est tombé sur un `TypeError` la première fois qu'un guide s'est
    passé d'`intro` : `guide_pdf._render_cred_html` gardait déjà `note` et `fields`,
    pas `intro`. Le rendu Streamlit, lui, ne levait pas — il posait un bloc markdown
    vide. Deux lecteurs d'un même objet, deux idées de ce qui est obligatoire.

    Le garde interroge le CONTRAT (`PlatformCred` déclare ce qui peut être absent) et
    vérifie qu'aucun rendu ne lit un champ optionnel sans le garder. Écrit sur les
    trois champs optionnels, pas seulement sur celui qui vient de casser — c'est la
    différence entre fermer un défaut et fermer sa classe.
    """
    import dataclasses

    from src.dashboard.content.credential_guides import PlatformCred

    # L'ANNOTATION, pas la valeur par défaut. `intro` reste positionnel — chaque guide
    # doit dire s'il en a une — donc `f.default is None` le manquait, et le garde
    # passait au vert sur le code qui venait de casser `make guide`. Le prédicat
    # regardait la mauvaise moitié de la déclaration.
    optional = {f.name for f in dataclasses.fields(PlatformCred)
                if f.default is None or "None" in str(f.type)}
    assert {"intro", "note"} <= optional, (
        f"le contrat de PlatformCred a changé : champs optionnels = {optional}")

    for path, who in ((_ROOT / "src/dashboard/guides/guide_pdf.py", "guide_pdf"),
                      (_ROOT / "src/dashboard/content/credential_guides_st.py",
                       "credential_guides_st")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for field in sorted(optional):
            for site in _unguarded_reads(tree, field):
                raise AssertionError(
                    f"{who} ligne {site} lit `{field}` sans tester son absence, alors "
                    f"que `PlatformCred.{field}` peut valoir None. C'est exactement la "
                    "forme qui a fait tomber `make guide` le 2026-09-04."
                )


def _unguarded_reads(tree: ast.AST, field: str) -> list[int]:
    """Les lignes où le champ est lu SANS être protégé — site par site.

    Deux versions de ce prédicat se sont trompées avant celle-ci, des deux façons
    possibles, et c'est la même erreur de portée dans les deux sens :

      * la première cherchait `f"if cred.{field}"` dans le TEXTE et a accusé
        `guide_pdf` de lire `admin_note` sans garde — un nom qui n'y figure que dans
        un commentaire expliquant qu'il n'est pas rendu ;
      * la deuxième lisait l'arbre mais posait la question au FICHIER : « ce champ
        est-il testé quelque part ? ». Un `guide.intro or ""` dans une autre fonction
        y répondait oui, et le garde restait vert sur le rendu non protégé.

    La question juste porte sur CHAQUE lecture : celle-ci est-elle sous un test qui
    la mentionne, ou repliée par un `or` ? Un champ optionnel lu deux fois doit être
    gardé deux fois.
    """
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node

    # Les variables qui portent VRAIMENT un `PlatformCred`, lues sur l'annotation du
    # paramètre. Filtrer sur les noms (`cred`, `guide`) confondait deux dataclasses :
    # `_render_guide_html(guide: PlatformGuide)` rend les guides d'import CSV, dont
    # l'`intro` n'est pas optionnelle, et le garde l'accusait d'un défaut qui n'est
    # pas le sien. Le nom d'une variable ne dit pas son type.
    holders: set[str] = set()
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for arg in list(fn.args.args) + list(fn.args.kwonlyargs):
            if getattr(arg.annotation, "id", "") == "PlatformCred":
                holders.add(arg.arg)

    def is_read(n) -> bool:
        return (isinstance(n, ast.Attribute) and n.attr == field
                and getattr(n.value, "id", "") in holders)

    def mentions(node) -> bool:
        return any(is_read(n) for n in ast.walk(node))

    bad: list[int] = []
    for node in ast.walk(tree):
        if not is_read(node):
            continue
        # Une occurrence DANS le test n'est pas une lecture à protéger : c'est la
        # protection. Sans cette ligne le garde accuse `if cred.intro:` lui-même.
        direct = parents.get(id(node))
        if isinstance(direct, (ast.If, ast.IfExp)) and node is direct.test:
            continue
        cur, safe = node, False
        while cur is not None and not safe:
            parent = parents.get(id(cur))
            if isinstance(parent, ast.BoolOp):          # `cred.note or ""`
                safe = True
            elif isinstance(parent, ast.If) and cur in parent.body:
                safe = mentions(parent.test)
            elif isinstance(parent, ast.IfExp) and cur is not parent.test:
                safe = mentions(parent.test)
            cur = parent
        if not safe:
            bad.append(node.lineno)
    return bad


# ── Le panneau des titres hébergés ailleurs ─────────────────────────────────

def test_the_claimed_tracks_panel_left_the_credentials_page():
    """Ce n'est pas un identifiant : c'est une déclaration de catalogue.

    Il vivait dans l'onglet SoundCloud de Credentials, DÉPLIÉ, donc au-dessus du seul
    champ à remplir. Un artiste venu coller son lien rencontrait d'abord un pavé sur
    les labels et les collectifs.
    """
    render = (_ROOT / "src/dashboard/views/credentials/_render.py").read_text(encoding="utf-8")
    tree = ast.parse(render)
    names = {f.name for f in ast.walk(tree) if isinstance(f, ast.FunctionDef)}
    assert "_render_claimed_tracks" not in names, (
        "le panneau des titres revendiqués est revenu dans la page Credentials")
    assert "render_claimed_tracks" not in render, (
        "la page Credentials appelle de nouveau le panneau de déclaration")


def test_the_panel_renders_on_the_soundcloud_page_including_when_it_is_empty():
    """Les deux chemins, et le second est celui qui compte.

    La page sort par un `return` quand aucune donnée n'est trouvée — et un profil vide
    est précisément l'état d'un artiste signé sur un label : il l'est par construction
    et le restera. Rendre le panneau seulement en fin de fonction l'aurait rendu
    invisible sur la seule page où il est la réponse.
    """
    src = (_ROOT / "src/dashboard/views/soundcloud.py").read_text(encoding="utf-8")
    assert src.count("render_claimed_tracks(db, artist_id)") >= 2, (
        "le panneau n'est rendu qu'une fois : le chemin « aucune donnée » sort par "
        "`return` avant lui, et c'est le cas d'usage du panneau"
    )

    tree = ast.parse(src)
    fn = next(f for f in ast.walk(tree)
              if isinstance(f, ast.FunctionDef) and f.name == "show")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "render_claimed_tracks"]
    assert len(calls) >= 2, "les appels ne sont pas dans `show()`"


def test_the_panel_does_not_open_by_itself():
    """« Ne déplie pas directement » — 2026-09-04.

    Une case dépliée d'office prend la place d'un contenu que l'artiste est venu voir.
    Le garde lit le mot-clé de l'appel, pas le rendu : `expanded` est le seul endroit
    où la décision existe.
    """
    src = (_ROOT / "src/dashboard/views/soundcloud_claims.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    exp = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
           and getattr(getattr(n.func, "attr", None), "__str__", str)() == "expander"]
    assert exp, "plus aucun expander dans le module : ce garde serait aveugle"
    for call in exp:
        kw = next((k.value for k in call.keywords if k.arg == "expanded"), None)
        assert isinstance(kw, ast.Constant) and kw.value is False, (
            "le panneau des titres hébergés ailleurs se déplie tout seul")
