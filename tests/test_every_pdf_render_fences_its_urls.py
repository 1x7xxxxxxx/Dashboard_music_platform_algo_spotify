"""Aucun rendu WeasyPrint de ce dépôt ne va chercher une ressource distante.

Type: Test
Uses: ast
Depends on: src/dashboard/utils/pdf_url_fence.py
Persists in: nothing

Le défaut, mesuré le 2026-09-17 en balayant les frères de
`server-side-render-fetches-tenant-chosen-urls` : la clôture existait, elle était
passée à **UN rendu sur trois**. `guides/guide_pdf.py` et `utils/guide_assets.py`
rendaient sans elle.

Aucun des deux ne touche à de la donnée de locataire aujourd'hui — il n'y avait donc
pas de défaut vivant, et c'est précisément pourquoi rien ne le signalait. Ce qui
existait était une clôture qui était la propriété d'un SITE au lieu d'être la
propriété du GESTE : un quatrième rendu l'aurait perdue de la même façon.

⚠️ Le cas qui décide est `guide_assets.pdf_from_html` : elle rend un HTML
**quelconque**, elle n'a **aucun appelant en production**, et elle est maintenue en
vie par un test qui vérifie sa mise en cache. Sans clôture, sans appelant, avec un
test : la forme exacte qu'on branche un jour sans relire sa sécurité.

Mutation record — 2026-09-17, trois mutations :
  1. retirer `url_fetcher=` de `guide_assets.py`      → **ROUGE** (1 échec, le site
     nommé dans le message).
  2. ajouter `None` à `_FENCE_NAMES`                  → **verte**, et c'est correct :
     les trois rendus passent désormais la clôture, donc élargir l'ensemble des noms
     acceptés ne change rien. La mutation ne visait pas un organe vivant. L'anti-vacuité
     réelle est `test_the_sweep_still_finds_the_renders`, qui exige ≥ 3 rendus.
  3. remplacer `if url.startswith("data:")` par `if True:` dans la clôture
                                                      → **ROUGE** (1 échec + 1 erreur) :
     un nom n'est pas un comportement, et `test_the_fence_actually_blocks_a_remote_url`
     l'exige sur trois URL, dont `169.254.169.254` et `file:///etc/passwd`.

---
rex: []
---
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"

# Les noms acceptables pour la clôture. `no_remote_resources` est le canonique ;
# `_no_remote_resources` reste un alias, nommé par le catalogue de classes d'erreur.
_FENCE_NAMES = {"no_remote_resources", "_no_remote_resources"}


def _weasyprint_html_calls() -> list[tuple[Path, ast.Call]]:
    """Tout appel `HTML(string=…)` de `src/` — c'est la porte du rendu PDF."""
    found: list[tuple[Path, ast.Call]] = []
    for path in sorted(_SRC.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:                      # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name != "HTML":
                continue
            if any(kw.arg == "string" for kw in node.keywords):
                found.append((path, node))
    return found


def _fence_argument(call: ast.Call) -> str | None:
    for kw in call.keywords:
        if kw.arg != "url_fetcher":
            continue
        value = kw.value
        if isinstance(value, ast.Name):
            return value.id
        return ast.dump(value)
    return None


def test_the_sweep_still_finds_the_renders() -> None:
    """Anti-vacuité : un test qui ne trouve aucun rendu passe toujours."""
    calls = _weasyprint_html_calls()
    assert len(calls) >= 3, (
        "aucun rendu `HTML(string=…)` trouvé sous `src/` — le détecteur ne voit plus "
        f"son sujet (trouvés : {len(calls)})")


def test_every_render_passes_the_fence() -> None:
    """La clôture est une propriété du GESTE, pas d'un site."""
    nus = []
    for path, call in _weasyprint_html_calls():
        fence = _fence_argument(call)
        if fence not in _FENCE_NAMES:
            nus.append(f"{path.relative_to(_ROOT)}:{call.lineno} → url_fetcher={fence}")
    assert not nus, (
        "un rendu PDF peut aller chercher une ressource distante :\n  "
        + "\n  ".join(nus)
        + "\n\nRemède : `url_fetcher=no_remote_resources` "
          "(`src/dashboard/utils/pdf_url_fence.py`). Les images de ce dépôt sont "
          "embarquées en `data:`, donc la clôture ne coûte rien.")


def test_the_fence_actually_blocks_a_remote_url() -> None:
    """Un nom n'est pas un comportement : la clôture doit LEVER."""
    import sys

    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.pdf_url_fence import no_remote_resources

    import pytest

    for url in ("http://169.254.169.254/latest/meta-data/",
                "https://example.com/x.png",
                "file:///etc/passwd"):
        with pytest.raises(ValueError):
            no_remote_resources(url)


def test_the_fence_still_serves_the_data_uris_the_documents_need() -> None:
    """Et elle ne doit pas casser les documents : ils sont faits de `data:`."""
    import base64
    import sys

    sys.path.insert(0, str(_ROOT))
    from src.dashboard.utils.pdf_url_fence import no_remote_resources

    pixel = base64.b64encode(b"\x89PNG\r\n\x1a\n").decode()
    out = no_remote_resources(f"data:image/png;base64,{pixel}")
    assert out, "une `data:` URI doit passer — sinon les captures du guide disparaissent"
