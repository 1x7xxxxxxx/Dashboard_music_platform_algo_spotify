"""Guard: an artist gives a link, not a page-source hunt.

Type: Utility
Uses: pytest, ast
Triggers: pytest
Persists in: nothing

Error class `setup-step-asks-for-a-developer-gesture`.

Measured 2026-09-03. The SoundCloud setup step read, in full:

    1. Connecté à SoundCloud, ouvrez soundcloud.com/discover
    2. Affichez le CODE SOURCE de la page (Ctrl+U), puis cherchez (Ctrl+F)
       exactement ceci: `soundcloud:users:` — le nombre collé juste après les
       deux-points est votre User ID
    3. Collez ce User ID dans Credentials API

`runbook-artist-test-session.md:127` already said what that costs, in writing:
*« YouTube (créer une clé API Google Cloud) et SoundCloud (afficher le code source
d'une page) ne sont pas des gestes d'artiste. Attends-toi à les faire AVEC lui, en
partage d'écran. »* Measured against production: of the 6 tenants who ever logged in,
3 opened the credentials page and **0 ever produced a SoundCloud row**.

The capability was already in the repo, two functions away. `_render.py`'s
`_resolve_soundcloud_track` calls SoundCloud's official `/resolve`, and its own
comment notes that *"`/resolve` happily returns a USER for a profile URL"* — the exact
thing the setup step needed.

## What this guards, and what it deliberately does not

Two entry points call one function: `_handle_save` (canonical, just before the write) and
`_test_soundcloud` (tolerant read of rows saved before this existed). Both delegate to
`soundcloud_user_id_from_url`, so the RULE exists once. The tests below pin that.

They do **not** demand the same treatment for YouTube. `_platform_youtube` resolves a
handle and then REPORTS the id for the artist to paste, on the recorded grounds that
*« a tenant's identity is not inferred here »*. A profile URL dereferences to exactly
one account; a name search does not. The asymmetry is a decision, and
`RESOLVED_HERE` states it rather than leaving it to be re-litigated.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.utils.platform_identity_resolver import (
    RESOLVED_HERE,
    ResolutionError,
    soundcloud_user_id_from_url,
)


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()
RENDER = REPO / "src" / "dashboard" / "views" / "credentials" / "_render.py"
SC_FORM = REPO / "src" / "dashboard" / "views" / "credentials" / "_platform_soundcloud.py"


# ── The refusals name the artist's next gesture, or say the fault is ours ────

def test_an_empty_link_is_refused_without_a_network_call():
    with pytest.raises(ResolutionError) as exc:
        soundcloud_user_id_from_url("")
    assert exc.value.code == "empty"


def test_a_missing_platform_app_is_reported_as_ours_not_theirs(monkeypatch):
    """`broken-probe-rendered-as-user-fault`: our missing credentials, their message."""
    monkeypatch.delenv("SOUNDCLOUD_CLIENT_ID", raising=False)
    monkeypatch.delenv("SOUNDCLOUD_CLIENT_SECRET", raising=False)
    with pytest.raises(ResolutionError) as exc:
        soundcloud_user_id_from_url("https://soundcloud.com/nasa")
    assert exc.value.code == "app_not_configured"


def test_every_resolution_code_renders_in_both_languages():
    """A code with no sentence behind it is a blank error box.

    The resolver raises codes rather than sentences so that nothing built from a
    caught exception reaches the UI in a credentials module
    (`test_no_probe_surfaces_a_whole_exception`) — but that only helps if every code
    has a rendering. This is the seam where the two halves could drift apart.
    """
    from src.dashboard.utils.i18n_catalog.credentials import EN as CREDENTIALS_EN
    from src.dashboard.views.credentials._render import _RESOLVE_MESSAGES
    from src.utils.platform_identity_resolver import RESOLUTION_CODES

    for code in RESOLUTION_CODES:
        assert code in _RESOLVE_MESSAGES, f"no FR sentence for resolution code {code!r}"
        assert f"credentials.resolve.{code}" in CREDENTIALS_EN, (
            f"no EN entry for resolution code {code!r} — an English reader gets French"
        )


def test_the_resolver_raises_no_rendered_sentence():
    """The reason the code indirection exists, pinned.

    A future edit that goes back to `raise ResolutionError("Collez d'abord…")` would
    put French in `src/utils/` AND re-break the credentials-security guard, since the
    view would have to surface the exception text again to show anything useful.
    """
    import ast

    src = (REPO / "src" / "utils" / "platform_identity_resolver.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call)):
            continue
        for arg in node.exc.args:
            assert isinstance(arg, ast.Constant) and " " not in str(arg.value), (
                f"ResolutionError at line {node.lineno} is raised with a sentence, not "
                "a code. Sentences here bypass i18n and force the view to surface the "
                "exception itself."
            )


# ── One rule, and both entry points go through it ────────────────────────────

def test_the_save_path_normalises_before_writing():
    """AST: the save path must resolve, not store what was typed.

    Resolving only in the connection test would prove the link good and still persist
    the URL — and `soundcloud_daily` reads the column, not the test.
    """
    tree = ast.parse(RENDER.read_text(encoding="utf-8"))
    save = next((n for n in ast.walk(tree)
                 if isinstance(n, ast.FunctionDef) and n.name == "_handle_save"),
                None)
    assert save is not None, "_handle_save is gone — this guard points at air"
    called = {n.func.id for n in ast.walk(save)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "soundcloud_user_id_from_url" in called, (
        "the save path no longer resolves the SoundCloud link. A URL would be written "
        "into a column the collector reads as a numeric user id: the row looks filled, "
        "counts as connected on every surface, and collects nothing."
    )


def test_a_bad_link_aborts_the_save_instead_of_storing_it():
    """AST: the failure branch must `return`, not fall through to the write.

    A row that looks filled but cannot collect is worse than an empty one — every
    surface that counts rows instead of identities reads it as connected.
    """
    src = RENDER.read_text(encoding="utf-8")
    tree = ast.parse(src)
    save = next(n for n in ast.walk(tree)
                if isinstance(n, ast.FunctionDef) and n.name == "_handle_save")
    handlers = [h for h in ast.walk(save) if isinstance(h, ast.ExceptHandler)
                and isinstance(h.type, ast.Name) and h.type.id == "ResolutionError"]
    assert handlers, "no ResolutionError handler on the save path"
    for h in handlers:
        assert any(isinstance(n, ast.Return) for n in ast.walk(h)), (
            "the ResolutionError branch does not return: execution continues to the "
            "write and stores the unresolved value."
        )


def test_the_connection_test_shares_the_same_resolver():
    """Two entry points are fine; two implementations of the rule are not."""
    tree = ast.parse(SC_FORM.read_text(encoding="utf-8"))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "soundcloud_user_id_from_url" in called


# ── The asymmetry with YouTube is declared, not accidental ──────────────────

def test_the_registry_states_which_platforms_are_resolved_here():
    assert RESOLVED_HERE["soundcloud"] is True
    for other in ("spotify", "youtube", "meta", "instagram"):
        assert RESOLVED_HERE[other] is False, (
            f"{other} is marked as resolved by this module. Spotify and YouTube "
            "already have their own path, Meta and Instagram have no public one — "
            "a second implementation is how two rules drift apart."
        )


def test_youtube_still_reports_rather_than_substitutes():
    """Pins the decision this change was one refactor away from overturning.

    `_platform_youtube` resolves a handle and hands the `UC…` back for the artist to
    paste: *« never substitute it silently: a tenant's identity is not inferred
    here »*. A profile URL dereferences to one account; a name search does not.
    """
    yt = (REPO / "src" / "dashboard" / "views" / "credentials"
          / "_platform_youtube.py").read_text(encoding="utf-8")
    assert "credentials.youtube.handle_resolved" in yt, (
        "the resolve-and-REPORT message is gone from the YouTube form — either it now "
        "substitutes silently, which reverses a recorded decision, or the key moved "
        "and this guard needs re-pointing."
    )
