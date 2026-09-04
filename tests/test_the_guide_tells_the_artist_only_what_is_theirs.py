"""A credential guide must not hand the artist the operator's job, or hide their own.

Type: Test
Uses: ast, the credential guide catalogues
Depends on: src/dashboard/content/credential_guides*.py, credential_guides_st.py, guides/guide_pdf.py
Persists in: nothing

Two defects, found by `make artist-firstlook` on 2026-08-30
------------------------------------------------------------
**1. Work that is not theirs, shown to them.** A brand-new artist read, on the
Credentials page:

    **Admin (une seule fois)** : créer une app sur developer.spotify.com… renseigner
    SPOTIFY_CLIENT_ID en variables d'environnement. **Les artistes n'ont alors qu'à
    coller le lien de leur profil.**

The last sentence proves the text was written FOR the operator. It was rendered
unconditionally — on screen and in the welcome PDF — on the very page where the
artist's whole job is to paste one link.

**2. Work that IS theirs, labelled as somebody else's.** The Meta guide carried, as
a footnote: "**Prérequis admin** : votre compte publicitaire doit être lié à l'app
partagée…". The information was there — my first report wrongly said it was absent —
but the label told the artist it was not their concern, while it is THEIR ad
account, in THEIR Business Manager, and nobody else can do it for them. So it did
not get done, the connection test failed, and nothing said why. That is the
2026-06-19 session.

The fix is one field: `admin_note` says who the text is for, instead of leaving the
renderer to guess. The sharing requirement moved from a footnote to a numbered step,
before the connection test, worded as the artist's action.
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_CONTENT = _ROOT / "src" / "dashboard" / "content"
_ST = _CONTENT.parent / "content" / "credential_guides_st.py"
_PDF = _ROOT / "src" / "dashboard" / "guides" / "guide_pdf.py"

# Wording that only an operator can act on. An artist has none of these accesses.
_OPERATOR_ONLY = (
    "variables d'environnement", "environment variables",
    "developer.spotify.com", "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET",
    "System User",
)


def _catalogues():
    import sys
    sys.path.insert(0, str(_ROOT))
    import src.dashboard.content.credential_guides as fr
    import src.dashboard.content.credential_guides_en as en
    out = []
    for mod, lang in ((fr, "fr"), (en, "en")):
        for value in vars(mod).values():
            if hasattr(value, "key") and hasattr(value, "steps"):
                out.append((lang, value))
    return out


def test_no_artist_facing_text_asks_for_operator_access():
    """`note` and `steps` are what the artist reads. They must be actionable BY them."""
    offenders = []
    for lang, guide in _catalogues():
        artist_text = " ".join(
            [guide.note or ""] + [str(s.text) for s in (guide.steps or [])])
        for phrase in _OPERATOR_ONLY:
            if phrase in artist_text:
                offenders.append(f"{lang}/{guide.key}: {phrase!r}")
    assert not offenders, (
        "These ask the artist for access only the operator has:\n  "
        + "\n  ".join(sorted(offenders))
        + "\n\nMove the sentence to `admin_note` — it is rendered to admins only, and "
          "never into the artist's welcome PDF."
    )


def test_the_meta_sharing_step_is_the_artists_and_comes_before_the_test():
    """The step that blocked the 2026-06-19 session, in both languages."""
    for lang, guide in _catalogues():
        if guide.key != "meta":
            continue
        texts = [str(s.text) for s in guide.steps]
        # The CONFIGURED app name, never the literal that shipped in 2026. The app
        # is renameable on Meta's side (`META_APP_DISPLAY_NAME`), and a guard that
        # greps a hardcoded string would then go red on correct code while staying
        # green on a guide that names an app nobody can find — the failure mode this
        # repo calls "a guard whose scope is the defect".
        from src.dashboard.content.credential_guides import META_APP_DISPLAY_NAME

        share = [i for i, t in enumerate(texts)
                 if META_APP_DISPLAY_NAME in t]
        assert share, (
            f"{lang}/meta no longer tells the artist to share their ad account with "
            f"{META_APP_DISPLAY_NAME}. Without it the collection reads nothing, "
            "whatever ID they paste."
        )
        test_step = [i for i, t in enumerate(texts)
                     if "Tester la connexion" in t or "Test connection" in t
                     or "API Credentials → Meta" in t or "Credentials API → Meta" in t]
        if test_step:
            assert min(share) < min(test_step), (
                f"{lang}/meta puts the sharing step AFTER the connection test. The "
                "test fails without it, so the artist meets the failure before the fix."
            )


def test_admin_note_is_gated_on_screen_and_absent_from_the_pdf():
    """Both surfaces, because the text reached the artist through both."""
    st_src = _ST.read_text(encoding="utf-8")
    assert "admin_note" in st_src and "is_admin()" in st_src, (
        "credential_guides_st.py no longer gates admin_note on is_admin() — the "
        "operator's instructions are back on the artist's screen."
    )
    pdf_src = _PDF.read_text(encoding="utf-8")
    tree = ast.parse(pdf_src)
    renders_admin_note = any(
        isinstance(n, ast.Attribute) and n.attr == "admin_note"
        and not isinstance(getattr(n, "ctx", None), ast.Store)
        for n in ast.walk(tree)
    )
    assert not renders_admin_note, (
        "guide_pdf.py reads `admin_note`. That PDF is attached to an artist's welcome "
        "e-mail; the operator's setup steps must never travel with it."
    )


def test_every_guide_still_tells_the_artist_something():
    """The fix must not have emptied the guides while silencing them."""
    thin = [f"{lang}/{g.key}" for lang, g in _catalogues() if not g.steps]
    assert not thin, f"these guides now have no steps at all: {thin}"
