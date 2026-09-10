"""Le rapport client n'écrit aucun caractère que sa chaîne de rendu ne sait pas dessiner.

Type: Test
Uses: pytest, re
Depends on: src/dashboard/utils/pdf_exporter/, src/dashboard/utils/i18n_catalog/pdf.py
Persists in: nothing

Ce qui a été mesuré, et la correction que la mesure a imposée
-------------------------------------------------------------
Constat de départ, le 2026-09-10 : rendu le golden HTML du rapport, un seul émoji sur
vingt-neuf s'imprimait — un nuage devant SoundCloud, rien devant les sept autres
plateformes. L'image de production (`python:3.11-slim`) n'embarque en effet **aucune
police** : vérifié, zéro entrée, et le `Dockerfile` installe la pile de rendu de
WeasyPrint sans une seule fonte.

**Mais le chemin de production n'était pas celui que j'avais mesuré.** Le générateur
retire déjà tous les émojis du HTML avant d'appeler WeasyPrint, par une expression
prévue pour ça. Le golden est un artefact d'AMONT : le rendre directement contourne ce
filtre. Le rapport livré aux artistes n'a donc jamais porté d'émoji invisible.

Ce que ce garde protège vraiment
---------------------------------
1. **Le filtre reste sur le chemin de rendu.** S'il disparaît, les émojis atteignent
   WeasyPrint et s'évaporent — sans erreur, sans carré de substitution.
2. **La source ne compte plus sur lui.** Les glyphes ont été retirés des chaînes, si
   bien qu'un émoji ne peut plus porter une DÉCISION : `_badge` indexait un
   dictionnaire par le glyphe de fraîcheur, c'est-à-dire par un caractère que le filtre
   d'aval effaçait de la sortie. La pastille se choisit désormais sur la couleur.

La leçon de forme, elle, tient : un rendu se vérifie en regardant la page produite —
et en vérifiant qu'on regarde bien la page que le PRODUIT fabrique.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Les surfaces qui composent le rapport client.
_PDF_SURFACES = [
    REPO / "src" / "dashboard" / "utils" / "pdf_exporter",
    REPO / "src" / "dashboard" / "utils" / "i18n_catalog" / "pdf.py",
]

# Tout ce qui vit au-delà du plan multilingue de base, plus les émojis du plan de base
# et le sélecteur de variante. Aucun n'est dessinable par la chaîne actuelle.
_UNDRAWABLE = re.compile(
    r"[\U0001F000-\U0001FAFF"      # émojis et symboles des plans supplémentaires
    r"☀-➿"               # symboles divers et dingbats
    r"️︎"                # sélecteurs de variante
    r"\U0001F1E6-\U0001F1FF]")     # indicateurs régionaux (drapeaux)


def _files():
    for s in _PDF_SURFACES:
        if s.is_dir():
            yield from sorted(s.rglob("*.py"))
        elif s.exists():
            yield s


def test_no_undrawable_glyph_reaches_the_client_report() -> None:
    """Par l'AST, et seulement sur les chaînes qui peuvent ATTEINDRE le document.

    Un commentaire ou une docstring ne part pas dans le PDF. Les lire ferait rougir ce
    garde sur l'explication de son propre correctif — le mode d'aveuglement que ce
    dépôt catalogue, et dans lequel je suis tombé deux fois dans la même séance avant
    d'écrire cette ligne.
    """
    import ast

    found: list[str] = []
    for f in _files():
        tree = ast.parse(f.read_text(encoding="utf-8"))
        docs = {id(p.body[0].value) for p in ast.walk(tree)
                if isinstance(p, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                  ast.AsyncFunctionDef))
                and p.body and isinstance(p.body[0], ast.Expr)
                and isinstance(p.body[0].value, ast.Constant)
                and isinstance(p.body[0].value.value, str)}
        for n in ast.walk(tree):
            if not (isinstance(n, ast.Constant) and isinstance(n.value, str)):
                continue
            if id(n) in docs:
                continue
            # L'expression du filtre DÉCRIT les glyphes à retirer : elle doit les
            # contenir. Un garde qui rougit sur le remède est un garde qu'on désarme.
            if "\\U0001" in n.value or n.value.startswith("["):
                continue
            for m in _UNDRAWABLE.finditer(n.value):
                found.append(f"{f.relative_to(REPO)}:{n.lineno} → {m.group(0)!r}")

    assert not found, (
        f"{len(found)} glyphe(s) que la chaîne de rendu ne sait pas dessiner :\n  "
        + "\n  ".join(found[:12])
        + "\n\nL'image de production n'embarque aucune police : ces caractères "
          "disparaissent du document, en silence, et le rapport part ainsi chez "
          "l'artiste. Mesuré le 2026-09-10 : 29 émojis portés, 1 imprimé.")


def test_the_render_path_still_strips_what_it_cannot_draw() -> None:
    """Le filtre d'aval est la vraie protection : il doit rester sur le chemin.

    Structurel, jamais textuel : on vérifie que la fonction qui produit le PDF applique
    bien la substitution, pas que son nom apparaisse quelque part dans le fichier.
    """
    import ast

    src = (REPO / "src" / "dashboard" / "utils" / "pdf_exporter" / "_report.py")
    tree = ast.parse(src.read_text(encoding="utf-8"))
    applied = [
        n for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        and n.func.attr == "sub"
        and getattr(n.func.value, "id", "") == "_EMOJI_RE"
    ]
    assert applied, (
        "le filtre qui retire les glyphes indessinables n'est plus appliqué dans "
        "`_report`. Sans lui, tout émoji laissé dans une chaîne atteint WeasyPrint et "
        "disparaît du document — sans erreur, sans carré de substitution.")


def test_the_predicate_would_catch_the_original_defect() -> None:
    """Non-vacuité : le prédicat doit voir ce qui a été retiré.

    Sans cette moitié, une expression régulière cassée rendrait le garde vert pour
    toujours — et c'est exactement le mode d'aveuglement que ce dépôt catalogue.
    """
    for glyph in ("✅", "🎵", "🍎", "☁", "⚠"):
        assert _UNDRAWABLE.search(glyph), f"{glyph!r} passerait le garde"
