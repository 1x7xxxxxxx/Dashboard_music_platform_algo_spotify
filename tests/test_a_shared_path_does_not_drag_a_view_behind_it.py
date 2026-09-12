"""Un module du chemin de la barre latérale n'importe pas une VUE.

Type: Test
Uses: ast
Depends on: src/dashboard/utils/*.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Mesuré le 2026-09-12, pas deviné : `setup_completion._csv_detail` avait besoin des
HUIT LIBELLÉS du registre d'import pour afficher « OK / NOK » par type de fichier,
et les lisait par `from src.dashboard.views.upload_csv import _PLATFORMS`.

    premier appel  1 073 ms
    second appel       2 ms

Les 1 071 ms sont l'IMPORT du module : pandas, les transformateurs CSV, Streamlit —
pour huit chaînes de caractères. Le budget d'un rendu de page complète est de
**287 ms** (`.claude/dev-docs/roadmap/checklist.md`), et `setup_completion` tourne
dans le chemin de la barre latérale, donc à chaque page. Le premier rendu qu'un
artiste voit passait à ×4.

L'import était PARESSEUX, et c'est précisément ce qui le rendait invisible : il ne
coûte rien à l'import du module, rien en test unitaire, et tout au premier clic.

Ce que le prédicat vise, et ce qu'il ne vise pas
------------------------------------------------
La règle n'est pas « ne jamais importer une vue ». C'est : **un module partagé —
tout ce qui vit sous `utils/` — ne tire pas une vue derrière lui.** Une vue est une
feuille du graphe : elle importe des utilitaires, jamais l'inverse. Quand un
utilitaire a besoin d'une DONNÉE qui vit dans une vue, c'est la donnée qui doit
descendre, pas l'utilitaire qui doit monter — recopier la donnée serait la seconde
copie que ce dépôt paie à chaque fois.

Le sens de la dépendance est donc aussi une règle d'architecture, et pas seulement
une optimisation : `utils/csv_platforms.py` existe pour cette raison.

Journal de mutation — 2026-09-12 : avec `from src.dashboard.views.upload_csv import
_PLATFORMS` remis dans `_csv_detail`, ce garde le nomme en `fichier:ligne` et
échoue ; retiré, il passe.
"""
from __future__ import annotations

import ast
import pathlib

_ROOT = pathlib.Path(__file__).resolve().parent.parent
_SHARED = _ROOT / "src" / "dashboard" / "utils"

# Les modules partagés qui ont une raison ÉCRITE d'atteindre une vue.
#
# LE CRITÈRE EST LE CHEMIN, PAS LE COÛT. Les quatre modules de vue mesurés le
# 2026-09-12 coûtent tous cher à l'import — `trigger_algo._common` 2 501 ms,
# `credentials._registry` 1 950 ms, `credentials.router` 1 774 ms,
# `upload_csv` 1 551 ms. Ce qui décide, c'est QUI paie : un import atteint depuis
# le rendu de la barre latérale ou de l'accueil est payé par tout le monde, à
# chaque page ; un import atteint depuis la page qui a déjà chargé ce paquet ne
# coûte rien de plus.
#
# Chaque entrée a donc été lue jusqu'à son appelant, pas jugée sur son nom.
_ALLOWED: dict[str, str] = {
    "src/dashboard/utils/pdf_exporter/_collectors.py":
        "chemin du PDF, jamais un rendu de page : `generate_pdf` n'est appelé que "
        "depuis `views/export_pdf` (déjà une vue) et depuis le DAG `onboarding_"
        "report`, qui n'a pas de budget d'interaction. Le coût est payé une fois par "
        "document, pas par visite.",
    "src/dashboard/utils/pdf_ml.py":
        "même chemin que `_collectors` — section ML du PDF.",
    "src/dashboard/utils/status_matrix.py":
        "`render_platform_state` n'a qu'un appelant, `views/credentials/_render.py`, "
        "qui a déjà importé le routeur pour s'afficher : l'import y est gratuit. "
        "⚠️ L'AUTRE lecture de ce fichier ne l'était pas — `_requires_sharing` "
        "importait `credentials._registry` (1 950 ms) et `render_status_matrix` est "
        "rendu SUR L'ACCUEIL pour tout artiste dont la mise en route n'est pas "
        "finie. Corrigé le 2026-09-12 : le drapeau est descendu dans "
        "`utils/platform_sharing.py`. L'exemption couvre le premier cas, pas le "
        "second — si une lecture de ce fichier redevient chaude, elle se lit ici.",
}


def _view_imports() -> list[str]:
    """Les imports de `views.*` depuis `utils/`, en fichier:ligne — par AST.

    Y compris les imports PARESSEUX, écrits dans un corps de fonction : ce sont
    ceux qui coûtent, parce qu'ils ne se voient ni à la lecture de l'en-tête ni au
    temps d'import du module.
    """
    out: list[str] = []
    for path in sorted(_SHARED.rglob("*.py")):
        rel = str(path.relative_to(_ROOT))
        if rel in _ALLOWED:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            module = None
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
            elif isinstance(node, ast.Import):
                module = next((a.name for a in node.names
                               if ".views." in a.name or a.name.endswith(".views")), None)
            if module and (".views." in module or module.endswith(".views")):
                out.append(f"{rel}:{node.lineno} → {module}")
    return out


def test_no_shared_module_imports_a_view() -> None:
    offenders = _view_imports()
    assert not offenders, (
        "un module partagé importe une VUE, donc le charge entièrement pour ce qu'il "
        "y lit :\n" + "\n".join(offenders) + "\n\n"
        "Mesuré le 2026-09-12 sur exactement ce geste : lire huit libellés dans "
        "`views/upload_csv` depuis `setup_completion` coûtait **1 073 ms au premier "
        "rendu de l'accueil** (pandas + transformateurs + Streamlit), pour un budget "
        "de page de 287 ms. Un import paresseux ne coûte rien en test et tout au "
        "premier clic.\n"
        "Faire DESCENDRE la donnée dans un module partagé — `utils/csv_platforms.py` "
        "est le précédent — jamais recopier, jamais faire monter l'utilitaire.")


def test_the_predicate_sees_the_lazy_form() -> None:
    """Non-vacuité : un prédicat aveugle aux imports de fonction verrait zéro.

    C'est LA forme du défaut — l'import était dans un corps de fonction, pas dans
    l'en-tête. Un garde qui ne lit que les imports de module aurait été vert sur le
    jour où l'accueil a quadruplé.
    """
    tree = ast.parse(
        "def f():\n    from src.dashboard.views.upload_csv import _PLATFORMS\n"
        "    return _PLATFORMS\n")
    found = [n for n in ast.walk(tree)
             if isinstance(n, ast.ImportFrom) and ".views." in (n.module or "")]
    assert found, "le lecteur AST ne voit pas un import écrit dans une fonction"


def test_the_allowlist_names_files_that_exist() -> None:
    """Une exemption sur un fichier disparu élargit la règle en silence."""
    gone = sorted(f for f in _ALLOWED if not (_ROOT / f).exists())
    assert not gone, f"exemption(s) sans fichier : {gone}"
