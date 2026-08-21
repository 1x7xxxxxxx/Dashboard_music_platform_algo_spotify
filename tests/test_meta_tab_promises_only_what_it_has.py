"""Guard — a credentials tab may not name a field it does not have.

Error class `operator-guidance-phantom-or-wrong-auth`.

The Meta tab declares two fields: `account_id` and `ig_user_id`. It nevertheless
read `access_token` / `app_id` / `app_secret` out of the tenant's saved values —
always three empty strings — so:

  * `_fetch_meta_token_expiry` returned None on its first guard EVERY time, and the
    caller's else-branch fired on EVERY save for EVERY artist: "⚠️ Impossible de
    récupérer la date d'expiration du token Meta … Le renouvellement automatique ne
    fonctionnera pas."
  * the "🔄 Rafraîchir le token Meta" button always answered "App ID ou App Secret
    manquant — renseigner d'abord ces champs", naming fields the form does not have.

Two beta testers reported "the credentials don't work". They were reading a
permanent warning about a CENTRAL credential (ADR-006: the Meta token is a platform
System User token that never expires) displayed on a PER-ARTIST page.

The generalised rule, not the instance: no user-facing string in a platform's UI may
name a credential field that is not one of that platform's own fields.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.dashboard.views.credentials._registry import PLATFORMS

REPO = Path(__file__).resolve().parents[1]
UI_DIR = REPO / "src/dashboard/views/credentials"

# Phrases naming a credential → the field key they mean. These are FIELD LABELS,
# not values: the allowlist pragmas below are there because the secret scanner
# matches on the keyword, and a guard about credential fields necessarily says
# their names out loud.
_FIELD_PHRASES = {
    "app id": "app_id",
    "app secret": "app_secret",  # pragma: allowlist secret
    "access token": "access_token",
    "client id": "client_id",
    "client secret": "client_secret",  # pragma: allowlist secret
    "api key": "api_key",
}


def _ui_strings(path: Path) -> list[str]:
    """String constants in CODE. Docstrings and comments are excluded on purpose.

    Comments are where the removal of this defect is explained, and they name the
    very fields the rule forbids. A textual signature would go red on the
    explanation of its own fix — so we read the tree, and drop docstrings.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc is not None:
                docstrings.add(id(node.body[0].value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings]


# A mention alone is not the defect. Explaining the central model — "the admin
# creates the shared app once, you only provide your User ID" — is exactly the
# ADR-006 explanation an artist needs, and naming the shared credential is how you
# give it. The defect is telling someone to ENTER something no box accepts. These
# markers are what turns a mention into an instruction.
_ENTRY_MARKERS = (
    "saisir", "saisis", "renseigne", "renseigner", "remplir", "remplis",
    "le champ", "les champs", "ces champs", "| champ", "the field", "the fields",
    "enter the", "fill in",
)


def _is_entry_instruction(text: str) -> bool:
    low = text.lower()
    return any(m in low for m in _ENTRY_MARKERS)


@pytest.mark.parametrize("platform_key", sorted(PLATFORMS))
def test_a_tab_never_names_a_field_it_does_not_have(platform_key: str) -> None:
    module = UI_DIR / f"_platform_{platform_key}.py"
    if not module.exists():
        pytest.skip(f"no dedicated module for {platform_key}")
    own = {f["key"] for f in PLATFORMS[platform_key]["fields"]}
    offences = []
    for text in _ui_strings(module):
        low = text.lower()
        if not _is_entry_instruction(text):
            continue
        for phrase, key in _FIELD_PHRASES.items():
            if phrase in low and key not in own:
                offences.append((key, " ".join(text.split())[:90]))
    assert not offences, (
        f"the {platform_key} tab has fields {sorted(own)} but tells the reader to "
        f"enter absent field(s): {offences}"
    )


def test_the_render_path_names_no_absent_meta_field() -> None:
    """`_render.py` is shared by every tab, so it must name none of them."""
    offences = []
    for text in _ui_strings(UI_DIR / "_render.py"):
        low = text.lower()
        for phrase, key in _FIELD_PHRASES.items():
            if phrase in low:
                offences.append((key, " ".join(text.split())[:90]))
    assert not offences, f"_render.py names credential field(s) in UI strings: {offences}"


def test_the_dead_expiry_probe_is_not_called_anywhere() -> None:
    """It could only ever return None; its caller turned that into a permanent warning."""
    called = []
    for path in UI_DIR.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                name = getattr(fn, "id", None) or getattr(fn, "attr", None)
                if name == "_fetch_meta_token_expiry":
                    called.append(f"{path.name}:{node.lineno}")
    assert not called, f"_fetch_meta_token_expiry is called again at {called}"
