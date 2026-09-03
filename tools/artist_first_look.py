#!/usr/bin/env python3
"""Show what a BRAND-NEW artist actually sees, page by page. READ-ONLY on real data.

Type: Utility
Uses: streamlit.testing.v1.AppTest, PostgresHandler
Triggers: `make artist-firstlook` — before inviting anyone, and after touching a view
Persists in: nothing (a throwaway tenant is created and deleted, unless --artist)

Why this exists, and why the render-smoke is not it
---------------------------------------------------
`tests/test_views_render_smoke.py` already renders every view for an empty tenant.
Its single assertion is "no exception" — and that is exactly the assertion that was
green while the two beta sessions were failing.

What those sessions actually found, in ~30 field notes, was never a crash. It was
**correct code that nothing reached**: an onboarding page outside the navigation, a
step whose page key was thrown away, an OS selector wired to a function with no
caller, a guide delivered only by e-mail. Six occurrences in one session. A render
test cannot see any of them, because each page renders perfectly.

So this tool does not ask "did it raise". It prints **what is on the screen**: the
title, the buttons, the messages, and whether the page offers the artist anything to
do at all. A page with nothing actionable is reported as a DEAD END — that is the
shape those six defects had.

Usage
-----
    make artist-firstlook                 # throwaway tenant, created then deleted
    make artist-firstlook ARTIST=12       # look through an EXISTING artist's eyes
    python3 tools/artist_first_look.py --json   # same, machine-readable

Never writes to an existing tenant's data: with --artist it only reads.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid

def _repo_root() -> str:
    """Where `src/` lives — the file's own directory is not a safe answer.

    `make artist-firstlook-prod` copies this script into the container at /tmp, so
    `dirname(__file__)/..` resolves to `/` and the import of `src` fails. Look for a
    directory that actually CONTAINS src/, starting from the obvious candidates.
    """
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (os.path.join(here, ".."), os.getcwd(), "/app", "/opt/airflow"):
        if os.path.isdir(os.path.join(candidate, "src")):
            return os.path.abspath(candidate)
    return os.path.abspath(os.path.join(here, ".."))


ROOT = _repo_root()
sys.path.insert(0, ROOT)
os.chdir(ROOT)   # the rendered script uses os.getcwd() to find the package

from src.utils.env_files import load_project_env  # noqa: E402

load_project_env()

# The journey, in the order an artist meets it. Kept explicit rather than derived
# from _NAV_SECTIONS: the point is to walk what a NEW artist walks, which is a
# deliberate subset, not every page that exists.
# `useful_links`, `onboarding_health`, `alerts`… sont dans `app._ADMIN_ONLY` : un
# artiste ne les voit jamais dans sa navigation. Les mettre ici faisait remonter
# « ⛔ Accès réservé à l'administrateur » comme un défaut du produit, alors que
# c'était une erreur de CETTE liste.
JOURNEY = [
    ("onboarding", "Le parcours guidé, juste après la vérification de l'e-mail"),
    ("home", "L'accueil — la première chose vue à chaque connexion"),
    ("credentials", "Connecter ses plateformes"),
    ("process_guide", "Le guide de démarrage"),
    ("upload_csv", "Importer un CSV Spotify for Artists"),
    ("account", "Son compte"),
]

# The session keys a REAL login sets (src/dashboard/auth.py:308-316), all of them.
# The first version set four of the six and `account` answered "Session expirée" —
# a finding about this tool, not about the product. A harness that models the
# session badly reports its own gaps as defects.
_SCRIPT = """
import sys
sys.path.insert(0, {root!r})
import streamlit as st
st.session_state["authenticated"] = True
st.session_state["username"]  = {username!r}
st.session_state["name"]      = "firstlook@test"
st.session_state["email"]     = "firstlook@test"
st.session_state["user_id"]   = {user_id}
st.session_state["artist_id"] = {artist_id}
st.session_state["role"]      = "artist"
from src.dashboard.views.{view} import show
show()
"""


def _db():
    from src.dashboard.utils import get_db_connection
    db = get_db_connection()
    if db is None:
        print("❌ base de données injoignable — impossible de créer un locataire", file=sys.stderr)
        raise SystemExit(2)
    return db


def _make_throwaway() -> tuple[int, int, str]:
    """A tenant AND its user row — the shape a real signup leaves behind.

    Creating only the `saas_artists` row was the first version, and `account`
    answered "Utilisateur introuvable": a finding about this tool, not the product.
    A new artist has a row in BOTH tables, so the throwaway must too, or every page
    that reads the user reports a defect that does not exist.
    """
    db = _db()
    tag = uuid.uuid4().hex[:8]
    try:
        artist_id = db.fetch_query(
            "INSERT INTO saas_artists (name, slug, tier, active) "
            "VALUES (%s, %s, 'free', TRUE) RETURNING id",
            (f"First Look {tag}", f"firstlook-{tag}"))[0][0]
        user_id = db.fetch_query(
            "INSERT INTO saas_users (username, email, password_hash, role, "
            "                        artist_id, active, email_verified) "
            "VALUES (%s, %s, %s, 'artist', %s, TRUE, TRUE) RETURNING id",
            (f"firstlook_{tag}", f"firstlook+{tag}@example.invalid",
             "!never-a-valid-hash", artist_id))[0][0]
        return artist_id, user_id, f"firstlook_{tag}"
    finally:
        db.close()


def _drop_throwaway(artist_id: int, user_id: int) -> None:
    db = _db()
    try:
        db.execute_query("DELETE FROM saas_users WHERE id = %s", (user_id,))
        db.execute_query("DELETE FROM artist_credentials WHERE artist_id = %s", (artist_id,))
        db.execute_query("DELETE FROM saas_artists WHERE id = %s", (artist_id,))
    finally:
        db.close()


def _texts(items) -> list[str]:
    out = []
    for el in items:
        v = getattr(el, "value", None) or getattr(el, "body", None) or getattr(el, "label", None)
        if v:
            out.append(" ".join(str(v).split())[:160])
    return out


def _offers_a_download(view: str) -> bool:
    """Does this view hand the artist a file? Read from the source, not the render.

    `AppTest` exposes no `download_button` accessor, so a page whose only action is
    a download reads as a dead end. `process_guide` — two download buttons — was
    reported as one until this existed.
    """
    import pathlib
    # ROOT, not `parents[1]`: in the container this file sits at /tmp, so the
    # relative walk lands on `/` and every page reads as offering no download —
    # `process_guide` was flagged a dead end for exactly that reason. Same defect as
    # the import path above; fixing one and not the other is how a tool half-works.
    root = pathlib.Path(ROOT) / "src" / "dashboard" / "views"
    for candidate in (root / f"{view}.py", root / view / "__init__.py"):
        if candidate.exists():
            body = candidate.read_text(encoding="utf-8")
            return "download_button" in body or "link_button" in body
    return False


def _has_any(at, names) -> tuple[bool, list[str]]:
    """`(found_one, unreadable)` — what the page carries, and what we could not check.

    The second half exists because the first version returned a bare `False` and was
    WRONG on the most important page in the product. Measured 2026-09-03:

    `make artist-firstlook` reported `upload_csv` as a CUL-DE-SAC — "nothing to click,
    type or download" — on the page that has a `st.file_uploader` and a 0-out-of-4
    completion rate. The page was fine. The tool ran under the SYSTEM `python3`, which
    carries **Streamlit 1.54**, where `AppTest` has no `file_uploader` attribute at
    all. The old `except: continue` turned that `AttributeError` into a "no".

    "I cannot read this" is not "this is absent". Collapsing the two is the same class
    as `broken-probe-rendered-as-user-fault`, and here it accused the product of a
    defect it did not have — on exactly the page a real defect would matter most.

    So an unreadable accessor is now REPORTED, never silently counted as absent.
    """
    unreadable: list[str] = []
    found = False
    for name in names:
        try:
            if len(getattr(at, name)):
                found = True
        except AttributeError:
            # This Streamlit's AppTest has no such accessor — a fact about the
            # interpreter, not about the page.
            unreadable.append(name)
        except Exception:  # noqa: BLE001 — a describing tool must survive its subject
            unreadable.append(name)
    return found, unreadable


def look(view: str, artist_id: int, user_id: int, username: str) -> dict:
    """Render one page as this tenant and describe what is on it."""
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(_SCRIPT.format(root=os.getcwd(), view=view, artist_id=artist_id,
                       user_id=user_id, username=username))
    try:
        at.run(timeout=180)
    except Exception as e:  # noqa: BLE001 — a crash is a finding, not a stop
        return {"view": view, "crash": f"{type(e).__name__}: {e}"[:200]}

    exc = [str(getattr(e, "value", e))[:200] for e in at.exception]
    buttons = _texts(at.button)

    _interactive, _unreadable = _has_any(
        at, ("text_input", "file_uploader", "selectbox", "radio",
             "checkbox", "text_area", "number_input"))
    return {
        "view": view,
        "exception": exc,
        "titles": _texts(at.title) + _texts(at.subheader),
        "buttons": buttons,
        "errors": _texts(at.error),
        "warnings": _texts(at.warning),
        "infos": _texts(at.info),
        # A page an artist cannot act on is the shape of the six 2026-08-23 defects.
        # `at.download_button` does not exist on AppTest — checked the hard way, it
        # raised AttributeError mid-journey and killed the run. Probe each accessor
        # defensively: this tool must survive the page it is describing.
        # A verdict of "dead end" is only honest when every accessor was READABLE.
        # With one unreadable, the right answer is "unknown" — see `_has_any`.
        "dead_end": (not buttons and not _interactive
                     and not _offers_a_download(view) and not _unreadable),
        "unreadable": _unreadable,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--artist", type=int,
                    help="regarder par les yeux d'un artiste EXISTANT (lecture seule)")
    ap.add_argument("--json", action="store_true", help="sortie machine")
    args = ap.parse_args()

    throwaway = args.artist is None
    user_id, username = 0, "firstlook"
    if throwaway:
        artist_id, user_id, username = _make_throwaway()
    else:
        artist_id = args.artist
        row = _db()
        try:
            got = row.fetch_query(
                "SELECT id, username FROM saas_users WHERE artist_id = %s LIMIT 1",
                (artist_id,))
            if got:
                user_id, username = got[0][0], got[0][1]
        finally:
            row.close()
        if not user_id:
            # Refuse rather than render as a user who does not exist. Measured
            # 2026-09-03: `--artist 17` against the LOCAL database produced
            # « Utilisateur introuvable » on the account page and a CUL-DE-SAC
            # verdict — findings about nothing, indistinguishable from an app
            # defect. Artist 17 has a user row in PRODUCTION and none locally.
            msg = (
                "\u274c le locataire {aid} n'a aucune ligne dans `saas_users` sur "
                "CETTE base.\n"
                "   Cet outil lit la base LOCALE (127.0.0.1:5433). Pour un artiste "
                "qui n'existe qu'en production :\n"
                "     make artist-firstlook-prod PROD_SSH=root@<hote>\n"
                "   Sans utilisateur, chaque page rendrait \u00ab Utilisateur "
                "introuvable \u00bb \u2014 un constat sur la base, pas sur l'app."
            ).format(aid=artist_id)
            print(msg, file=sys.stderr)
            return 2
    if throwaway:
        print(f"▶ locataire jetable créé : artist_id={artist_id} (supprimé à la fin)\n")
    else:
        print(f"▶ vue par les yeux de l'artiste {artist_id} — lecture seule\n")

    results = []
    try:
        for view, why in JOURNEY:
            r = look(view, artist_id, user_id, username)
            r["why"] = why
            results.append(r)
            if args.json:
                continue
            head = "❌" if (r.get("crash") or r.get("exception")) else (
                "🚧" if r.get("dead_end") else "✅")
            print(f"{head} {view:20} {why}")
            if r.get("crash"):
                print(f"     PLANTE : {r['crash']}")
            for e in r.get("exception", []):
                print(f"     EXCEPTION : {e}")
            for t in r.get("titles", [])[:3]:
                print(f"     titre    │ {t}")
            for b in r.get("buttons", [])[:6]:
                print(f"     bouton   │ {b}")
            for m in r.get("errors", []):
                print(f"     ERREUR   │ {m}")
            for m in r.get("warnings", []):
                print(f"     alerte   │ {m}")
            for m in r.get("infos", [])[:3]:
                print(f"     info     │ {m}")
            if r.get("unreadable"):
                # Loud, because silence here is what produced a false CUL-DE-SAC on
                # `upload_csv`: this Streamlit's AppTest cannot see these element
                # kinds, so no verdict about them is possible.
                print(f"     ⚠ NON LISIBLE : {', '.join(r['unreadable'])} — "
                      f"AppTest de ce Streamlit ne les expose pas, verdict impossible")
            if r.get("dead_end"):
                print("     🚧 CUL-DE-SAC : rien à cliquer, saisir ou télécharger sur cette page")
            print()
    finally:
        if throwaway:
            _drop_throwaway(artist_id, user_id)
            print(f"▶ locataire jetable {artist_id} supprimé")

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))

    broken = [r["view"] for r in results if r.get("crash") or r.get("exception")]
    dead = [r["view"] for r in results if r.get("dead_end")]
    print(f"\n{len(results)} pages · {len(broken)} en erreur · {len(dead)} cul-de-sac")
    if broken:
        print(f"  ❌ {broken}")
    if dead:
        print(f"  🚧 {dead}")
    return 1 if broken else 0


if __name__ == "__main__":
    raise SystemExit(main())
