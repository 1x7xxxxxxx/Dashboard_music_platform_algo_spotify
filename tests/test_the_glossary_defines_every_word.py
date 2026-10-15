"""R592 — the glossary page: reachable after « Mon compte », every word defined in FR and EN.

Type: Hook
Depends on: src/dashboard/utils/glossary.py, src/dashboard/views/glossary.py,
            src/dashboard/utils/nav_sections.py, src/dashboard/routes.py,
            tools/dev/glossary_inventory.py

Owner, 2026-10-15 : « une vue Glossaire dans Compte, juste après Mon compte : le schéma du
fonctionnement de l'app et toutes les définitions techniques ». Four properties:
  - the page is in the « Compte » section, right after « Mon compte », and routed;
  - every word has an EN term and an EN definition (a FR-only word is half a glossary);
  - every word an in-place glossary defines is also in the page (one place holds them all);
  - every word is one the app actually uses — a definition nobody meets is noise.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.dashboard.utils.glossary import TERMS  # noqa: E402
from src.dashboard.utils.i18n_catalog.glossary import EN  # noqa: E402


def test_the_page_follows_my_account_and_is_routed():
    from src.dashboard.routes import ROUTES
    from src.dashboard.utils.nav_sections import NAV_SECTIONS
    account = next(items for key, _label, items in NAV_SECTIONS if key == "account")
    keys = [k for _label, k in account]
    assert keys[:2] == ["account", "glossary"], keys
    assert ROUTES["glossary"] == "views.glossary"


def test_every_word_is_translated():
    missing = [k for k, *_ in TERMS
               if f"glossary.term.{k}" not in EN or f"glossary.def.{k}" not in EN]
    assert not missing, missing
    assert len({k for k, *_ in TERMS}) == len(TERMS), "a word is defined twice"


def test_every_in_place_definition_is_in_the_glossary():
    from tools.dev.glossary_inventory import in_place_definitions
    local = in_place_definitions()
    assert len(local) >= 10, "the in-place glossaries vanished — the check would pass empty"
    gloss = " ".join(f"{term} {d}" for _k, _g, term, d, _p in TERMS).lower()
    words = {"clic_sortant": "clic sortant", "frequence": "fréquence",
             "etape": "étape d'avant", "cout_unitaire": "coût à l'unité"}
    absent = [k for _f, _l, k in local
              if words.get(k, k).lower().replace("_", " ") not in gloss]
    assert not absent, f"defined in place but not in the glossary: {absent}"


def test_every_word_is_one_the_app_uses():
    from tools.dev.glossary_inventory import occurrences
    occ = occurrences()
    unused = [k for k, v in occ.items() if not v]
    assert not unused, f"defined but met nowhere in src/dashboard: {unused}"


def test_the_diagram_draws_the_whole_flow():
    from src.dashboard.views.glossary import flow_dot
    dot = flow_dot()
    edges = set(re.findall(r"(\w+) -> (\w+);", dot))
    # sources reach the pages through the database and the shared calculations
    assert {("collect", "db"), ("csv", "db"), ("db", "gold"), ("gold", "pages")} <= edges
    assert dot.startswith("digraph") and dot.rstrip().endswith("}")
