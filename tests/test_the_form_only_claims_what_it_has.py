"""Guard: the form header must not announce fields the form does not have.

Type: Utility
Uses: ast, src.dashboard.views.credentials._registry
Triggers: pytest
Persists in: nothing

Error class `header-announces-a-field-the-form-does-not-have`.

Reported 2026-09-06 on the Meta Ads tab: « retire "🔒 Champs secrets chiffrés •
Laissez vide pour conserver la valeur actuelle", inutile ». It was not merely
useless — it was FALSE. Measured on the registry the same day: `meta`, `soundcloud`
and `instagram` declare **zero** secret fields. Their form holds a single public
link, and it announced encrypted secrets and a blank-keeps-the-old-value rule with
nothing to apply it to. Three tabs out of five.

The fix is a CONDITION, not a deletion: on `spotify` and `youtube` the sentence is
true and useful — leaving a secret blank keeps a value nobody can read back. A
sentence that is right on two screens and wrong on three is not a wording problem,
it is a missing predicate.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.dashboard.views.credentials._registry import PLATFORMS


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


_RENDER = _repo_root() / "src" / "dashboard" / "views" / "credentials" / "_render.py"
_CAPTION_KEY = "credentials.form.caption"


def caption_holders(source: str) -> list[ast.If]:
    """Every `if` whose body renders the secret caption. Pure."""
    return [node for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.If)
            and _CAPTION_KEY in " ".join(ast.unparse(n) for n in node.body)]


def secret_gate(source: str) -> str | None:
    """The condition, among the caption's `if`s, that reads this form's secret fields."""
    for node in caption_holders(source):
        test = ast.unparse(node.test)
        if "secret" in test and "fields_def" in test:
            return test
    return None


def test_some_platforms_have_secrets_and_some_do_not():
    """Sans les deux cas, une condition ne se distingue pas d'un `if True`."""
    with_secret = [k for k, i in PLATFORMS.items()
                   if any(f.get("secret") for f in i.get("fields", []))]
    without = [k for k, i in PLATFORMS.items()
               if not any(f.get("secret") for f in i.get("fields", []))]
    assert with_secret and without, (
        f"avec secret={with_secret}, sans={without} — un des deux cas a disparu, "
        "et ce fichier ne prouverait plus rien")


def test_the_secret_caption_is_rendered_under_a_condition():
    """Par AST : la légende doit vivre sous un `if` qui interroge `secret`.

    Le prédicat est cherché dans le TEST du `if`, pas dans le fichier : un
    commentaire — celui qui explique ce correctif, par exemple — contient le mot
    `secret` et suffirait à une recherche de chaîne.
    """
    holders = caption_holders(_RENDER.read_text(encoding="utf-8"))

    assert holders, (
        f"« {_CAPTION_KEY} » n'est plus rendu sous aucun `if` : il s'affiche donc "
        "sur les formulaires sans champ secret, où il annonce une propriété fausse "
        "et une consigne sans objet.")

    # AU MOINS UN des `if` de la chaîne doit interroger les champs secrets. Ils sont
    # imbriqués — l'extérieur teste `existing_row`, ce qui est juste et n'a rien à
    # voir — donc exiger le prédicat de CHACUN condamnerait le bon code.
    tests = [ast.unparse(n.test) for n in holders]
    gated = [t_ for t_ in tests if "secret" in t_]
    assert gated, (
        f"aucune des conditions {tests} n'interroge les champs secrets : la légende "
        "s'affiche sur les formulaires qui n'en ont pas, où elle annonce une "
        "propriété fausse. Un `if True` ou une liste de plateformes tapée à la main "
        "ramènerait le défaut sous une autre forme.")
    assert any("fields_def" in t_ for t_ in gated), (
        f"`{gated}` ne lit pas les champs de CE formulaire — la condition doit être "
        "dérivée du registre, pas d'une constante.")


@pytest.mark.parametrize("platform", sorted(PLATFORMS))
def test_a_platform_without_secrets_would_not_reach_the_caption(platform):
    """La condition, évaluée sur les données réelles de chaque plateforme."""
    # The REAL condition, read from `_render.py` and evaluated on this platform's
    # fields. Until 2026-09-26 this test computed `shows` and `has` with the same
    # expression written twice — a tautology that could not fail.
    gate = secret_gate(_RENDER.read_text(encoding="utf-8"))
    assert gate, "no caption condition reads the form's secret fields"
    fields_def = PLATFORMS[platform].get("fields", [])
    shows = eval(gate, {"any": any}, {"fields_def": fields_def})  # noqa: S307
    has = any(f.get("secret") for f in fields_def)
    assert bool(shows) == has, f"{platform} : la condition ne suit pas ses champs"


def test_the_detector_sees_the_defect_it_is_written_for():
    """Non-vacuity: the caption under `if True:` (or under a hand-typed platform list)
    offers no secret gate; under the registry-derived condition it does."""
    def render(cond: str) -> str:
        return (f"if existing_row:\n    if {cond}:\n"
                f"        st.caption(t('{_CAPTION_KEY}'))\n")

    assert secret_gate(render("True")) is None
    assert secret_gate(render("platform in ('meta', 'youtube')")) is None
    good = "any(f.get('secret') for f in fields_def)"
    assert secret_gate(render(good)) is not None
