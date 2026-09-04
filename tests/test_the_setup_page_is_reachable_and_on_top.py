"""Guards: the setup assistant is reachable, on top, and it decides the landing.

Type: Utility
Uses: ast, pathlib
Triggers: pytest
Persists in: nothing

Five defects, all reported from ONE real second login on the sandbox tenant
(2026-09-04), all of the same family — a surface that exists and that nothing leads to:

1. « c'est tout en bas du volet de navigation » — the `### Étapes` list was written by
   `views/onboarding.show()`, i.e. during the CONTENT phase, so it landed under the
   whole sidebar including the logout button.
2. « impossible de revenir aux différentes étapes de config » — the three steps were
   `st.markdown`. They NAMED the steps without leading to them. Exactly the defect the
   home page's four steps had, fixed there on 2026-08-30 for the same reason.
3. « je ne suis plus sur étapes 1 2 3 » — the landing router asked "has this artist
   declared NOTHING?" while the home page asked "is the setup FINISHED?". One declared
   identity was enough to make the assistant disappear at 1/4.
4. « il n'y a toujours pas d'onglet sélectionné dans le navigateur » — the init path set
   every section radio to `None`, so the menu highlighted nothing while the content
   rendered a page. `goto()` reproduced it on every programmatic navigation.
5. « remonter … artiste <nom> au niveau de votre plan : premium » — the two halves of
   the same identity sat at the two ends of the sidebar.

Each test below fails on the state of the code BEFORE the fix; each was verified red by
mutation, not assumed to be.
"""
from __future__ import annotations

import ast
from pathlib import Path


def _repo_root() -> Path:
    for d in Path(__file__).resolve().parents:
        if (d / ".claude").is_dir():
            return d
    raise RuntimeError("no .claude/ above this test")


REPO = _repo_root()
APP = REPO / "src" / "dashboard" / "app.py"
ONB = REPO / "src" / "dashboard" / "views" / "onboarding.py"
AUTH = REPO / "src" / "dashboard" / "auth.py"
HOME = REPO / "src" / "dashboard" / "views" / "home.py"


def _fn(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == name), None)
    assert fn is not None, f"{path.name} no longer defines {name}()"
    return fn


def _call_lines(fn: ast.AST, name: str) -> list[int]:
    """Line numbers where `name` is called (bare or as an attribute)."""
    out = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if (isinstance(f, ast.Name) and f.id == name) or \
           (isinstance(f, ast.Attribute) and f.attr == name):
            out.append(node.lineno)
    return out


# ── 1. Position ───────────────────────────────────────────────────────────────

def test_the_step_list_is_drawn_before_the_navigation():
    """Above the menu, not under the logout button."""
    body = _fn(APP, "_main_body")
    steps = _call_lines(body, "render_sidebar_steps")
    nav = _call_lines(body, "render_navigation")
    assert steps, (
        "_main_body no longer draws the assistant's steps. They would go back to being "
        "written by views/onboarding.show(), i.e. after the entire sidebar."
    )
    assert nav, "_main_body no longer renders the navigation"
    assert min(steps) < min(nav), (
        "the step list is drawn after the navigation — it reads as a footer, which is "
        "exactly what was reported."
    )


def test_the_view_no_longer_writes_the_sidebar_itself():
    """One writer for that block. Two would put it in two places at once."""
    show = _fn(ONB, "show")
    sidebar_writes = [n.lineno for n in ast.walk(show)
                      if isinstance(n, ast.Attribute) and n.attr == "sidebar"]
    assert not sidebar_writes, (
        f"onboarding.show() writes st.sidebar at line(s) {sidebar_writes}. That runs in "
        "the content phase, so the block lands under the whole sidebar."
    )


def test_the_identity_block_carries_the_plan_and_is_drawn_before_the_nav():
    """« artiste <nom> » and « Votre plan » are one block, at the top."""
    auth_src = AUTH.read_text(encoding="utf-8")
    assert "nav.plan_badge_premium" in auth_src, (
        "the plan badge left show_user_sidebar(); the identity and its plan are back at "
        "the two ends of the sidebar."
    )
    assert "nav.plan_badge_premium" not in APP.read_text(encoding="utf-8"), (
        "the plan badge is rendered in app.py too — two surfaces, one fact.")
    body = _fn(APP, "_main_body")
    ident = _call_lines(body, "show_user_sidebar")
    nav = _call_lines(body, "render_navigation")
    assert ident and nav and min(ident) < min(nav), (
        "the identity block is drawn after the navigation — that is the bottom of the "
        "sidebar, which is what was reported."
    )


# ── 2. Reachability ───────────────────────────────────────────────────────────

def test_every_step_that_is_not_the_current_one_is_a_button():
    """A step you cannot click is a step you cannot go back to."""
    fn = _fn(ONB, "render_sidebar_steps")
    buttons = _call_lines(fn, "button")
    assert buttons, (
        "render_sidebar_steps draws no button: the three steps are text again, and "
        "« impossible de revenir aux différentes étapes de config » is back."
    )


def test_the_assistant_offers_a_way_into_the_app_and_a_way_to_stop_showing_it():
    """A screen you cannot leave is a door, not a help page."""
    fn = _fn(ONB, "_render_landing_choice")
    assert _call_lines(fn, "button"), "no way out of the setup page"
    assert _call_lines(fn, "checkbox"), (
        "no checkbox: the artist cannot decide to stop landing here.")
    assert _call_lines(fn, "set_show_on_login"), (
        "the checkbox is not persisted — a login preference that does not survive the "
        "login answers nothing."
    )


# ── 3. One definition of 'finished' ───────────────────────────────────────────

def test_the_landing_asks_whether_the_setup_is_FINISHED():
    src = ast.get_source_segment(
        APP.read_text(encoding="utf-8"), _fn(APP, "_setup_is_unfinished")) or ""
    assert "read_setup_state" in src, (
        "the first-run predicate no longer reads the shared completion state.")
    assert "artist_readiness" not in src, (
        "the router is back on artist_readiness, whose 'all todo' threshold means "
        "'has not STARTED' — one declared identity made the assistant disappear."
    )


def test_the_first_run_is_decided_whatever_the_entry_path():
    """Not only when the session has no page yet.

    The welcome e-mail links to `?page=onboarding`, `_main_body` pins that parameter
    BEFORE the sidebar runs, so `_nav_page` was already known and the repair branch —
    the only place that armed the flag — never fired. An artist arriving by the mail
    link, i.e. the NOMINAL path, got the whole menu. Reported on 2026-09-04:
    « normalement la première fois qu'on se connecte on n'a pas accès au volet de
    navigation, il faudrait le remettre ».
    """
    fn = _fn(APP, "resolve_nav_page")
    calls = _call_lines(fn, "arm_first_run_once")
    assert calls, (
        "resolve_nav_page no longer arms the first-run flag: it would only be set on "
        "the path where the session has no page — never when a link names one."
    )
    # And it must be armed BEFORE the repair branch reads it.
    repair = [n.lineno for n in ast.walk(fn) if isinstance(n, ast.If)
              and "_nav_page" in ast.dump(n.test)]
    assert repair and min(calls) < min(repair), (
        "the flag is armed after the branch that reads it")

    armed = _fn(APP, "arm_first_run_once")
    src = ast.get_source_segment(APP.read_text(encoding="utf-8"), armed) or ""
    assert "_FIRST_RUN_EVALUATED" in src, (
        "nothing stops the decision being re-taken on every rerun: it would re-arm "
        "the focus after the artist has left the setup, taking the menu away again."
    )


def test_both_surfaces_read_the_same_completion_rule():
    """The home page's `{done}/4` and the landing must never disagree again."""
    for path in (APP, HOME):
        assert "setup_completion" in path.read_text(encoding="utf-8"), (
            f"{path.name} no longer goes through utils/setup_completion — the rule is "
            "being restated, which is how the two answers diverged."
        )


# ── 4. The menu agrees with the page ──────────────────────────────────────────

def test_the_menu_selection_is_reasserted_on_every_run():
    """Not only when the state is being repaired.

    `goto()` sets every section radio to None, and `goto` runs on a page whose key IS
    visible — so the repair branch never fires and the menu shows no selection at all.
    """
    fn = _fn(APP, "resolve_nav_page")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name) and n.func.id == "_select_nav_radio"]
    assert calls, "resolve_nav_page never points the radios at the active page"
    # At least one call must sit at the function's TOP level — inside the `if` only
    # would mean "on repair only", which is the bug.
    top_level = []
    for stmt in fn.body:
        for node in ast.walk(stmt):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "_select_nav_radio"
                    and not isinstance(stmt, (ast.If, ast.Try, ast.For, ast.While))):
                top_level.append(node.lineno)
    assert top_level, (
        "_select_nav_radio is only called inside a conditional — after goto(), the "
        "condition is false and the menu highlights nothing."
    )


# ── 5. A view may navigate without crashing the page ──────────────────────────

NAV = REPO / "src" / "dashboard" / "utils" / "navigation.py"


def test_goto_does_not_write_widget_keys():
    """Error class: writing a widget's session key after the widget exists.

    `goto()` is called from VIEWS — the content phase — and the sidebar radios are
    instantiated before that. It used to set every `_nav_<section>` key to None, which
    Streamlit refuses:

        StreamlitAPIException: `st.session_state._nav_reports` cannot be modified
        after the widget with key `_nav_reports` is instantiated.

    So EVERY programmatic navigation from a view raised — the four home-page steps
    included. On the assistant it was masked by an early `?page=onboarding` route that
    rendered no sidebar at all; removing that route on 2026-09-04 is what exposed it,
    live in a browser.

    Menu/page agreement now belongs to `app.resolve_nav_page`, which runs before the
    widgets exist. Nothing else may touch those keys.
    """
    fn = _fn(NAV, "goto")
    writes = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not (isinstance(target, ast.Subscript)
                    and isinstance(target.value, ast.Attribute)
                    and target.value.attr == "session_state"):
                continue
            key = target.slice
            # `_nav_page` is plain state, not a widget — it is the one legal write.
            if isinstance(key, ast.Constant) and key.value == "_nav_page":
                continue
            if isinstance(key, ast.Name) and key.id == "_PAGE_KEY":
                continue
            writes.append(ast.dump(key)[:60])
    assert not writes, (
        f"goto() writes session keys other than _nav_page: {writes}. Called from a "
        "view, that raises StreamlitAPIException on any key that is a widget's."
    )


def test_the_assistant_has_no_early_route_that_skips_the_sidebar():
    """`?page=onboarding` must render INSIDE the app shell, like every other page."""
    body = _fn(APP, "_main_body")
    src = ast.get_source_segment(APP.read_text(encoding="utf-8"), body) or ""
    head = src.split("_check_db_health")[0]
    assert "show_onboarding()" not in head, (
        "the early ?page=onboarding route is back: it renders the assistant alone and "
        "calls st.stop(), so the sidebar — steps, menu, identity — never renders. And "
        "because the URL mirror writes ?page=<page> on every run, that branch fires on "
        "every rerun once the assistant has been shown once."
    )


# ── 6. First run: the assistant and nothing else, exit at the bottom ──────────

def test_the_first_run_hides_the_menu_and_the_collect_button():
    """« lors de la première connexion qu'on ait accès uniquement à la mise en route ».

    A full 40-entry menu and a collect button next to an account that has declared no
    identity offer forty destinations with nothing to show and one action that can
    collect nothing. The exit is the button at the bottom of the page, and unchecking
    the box brings the menu back on the spot — so this is a focus, not a door.
    """
    body = _fn(APP, "_main_body")
    guarded = []
    for node in ast.walk(body):
        if not isinstance(node, ast.If):
            continue
        # The nav + collect panel must live in the `else` of the focus test.
        names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
        if "FIRST_RUN_FOCUS" not in names and "_focus" not in names:
            continue
        else_calls = {c for stmt in node.orelse for c in _names_called(stmt)}
        if {"render_navigation", "show_data_collection_panel"} <= else_calls:
            guarded.append(node.lineno)
    assert guarded, (
        "the navigation and the collect button are not gated on the first-run focus "
        "flag: a brand-new account gets the whole app instead of its setup."
    )


def _names_called(node: ast.AST) -> set[str]:
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                out.add(f.id)
            elif isinstance(f, ast.Attribute):
                out.add(f.attr)
    return out


def test_the_way_out_is_rendered_after_the_step_content():
    """« le bouton accéder à l'application [doit être] à la fin ».

    It was above the step's own title: the first thing an artist saw on their setup
    page was the button for leaving it.
    """
    show = _fn(ONB, "show")
    exit_lines = _call_lines(show, "_render_landing_choice")
    # Les deux étapes qui restent. Il y en avait trois jusqu'au 2026-09-04 :
    # `_step_credentials` (qui redisait la liste de plateformes de la page 1) et
    # `_step_ready` (qui redemandait ce que le bouton précédent venait de décider)
    # ont fusionné dans `_step_status`.
    step_lines = (_call_lines(show, "_step_welcome")
                  + _call_lines(show, "_step_status"))
    assert exit_lines and step_lines, "show() no longer renders both"
    assert min(exit_lines) > max(step_lines), (
        "the exit block is rendered before the step content — it reads as a header, "
        "which is what was reported."
    )


def test_the_first_run_covers_the_whole_setup_journey_then_dies():
    """Not just the assistant's own page.

    It cleared on ANY page change, so « Connecter ma sélection » → Credentials killed
    it in one click and that page — the one that must narrow to the ticked platforms —
    showed all six again. Seen in a browser on 2026-09-04, green in every test.
    It now spans the setup pages and dies on the first page that is not one.
    """
    src = APP.read_text(encoding="utf-8")
    tree = ast.parse(src)
    setup = next(
        (n.value for n in ast.walk(tree)
         if isinstance(n, ast.Assign)
         and any(getattr(t, "id", "") == "_SETUP_PAGES" for t in n.targets)),
        None)
    assert setup is not None, "_SETUP_PAGES is gone — the flag is back to one page"
    names = {c.value for c in ast.walk(setup)
             if isinstance(c, ast.Constant) and isinstance(c.value, str)}
    assert {"onboarding", "credentials"} <= names, (
        f"the setup journey no longer includes Credentials: {sorted(names)}. That is "
        "the page the narrowing exists for.")
    assert "home" not in names, (
        "the home page counts as setup: the reduced view would never end")


def test_leaving_the_setup_clears_the_focus():
    """Coming back later through the menu must give the whole app, not the focus."""
    fn = _fn(APP, "resolve_nav_page")
    pops = [n for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "pop"
            and any(isinstance(a, ast.Name) and a.id == "FIRST_RUN_FOCUS" for a in n.args)]
    assert pops, (
        "resolve_nav_page never clears the first-run flag: an artist who later opens "
        "the assistant from the menu would lose the menu."
    )


# ── 7. La mise en route, réduite au strict nécessaire le premier jour ─────────

CREDS = REPO / "src" / "dashboard" / "views" / "credentials" / "router.py"
SANDBOX = REPO / "tools" / "create_sandbox.py"


def test_the_welcome_step_is_three_numbered_blocks_then_the_choice():
    """0 langue · 1 à quoi ça sert · 2 ce que tu as et ce que tu perds · puis on coche.

    Four blocks until 2026-09-04. The fourth — « 3. Ton guide, et ce qui se passe
    ensuite », its two PDF buttons and the two sentences under them — was removed on
    the artist's word: « ça sert à rien, on l'envoie par mail, et sinon je préfère
    qu'il suive la page d'onboarding ». What replaces it is nothing: the page ends on
    the only thing it asks for.

    The ordering assertion survives the deletion because it was never about the
    guide; it is about a reader who picks a language, learns what the tool does, sees
    what they keep and lose, and only then chooses. The picker is now the last term.
    """
    fn = _fn(ONB, "_step_welcome")
    src = ast.get_source_segment(ONB.read_text(encoding="utf-8"), fn) or ""
    lang = src.index("_language_buttons()")
    brief = src.index("1. streaMLytics en bref")
    offer = src.index("onboarding.b2_title")
    pick = src.index("_platform_picker(")
    assert lang < brief < offer < pick, (
        "the blocks are out of order: the reader picks a language, learns what the "
        "tool does, sees what they have and lose, then chooses what to connect."
    )
    assert "onboarding.b3_title" not in src, (
        "the guide block is back on the welcome step — it was removed because the "
        "guide is mailed and downloadable on its own page (📋 Guide de démarrage)"
    )
    assert "download_button" not in src, (
        "a PDF download is back on the welcome step: it opens another context at the "
        "exact moment the page asks for a choice"
    )


def test_the_picker_lays_out_three_derived_columns():
    """Trois colonnes, et leur contenu vient des données — pas de trois listes ici.

    Mesuré au navigateur le 2026-09-04 à 1440 px : x = 380 / 717 / 1055, gauche
    cochée. Ce test ne remesure pas ces pixels — `st.columns` les décide — il fige
    ce qu'un navigateur ne dira jamais : que les groupes sont DÉRIVÉS. Une pile de
    six cases et trois colonnes alimentées par des clés recopiées se ressemblent à
    l'écran ; seule la seconde oublie une plateforme le jour où on en ajoute une.
    """
    fn = _fn(ONB, "_platform_picker")
    src = ast.get_source_segment(ONB.read_text(encoding="utf-8"), fn) or ""
    assert "setup_columns(" in src, (
        "le sélecteur ne dérive plus ses colonnes du registre : il porte sa propre "
        "idée de qui va où, et elle se périmera sans bruit"
    )
    assert "st.columns(len(SETUP_COLUMN_ORDER)" in src, (
        "le nombre de colonnes est écrit en dur : ajouter un groupe en laisserait "
        "un hors de l'écran"
    )
    # Aucune clé de plateforme littérale dans le corps du sélecteur — c'est la forme
    # exacte qu'on refuse.
    from src.dashboard.content.platform_value import PLATFORM_VALUES
    hard = [pv.key for pv in PLATFORM_VALUES if f'"{pv.key}"' in src or f"'{pv.key}'" in src]
    assert not hard, (
        f"le sélecteur nomme {hard} en dur ; il doit lire le registre, sinon la "
        "septième plateforme atterrit dans aucune colonne"
    )


def test_the_trial_says_one_month_not_only_thirty_days():
    body = ONB.read_text(encoding="utf-8")
    assert "1 mois" in body, (
        "the welcome offer no longer says how long it lasts in the words the artist "
        "used. « 30 jours » alone was read as a detail, not as an expiry."
    )


def test_the_language_choice_is_buttons_not_a_second_radio():
    """A second radio would fight the sidebar's on every rerun.

    Two widgets cannot share a key, and two independent radios overwrite each other:
    the page one would undo a choice made in the sidebar, and vice versa. A button
    holds no state — it writes the sidebar radio's key BEFORE that widget is created
    on the next run, exactly like the nav radios.
    """
    fn = _fn(ONB, "_language_buttons")
    assert _call_lines(fn, "button"), "the language block is no longer buttons"
    assert not _call_lines(fn, "radio"), (
        "a radio came back into the page: it will fight the sidebar's language radio")
    src = ast.get_source_segment(ONB.read_text(encoding="utf-8"), fn) or ""
    # The FIRST version of this guard demanded the opposite — that the page write
    # `_lang_sel`, the sidebar radio's key — and that write is what crashed the page:
    # the radio lives in the sidebar, so it is already instantiated when this runs, and
    # Streamlit refuses. The reasoning ("the sidebar would re-impose the old language")
    # was right; the remedy was not. One OWNER at a time is the remedy: `app.py` does
    # not render the sidebar selector on this page. Same error class as `goto()`:
    # `widget-key-written-after-instantiation`.
    tree = ast.parse(ONB.read_text(encoding="utf-8"))
    fn_node = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "_language_buttons")
    writes = [n.lineno for n in ast.walk(fn_node)
              if isinstance(n, ast.Assign)
              for t in n.targets
              if isinstance(t, ast.Subscript)
              and isinstance(t.value, ast.Attribute) and t.value.attr == "session_state"
              and isinstance(t.slice, ast.Constant) and t.slice.value == "_lang_sel"]
    assert not writes, (
        f"the page writes the sidebar radio's key at line(s) {writes}. That widget is "
        "already instantiated — Streamlit raises, and the artist is stuck in a "
        "language they cannot leave."
    )
    assert "remember_lang" in src, "the choice is no longer persisted per artist"


def test_only_one_language_selector_is_rendered_at_a_time():
    """Two owners for one setting is the defect; the crash was its symptom."""
    fn = _fn(APP, "_main_body")
    src = ast.get_source_segment(APP.read_text(encoding="utf-8"), fn) or ""
    idx = src.index("language_selector()")
    guard = src[max(0, idx - 200):idx]
    assert "page != 'onboarding'" in guard, (
        "the sidebar language selector is rendered unconditionally again: on the "
        "assistant it would fight the page's own buttons and re-impose the previous "
        "language on every rerun."
    )


def test_the_first_run_shows_only_the_platforms_that_were_ticked():
    """« il y avait uniquement les items qu'on avait sélectionnés, il faudrait le
    remettre » — and the artist's own hypothesis, « peut-être uniquement après
    création du compte », is the right scope."""
    src = CREDS.read_text(encoding="utf-8")
    # AST, not the word. The first version asserted `"FIRST_RUN_FOCUS" in src` and
    # stayed GREEN when the flag was replaced by `first_run = False` — the name still
    # appeared in the import and the comment. Sixth time a textual predicate answered
    # a question about structure.
    tree = ast.parse(src)
    reads = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "get"
             and any(isinstance(a, ast.Name) and a.id == "FIRST_RUN_FOCUS"
                     for a in n.args)]
    assert reads, (
        "nothing READS the first-run flag from the session any more: the credentials "
        "page shows all six platforms on day one again."
    )
    assert "credentials.other_platforms" in src, (
        "the unselected platforms are HIDDEN rather than folded away: hiding what "
        "exists makes people hunt for it."
    )


def test_the_sandbox_reset_replays_the_email_verification():
    """« ça ne nous remet pas à l'étape de mail à vérifier ».

    `authenticate` refuses an unverified account, so replaying that step means
    writing the token AND printing the link — the sandbox exists precisely so the
    rehearsal depends on nothing, least of all on an e-mail arriving.
    """
    src = SANDBOX.read_text(encoding="utf-8")
    assert "verification_token" in src, (
        "the reset no longer arms a verification token: the journey would start one "
        "step after where a real artist starts")
    assert "page=verify&token=" in src, (
        "the reset does not print the verification link — the account would be "
        "unverified AND unreachable, which is worse than skipping the step")
    assert "--verified" in src, "no way to skip the step when you just want in"


def test_every_selectable_platform_maps_to_a_tab_that_exists():
    """Otherwise narrowing HIDES what the artist just ticked.

    The onboarding selection is per PLATFORM; the credentials tabs are per
    CREDENTIAL. Instagram has no tab of its own — it is entered inside Meta's — so a
    naive `key in focus` folded Instagram away for an artist who had just chosen it:
    worse than the six tabs it replaced. Caught in a browser on the first try.

    A CSV platform legitimately has no tab: it is a file import, nothing to type
    here. The exemption is READ from the registry (`where == CSV`) and not written
    down: it said `{"apple_music"}` until 2026-09-04, and Spotify for Artists — added
    the same day, also CSV — went red on a rule it satisfied. An exemption list is a
    second copy of a fact the data already carries.
    """
    import sys
    sys.path.insert(0, str(REPO))
    from src.dashboard.content.platform_value import CSV, PLATFORM_VALUES
    from src.dashboard.views.credentials._registry import PLATFORMS
    from src.dashboard.views.credentials.router import _TAB_FOR_PLATFORM

    csv_only = {pv.key for pv in PLATFORM_VALUES if pv.where == CSV}
    assert csv_only, "no CSV platform — the exemption below would be vacuous"
    unreachable = [
        pv.key for pv in PLATFORM_VALUES
        if pv.key not in csv_only
        and _TAB_FOR_PLATFORM.get(pv.key, pv.key) not in PLATFORMS
    ]
    assert not unreachable, (
        f"{unreachable} can be ticked during setup but map to no credentials tab: on "
        "a first run the page would fold away exactly what the artist chose."
    )


def test_the_sandbox_default_email_is_deliverable():
    """`<slug>@sandbox.local` bounced, and the bounce is the evidence.

    Gmail returned the welcome mail on 2026-09-04: « le domaine sandbox.local est
    introuvable ». A sandbox that replays signup must receive what an artist receives,
    otherwise it replays half of it — the half without the two e-mails.
    """
    src = SANDBOX.read_text(encoding="utf-8")
    # AST: `"_default_email" in src` stayed GREEN when the function was renamed to
    # `_default_email_disabled` and the caller went back to the literal — the name is
    # a SUBSTRING of the new one. Seventh textual predicate to answer a structural
    # question in this repo.
    called = _call_lines(_fn(SANDBOX, "main"), "_default_email")
    assert called, (
        "main() no longer calls _default_email: the default address is hardcoded "
        "again, and `.local` bounces.")
    assert "ALERT_EMAIL" in src and "SMTP_USER" in src, (
        "the default no longer derives a `+alias` from the operator's own address")
    assert 'n\'est pas une adresse livrable' in src, (
        "nothing warns when the address cannot receive: the two mails of the journey "
        "would bounce in silence and the rehearsal would look complete")


def test_adopting_a_registered_account_refuses_anything_that_is_not_fresh():
    """`--adopt` is the door that makes « replay from signup » possible at all.

    Replaying from the real form means creating an ORDINARY tenant; the uniqueness
    exemption is only needed afterwards, to type one's own identifiers into it. What
    makes the door safe is the condition, not the intention.
    """
    fn = _fn(SANDBOX, "_adopt")
    src = ast.get_source_segment(SANDBOX.read_text(encoding="utf-8"), fn) or ""
    assert "_TENANT_DATA_TABLES" in src, (
        "adoption no longer checks for collected rows: exempting a live tenant from "
        "the uniqueness guard would reopen the tenant leak that guard closed")
    assert "is_canary" in src, (
        "a canary can be adopted: it is a FLAG, not a permission — exempting it would "
        "hollow out the nightly per-tenant proof it carries")


def test_the_plan_table_does_not_contradict_the_real_gating():
    """A comparison table that lies about the current plan is worse than none.

    `export_pdf` IS in `PLAN_FEATURES['free']`, so the Free column must keep it. What
    moved to Premium on 2026-09-04 is the WEEKLY MAILED report (migration 081) — a
    different thing that happens to produce the same file.
    """
    import sys
    sys.path.insert(0, str(REPO))
    from src.database.stripe_schema import PLAN_FEATURES

    fn = _fn(ONB, "_step_welcome")
    src = ast.get_source_segment(ONB.read_text(encoding="utf-8"), fn) or ""
    free_block = src[src.index("('free',"):src.index("('premium',")]
    premium_block = src[src.index("('premium',"):]

    # DÉRIVÉ du gating, jamais figé sur un item : la première version affirmait
    # « export_pdf est dans Free » et serait devenue fausse le jour où le prix change —
    # c'est-à-dire le lendemain (2026-09-04, `export_pdf` est passé Premium). Un garde
    # qui recopie une décision se périme avec elle ; celui-ci lit la décision.
    checked = {"export_pdf": "nav.item.export_pdf", "export_csv": "feat_export_csv",
               "data_wrapped": "Data Wrapped"}
    for feature, marker in checked.items():
        free = feature in PLAN_FEATURES["free"]
        assert (marker in free_block) is free, (
            f"the plan table puts {feature!r} in the wrong column: PLAN_FEATURES says "
            f"free={free}, the table says {marker in free_block}. A comparison table "
            "that misstates the current plan is worse than none."
        )
        if not free:
            assert marker in premium_block or "feat_pdf_weekly" in premium_block, (
                f"{feature!r} left Free and appears nowhere in Premium either — it "
                "vanished from the table entirely")
    assert "feat_pdf_weekly" in premium_block, (
        "the weekly mailed report left the Premium column")


# ── 8. Les optimisations du 2026-09-04 ───────────────────────────────────────

HOME = REPO / "src" / "dashboard" / "views" / "home.py"
TRIAL = REPO / "airflow" / "dags" / "trial_expiry_reminder.py"


def test_the_home_says_WHEN_instead_of_showing_four_zeros():
    """Four zeros say « nothing », not « not yet ».

    Day one they are false and discouraging: collection runs in the morning, and a
    manual trigger brings numbers back in ~2 min. The biggest expectation gap left in
    the journey.
    """
    fn = _fn(HOME, "_section_streams")
    src = ast.get_source_segment(HOME.read_text(encoding="utf-8"), fn) or ""
    assert "home.no_data_yet" in src, (
        "the empty-state message is gone: a brand-new tenant sees four zeros again")
    assert src.index("home.no_data_yet") < src.index("grand_total:,"), (
        "the message is rendered after the zero tiles instead of replacing them")


def test_the_launch_step_launches():
    """An instruction is what you write when the button is somewhere else."""
    fn = _fn(HOME, "_section_onboarding")
    assert _call_lines(fn, "_launch_collections"), (
        "the 'launch your first collection' step no longer launches anything — it "
        "names the action and sends the artist to the sidebar to perform it.")
    # And the rule must not be copied: a second `conf={'artist_id': …}` is what
    # produced the tenant leak.
    launcher = _fn(HOME, "_launch_collections")
    lsrc = ast.get_source_segment(HOME.read_text(encoding="utf-8"), launcher) or ""
    assert "trigger_all_collections" in lsrc, (
        "home re-implements the trigger instead of calling the shared one")
    assert "artist_id" not in lsrc.split("trigger_all_collections")[0].split("conf")[-1] \
        or "conf=" not in lsrc, (
        "home builds its own `conf` — the per-tenant rule must have ONE owner")


def test_the_trial_reminder_never_fires_twice():
    """A trial reminder sent twice reads as pressure, not as information."""
    src = TRIAL.read_text(encoding="utf-8")
    assert "trial_reminder_sent_at IS NULL" in src, (
        "the query no longer excludes accounts already reminded")
    # And the stamp must be written only AFTER a confirmed send, so a closed audience
    # gate does not consume the reminder.
    fn = _fn(TRIAL, "send_trial_reminders")
    fsrc = ast.get_source_segment(src, fn) or ""
    send = fsrc.index("send_email")
    stamp = fsrc.index("trial_reminder_sent_at = NOW()")
    assert send < stamp, (
        "the reminder is marked as sent before the send is confirmed: a closed "
        "audience gate would burn it and the artist would never be warned.")
    assert "is_canary" in src and "is_sandbox" in src, (
        "the reminder targets canaries or sandboxes — accounts we create ourselves")


def test_every_smtp_connection_declares_a_timeout():
    """Error class: an unbounded socket in the request path.

    `smtplib.SMTP(host, port)` with no `timeout=` waits for the OS TCP timeout — up to
    ~2 minutes on Linux — and one of these calls runs inside the SIGNUP submit, so the
    artist watches a spinner for that long. Measured 2026-09-04: the real handshake
    costs 0.24 s in production, so the cap bounds the OUTAGE and never the nominal case.
    Four call sites had none.
    """
    for rel in ("src/utils/verification_email.py", "src/utils/email_alerts.py"):
        tree = ast.parse((REPO / rel).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr in {"SMTP", "SMTP_SSL"}):
                continue
            kw = {k.arg for k in node.keywords}
            assert "timeout" in kw, (
                f"{rel}:{node.lineno} opens an SMTP connection with no timeout — a "
                "mail server that stops answering freezes the page that called it."
            )


def test_the_post_signup_screen_gives_something_to_do(tmp_path):
    """Rendered, not asserted from the source — and it must survive a rerun.

    « Beaucoup de temps entre l'inscription et la réception du mail, et on ne sait pas
    quoi faire en attendant » (2026-09-04). The screen existed only during the submit
    run: any button on it vanished on the next rerun, which is why it carried nothing
    but a link. It is remembered in session state now, so it can carry actions.
    """
    from streamlit.testing.v1 import AppTest

    probe = tmp_path / "probe.py"
    probe.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(REPO)!r})\n"
        f"sys.path.insert(0, {str(REPO / 'src' / 'dashboard')!r})\n"
        "import streamlit as st\n"
        "st.session_state['_register_done'] = {\n"
        "    'artist_name': 'A', 'email': 'a@b.c', 'discount_msg': '',\n"
        "    'email_sent': True, 'resend': 'verify',\n"
        "    'username': 'a', 'token': 't'}\n"
        "from views.register import show\n"
        "show()\n",
        encoding="utf-8")

    at = AppTest.from_file(str(probe), default_timeout=60).run()
    assert not at.exception, f"the post-signup screen raised: {at.exception}"
    body = "\n".join([m.value for m in at.markdown]
                     + [i.value for i in at.info] + [s.value for s in at.success])
    assert "Pendant que le mail arrive" in body or "While the e-mail" in body, (
        "nothing to do while the mail travels — the screen is a dead end again")
    assert "spam" in body.lower(), (
        "the screen no longer says where to look when the mail is missing")
    assert at.get("download_button"), (
        "the getting-started guide is not downloadable before verification — it is "
        "documentation, it contains nothing personal, and it is exactly what one "
        "wants to read while waiting")
    assert any("renvoyer" in b.label.lower() or "resend" in b.label.lower()
               for b in at.button), "no way to ask for the mail again"


# ── 9. Les figures d'exemple ─────────────────────────────────────────────────

EXAMPLES = REPO / "src" / "dashboard" / "assets" / "examples"
CHARTS = REPO / "tools" / "dev" / "make_example_charts.py"
VERIF = REPO / "src" / "utils" / "verification_email.py"


def test_the_example_charts_exist_and_are_committed():
    """They are shown to an account with NO data — so they must be prebuilt.

    Rendered live they would need data that does not exist yet; exported live they
    would need `kaleido`, absent from every image (measured 2026-09-04).
    """
    for name in ("dashboard-global.png", "prediction-discover-weekly.png",
                 "meta-x-s4a.png"):
        f = EXAMPLES / name
        assert f.exists(), f"{name} is missing — run `make example-charts`"
        assert f.stat().st_size > 10_000, f"{name} looks empty ({f.stat().st_size} B)"


def test_every_example_chart_says_it_is_an_example():
    """An example that does not announce itself is a lie with a chart around it.

    The repo has already shipped a demo value read as real (the public artist counter
    that counted our own canaries). The badge is drawn INTO the image, so it survives
    a screenshot, a copy-paste and a forwarded e-mail.
    """
    fn = _fn(CHARTS, "_example_badge")
    src = ast.get_source_segment(CHARTS.read_text(encoding="utf-8"), fn) or ""
    assert "Exemple" in src and "fictives" in src, (
        "the example badge no longer says the data is fictional")
    body = CHARTS.read_text(encoding="utf-8")
    tree = ast.parse(body)
    for maker in ("dashboard_global", "discover_weekly_prediction", "meta_x_s4a"):
        fn = next(n for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef) and n.name == maker)
        assert _call_lines(fn, "_example_badge"), (
            f"{maker}() ships a figure with no example badge")


def test_the_charts_never_use_a_second_y_axis():
    """The #1 chart mistake, and this exact pair of measures invites it.

    Spend and streams have different scales: one axis each, in two stacked panels
    sharing the x. A `twinx()` here would let anyone read a correlation that is an
    artefact of where the two scales were pinned.
    """
    body = CHARTS.read_text(encoding="utf-8")
    tree = ast.parse(body)
    twins = [n.lineno for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr in {"twinx", "twiny"}]
    assert not twins, f"a dual-axis chart appeared at line(s) {twins}"


def test_the_welcome_mail_embeds_its_image_and_reads_without_it():
    """By CID, never by URL — and the mail must be complete when images are blocked."""
    body = VERIF.read_text(encoding="utf-8")
    assert "cid:" in body, "the welcome image is no longer embedded by Content-ID"
    # Les DOCSTRINGS exclues. La première version cherchait `src="https://` dans le
    # texte du module et se déclenchait sur le commentaire qui EXPLIQUE pourquoi c'est
    # interdit. Huitième prédicat textuel à répondre à une question de structure : on
    # ne regarde que les chaînes qui deviennent du HTML.
    tree = ast.parse(body)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)):
            d = ast.get_docstring(node, clean=False)
            if d:
                docstrings.add(d)
    remote = [n.lineno for n in ast.walk(tree)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)
              and n.value not in docstrings
              and ("src=\"http" in n.value or "src='http" in n.value)]
    assert not remote, (
        f"an image is fetched from a URL at line(s) {remote}: the recipient's client "
        "would tell a third party when the mail was opened, and most clients block "
        "it anyway")
    # Un `alt=` NON VIDE sur chaque image, pas une clé i18n nommée. La version
    # d'avant cherchait la chaîne `email.welcome.image_alt` : elle est passée au rouge
    # le 2026-09-04 en renommant la clé, sur du code où chaque image porte bel et bien
    # son texte de remplacement. Un garde qui vise le NOM d'une clé répond « cette clé
    # existe-t-elle », jamais « ces images ont-elles un alt ».
    import re as _re
    from src.utils.verification_email import _welcome_image_row, _welcome_images

    row = _welcome_image_row("fr")
    imgs = _re.findall(r"<img\b[^>]*>", row)
    assert imgs, "the welcome mail no longer renders any example figure"
    for tag in imgs:
        alt = _re.search(r'alt="([^"]*)"', tag)
        assert alt and alt.group(1).strip(), (
            f"an embedded image has no alt text — blocked images are the normal "
            f"case: {tag[:90]}")

    # Le POIDS, pas le nombre. « Une image, pas trois » était la formulation de la
    # règle en septembre ; la règle elle-même a toujours été « un mot de bienvenue
    # lourd se délivre moins bien ». Les trois promesses sont désormais montrées côte
    # à côte (demandé le 2026-09-04) en VIGNETTES : trois d'entre elles pèsent moins
    # que la moitié des trois figures pleines, et un neuvième du PDF que ce même
    # e-mail transporte déjà en pièce jointe. Compter les images aurait interdit le
    # changement ; peser les octets dit ce qu'on voulait vraiment dire.
    from pathlib import Path as _Path
    total = sum(_Path(path).stat().st_size for _cid, path in _welcome_images())
    assert total <= 120 * 1024, (
        f"the welcome mail carries {total // 1024} KB of inline images (ceiling: "
        "120 KB). Rebuild the thumbnails with `make example-charts` — a heavier "
        "welcome mail is a less deliverable one.")


def test_the_sandbox_reset_actually_sends_the_verification_mail():
    """« Le parcours commence ici, comme pour un vrai artiste » — alors il l'envoie.

    `--reset` armait le jeton, imprimait le lien, et n'envoyait rien. Il annonçait donc
    un parcours identique à celui d'un artiste tout en sautant la seule chose qu'un
    artiste reçoit. Signalé le 2026-09-04 : « je viens de refaire le process mais
    toujours pas de mail ». Un outil qui rejoue un parcours rejoue ses effets, ou dit
    lequel il ne rejoue pas.
    """
    fn = _fn(SANDBOX, "_send_verification")
    src = ast.get_source_segment(SANDBOX.read_text(encoding="utf-8"), fn) or ""
    assert "send_verification_email" in src, (
        "the sandbox composes its own mail instead of calling the signup path — the "
        "day the e-mail changes, the rehearsal would replay the old one")
    main = _fn(SANDBOX, "main")
    assert _call_lines(main, "_send_verification"), (
        "--reset no longer sends the verification mail: it would announce a journey "
        "identical to an artist's while skipping the only thing an artist receives")
    body = SANDBOX.read_text(encoding="utf-8")
    assert "n'est PAS parti" in body, (
        "a failed send is not reported — the operator would wait for a mail that "
        "never left, which is exactly what happened")
