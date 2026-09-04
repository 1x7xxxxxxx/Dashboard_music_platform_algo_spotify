"""Quand un message envoie l'artiste sur une page, il l'appelle par son nom du menu.

Type: Test
Uses: app._NAV_SECTIONS, les catalogues i18n, les vues qui renvoient ailleurs
Depends on: src/dashboard/app.py, src/dashboard/**/*.py
Persists in: nothing

Le défaut, trouvé le 2026-09-04
-------------------------------
La page d'import s'appelait « 📂 Import CSV ». Elle a été renommée « 📂 Ajouter mes
chiffres Spotify for Artists & Apple » — parce qu'un artiste ne sait pas ce qu'est un
CSV, c'était la demande. Deux messages de la page Credentials ont continué à dire
« Sa page est **📂 Import CSV** » et « 📂 Aller à l'import CSV → » : ils envoient
chercher dans le menu une entrée qui n'y est plus.

Personne ne l'a vu, et rien ne pouvait le voir. Le renommage a touché `_NAV_SECTIONS`,
les tests de menu ont vérifié le menu, et les phrases qui citaient l'ancien nom vivaient
dans deux autres fichiers. C'est la forme exacte de « la doc pourrit là où rien ne la
lit », appliquée à l'interface : une seconde copie d'un nom, dans une prose que rien ne
compare à sa source.

Ce que ce fichier affirme
-------------------------
Qu'aucune chaîne visible ne cite un nom de page PÉRIMÉ, c'est-à-dire un libellé qui a
été celui d'une entrée de menu et ne l'est plus. Le test lit les libellés vivants dans
`_NAV_SECTIONS` ; la liste des noms morts est explicite et ne peut que s'allonger — un
nom qu'on retire du menu s'y ajoute le jour du renommage.

Pourquoi une liste de noms morts plutôt qu'une règle générale
--------------------------------------------------------------
« Toute chaîne entre ** qui ressemble à un nom de page doit exister dans le menu »
serait la règle idéale et elle est inapplicable : l'interface met en gras des noms de
boutons, d'onglets, de champs et de plateformes. Un prédicat aussi large produirait du
bruit à chaque phrase et finirait désarmé. Une liste courte de noms qu'on SAIT morts
n'attrape que ce qu'on cherche, et le coût d'y ajouter une ligne est celui d'un
renommage — le moment exact où on y pense.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_APP = _ROOT / "src" / "dashboard" / "app.py"
_DASHBOARD = _ROOT / "src" / "dashboard"

# Un nom retiré du menu, et la raison. On n'en retire jamais d'entrée : le jour où on
# rebaptise une page, l'ancien nom vient ici.
_RETIRED_PAGE_NAMES = {
    "📂 Import CSV": "renommée « Ajouter mes chiffres Spotify for Artists & Apple » "
                     "le 2026-09-04 — « CSV » ne dit rien à un artiste",
    "📂 CSV import": "idem, côté anglais",
}

# La comparaison ignore la CASSE. Écrite sensible à la casse, la première version de
# ce garde a trouvé les six occurrences françaises et raté les quatre anglaises, qui
# disaient « 📂 CSV Import » avec un I majuscule. C'est la portée du garde qui était
# le défaut — pour la sixième fois — et sur le garde écrit pour trouver ce défaut-là.
_RETIRED_LOWER = {k.lower(): k for k in _RETIRED_PAGE_NAMES}


def _nav_labels() -> set[str]:
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    labels: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(getattr(x, "id", "") == "_NAV_SECTIONS" for x in node.targets):
            continue
        for sub in ast.walk(node.value):
            if isinstance(sub, ast.Tuple) and len(sub.elts) == 2:
                a, b = sub.elts
                if (isinstance(a, ast.Constant) and isinstance(a.value, str)
                        and isinstance(b, ast.Constant) and isinstance(b.value, str)):
                    labels.add(a.value)
    return labels


def test_the_menu_labels_are_readable_at_all():
    """Non-vacuité : sans libellés lus, tout ce fichier passerait pour rien."""
    labels = _nav_labels()
    assert len(labels) > 20, (
        f"seulement {len(labels)} libellés lus dans `_NAV_SECTIONS` — la lecture a "
        "cassé, et les assertions ci-dessous ne prouveraient plus rien")


def test_no_retired_page_name_is_still_in_the_menu():
    """Un nom déclaré mort qui vit encore dans le menu invaliderait la liste."""
    alive = _nav_labels() & set(_RETIRED_PAGE_NAMES)
    assert not alive, (
        f"{sorted(alive)} figure(nt) dans `_RETIRED_PAGE_NAMES` ET dans le menu. "
        "Retire l'entrée de la liste, ou le libellé du menu — telle quelle, elle "
        "interdit un nom que l'application utilise.")


def test_no_visible_string_still_names_a_retired_page():
    offenders: list[str] = []
    for path in sorted(_DASHBOARD.rglob("*.py")):  # vues ET catalogues i18n
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        low = text.lower()
        for dead_low, dead in _RETIRED_LOWER.items():
            if dead_low in low:
                line = next(n for n, ln in enumerate(text.splitlines(), 1)
                            if dead_low in ln.lower())
                offenders.append(f"{path.relative_to(_ROOT)}:{line} → {dead!r}")

    assert not offenders, (
        "Ces textes envoient l'artiste chercher dans le menu une entrée renommée :\n  "
        + "\n  ".join(offenders)
        + "\n\nNoms retirés et pourquoi :\n  "
        + "\n  ".join(f"{k!r} : {v}" for k, v in _RETIRED_PAGE_NAMES.items())
        + "\n\nEmploie le libellé exact du menu — c'est ce que l'artiste lit."
    )
