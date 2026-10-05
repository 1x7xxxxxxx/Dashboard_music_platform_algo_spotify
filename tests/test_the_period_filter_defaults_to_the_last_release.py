"""R259 — one period filter, one default: « depuis la dernière sortie », for the whole app.

Type: Test
Uses: src/dashboard/utils/period_filter.py, src/dashboard/views/*.py (AST + text)

Owner, 2026-09-27 (notes L89-L91, L98, L511) : « mets la dernière release en automatique =>
fais ça pour toute l'app », « il faut qu'on ait les mêmes filtres à chaque fois ». Before
R259 the rule lived at SEVEN call sites (`default_override="last_release"`), the layer's own
default was « current », and two views rendered another selector (`ui.smart_date_range`,
other labels, full span by default). The rule now lives in ONE place ; this keeps it there.
"""
import ast
import inspect
import pathlib

from src.dashboard.utils import period_filter as pf

ROOT = pathlib.Path(__file__).resolve().parents[1]
VIEWS = ROOT / "src" / "dashboard" / "views"

# Views that draw a daily series WITHOUT the shared filter — each with its reason.
EXEMPT = {
    "db_health.py": "admin : la fenêtre est « hier » par construction (anomalie d'ingestion)",
    "admin.py": "supervision : on y choisit un mois de facturation, pas une fenêtre",
    "airflow_kpi.py": "ops : fenêtre de supervision des DAG, public exploitant",
    "revenue_forecast.py": "trésorerie : un cumul part du premier euro, une fenêtre le fausserait",
    "trigger_algo/_tab_budget_roi.py": "point mort : cumul depuis le premier euro, même raison",
    # R368 — seen only once `_uses_the_layer` stopped counting an ACCOUNT-filter import.
    "meta_cpr_optimizer.py": "coût par résultat sur TOUTE la vie de chaque campagne : une fenêtre tronquerait le CPR",
    "meta_x_spotify.py": "la fenêtre EST celle de la campagne choisie (`_campaign_window`), pas une période libre",
    # R377 (V24) — the default « depuis la dernière sortie » hid the previous campaign.
    "hypeddit.py": "on compare des CAMPAGNES choisies (deux dernières par défaut), pas une période libre",
    # R385 (V44) — the dated per-track chart became an equal-AGE comparison.
    "soundcloud.py": "titres comparés à âge égal (jours depuis l'upload) ; le catalogue montre ses 19 relevés, toute la collecte",
}


def test_the_layer_defaults_to_the_last_release():
    for fn in (pf.smart_period_filter, pf.span_period_filter, pf.entity_period_filter):
        assert inspect.signature(fn).parameters["default_override"].default == "last_release", (
            f"{fn.__name__} ne s'ouvre plus sur « depuis la dernière sortie »")
    assert pf._default_preset(400, "last_release")[0] == "last_release"


def _redundant_defaults(source: str) -> int:
    """Calls that repeat the layer's default — the rule copied back into a view. Pure."""
    n = 0
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if (kw.arg == "default_override" and isinstance(kw.value, ast.Constant)
                        and kw.value.value == "last_release"):
                    n += 1
    return n


def test_no_view_repeats_the_default():
    hits = {str(p.relative_to(VIEWS)): _redundant_defaults(p.read_text(encoding="utf-8"))
            for p in VIEWS.rglob("*.py")}
    hits = {k: v for k, v in hits.items() if v}
    assert not hits, f"la règle recopiée dans une vue au lieu de vivre dans la couche : {hits}"


def _draws_daily_series(source: str) -> bool:
    return "charts.plotly_chart" in source and ("_daily" in source or "_timeline" in source)


_PERIOD_CALLS = frozenset({"smart_period_filter", "span_period_filter", "entity_period_filter"})
_FILTERS_ALIASES = frozenset({"period", "span", "entity"})


def _uses_the_layer(source: str) -> bool:
    """The view CALLS a period filter. R368 (2026-10-05): this read `"utils.filters" in
    source`, so `from …filters import account_clause` — the Meta ACCOUNT, no period —
    passed a view that never filtered its window. Pure, by the AST."""
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Name) and f.id in _PERIOD_CALLS:
            return True
        if isinstance(f, ast.Attribute) and (f.attr in _PERIOD_CALLS or (
                f.attr in _FILTERS_ALIASES and isinstance(f.value, ast.Name)
                and f.value.id == "filters")):
            return True
    return False


def test_every_view_drawing_a_daily_series_goes_through_the_shared_filter():
    missing = []
    for p in sorted(VIEWS.rglob("*.py")):
        rel = str(p.relative_to(VIEWS))
        src = p.read_text(encoding="utf-8")
        if _draws_daily_series(src) and not _uses_the_layer(src) and rel not in EXEMPT:
            missing.append(rel)
    assert not missing, f"vues qui tracent une série quotidienne sans le filtre commun : {missing}"
    for rel in EXEMPT:
        assert (VIEWS / rel).is_file(), f"exemption vers une vue disparue : {rel}"


def test_the_detectors_see_the_defects_they_are_written_for():
    assert _redundant_defaults('f(db, default_override="last_release")') == 1
    assert _redundant_defaults('f(db, default_override="all")') == 0
    drawing = 'db.fetch_df("SELECT * FROM v_meta_daily"); charts.plotly_chart(fig)'
    assert _draws_daily_series(drawing) and not _uses_the_layer(drawing)
    assert _uses_the_layer("from src.dashboard.utils import filters\nw = filters.period(db)\n" + drawing)
    # R368 — importing the ACCOUNT filter is not filtering the period.
    assert not _uses_the_layer(
        "from src.dashboard.utils.filters import account_clause\n" + drawing)
    assert not _uses_the_layer("from src.dashboard.utils import filters\n" + drawing)
