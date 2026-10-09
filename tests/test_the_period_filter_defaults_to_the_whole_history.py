"""R259, R478 — one period filter, one default for the whole app: the WHOLE history.

Type: Test
Uses: src/dashboard/utils/period_filter.py, src/dashboard/views/*.py (AST + text)

Owner, 2026-09-27 (notes L89-L91, L98, L511) : « mets la dernière release en automatique =>
fais ça pour toute l'app », « il faut qu'on ait les mêmes filtres à chaque fois ». Before
R259 the rule lived at SEVEN call sites (`default_override="last_release"`), the layer's own
default was « current », and two views rendered another selector (`ui.smart_date_range`,
other labels, full span by default). The rule now lives in ONE place ; this keeps it there.

R478, owner 2026-10-09 (W7, W11) : « d'office toute la durée ». The default flipped from
« depuis la dernière sortie » to the whole history — the latest-release half of the rule
moved to the TITLES (`release_picker`, two latest by default). Measured before the flip,
alternating, on the biggest tenant : no render-time difference beyond noise.
"""
import ast
import inspect
import pathlib

from src.dashboard.utils import period_filter as pf

ROOT = pathlib.Path(__file__).resolve().parents[1]
VIEWS = ROOT / "src" / "dashboard" / "views"

# Views that draw a daily series WITHOUT the shared filter — each with its reason.
EXEMPT = {
    "trigger_algo/_common/_budget_roi.py": "CPR par campagne mappée au titre, sur TOUTE la vie : une barre par campagne, pas une série temporelle (R477)",
    "db_health.py": "admin : la fenêtre est « hier » par construction (anomalie d'ingestion)",
    "admin.py": "supervision : on y choisit un mois de facturation, pas une fenêtre",
    "airflow_kpi.py": "ops : fenêtre de supervision des DAG, public exploitant",
    "revenue_forecast.py": "trésorerie : un cumul part du premier euro, une fenêtre le fausserait",
    "trigger_algo/_tab_budget_roi.py": "point mort : cumul depuis le premier euro, même raison",
    # R368 — seen only once `_uses_the_layer` stopped counting an ACCOUNT-filter import.
    "meta_cpr_optimizer.py": "coût par résultat sur TOUTE la vie de chaque campagne : une fenêtre tronquerait le CPR",
    "meta_x_spotify.py": "la fenêtre EST celle de la campagne choisie (`campaign_window` de la barre, R399), pas une période libre",
    # R399 — the page's one filter bar draws the period; the section reads `bar.window`.
    "meta_creatives.py": "la fenêtre vient de la barre de filtres unique de la page Meta (R399)",
    # R377 (V24) — the default « depuis la dernière sortie » hid the previous campaign.
    # R404 (V68) — the settings bars aggregate each setting over the account's whole life.
    "trigger_algo/_tab_reglages.py": "réglages comparés sur TOUTE la vie du compte : une fenêtre ferait tomber chaque réglage sous le seuil d'annonces fiable",
    "hypeddit.py": "on compare des CAMPAGNES choisies (deux dernières par défaut), pas une période libre",
    # R385 (V44) — the dated per-track chart became an equal-AGE comparison.
    # R381 (V66) — SHAP bars per playlist; the CPR range reads each campaign's whole life.
    "trigger_algo/_playlist_detail.py": "barres SHAP par playlist, pas une série temporelle ; le CPR lit toute la vie des campagnes",
    "soundcloud.py": "titres comparés à âge égal (jours depuis l'upload) ; le catalogue montre ses 19 relevés, toute la collecte",
}


def test_the_layer_defaults_to_the_whole_history():
    for fn in (pf.smart_period_filter, pf.span_period_filter, pf.entity_period_filter):
        assert inspect.signature(fn).parameters["default_override"].default == "all", (
            f"{fn.__name__} ne s'ouvre plus sur toute la durée")
    assert pf._default_preset(400, "all")[0] == "all"
    assert pf._default_preset(400, "last_release")[0] == "last_release", (
        "« depuis la dernière sortie » doit rester un choix à un clic")


def _redundant_defaults(source: str) -> int:
    """Calls that repeat the layer's default — the rule copied back into a view. Pure."""
    n = 0
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if (kw.arg == "default_override" and isinstance(kw.value, ast.Constant)
                        and kw.value.value == "all"):
                    n += 1
    return n


def test_no_view_repeats_the_default():
    hits = {str(p.relative_to(VIEWS)): _redundant_defaults(p.read_text(encoding="utf-8"))
            for p in VIEWS.rglob("*.py")}
    hits = {k: v for k, v in hits.items() if v}
    assert not hits, f"la règle recopiée dans une vue au lieu de vivre dans la couche : {hits}"


def _draws_daily_series(source: str) -> bool:
    return "charts.plotly_chart" in source and ("_daily" in source or "_timeline" in source)


_PERIOD_CALLS = frozenset({"smart_period_filter", "span_period_filter", "entity_period_filter",
                           # R399 — the Meta page's one bar; held below to call the layer.
                           "filter_bar"})
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


def test_the_meta_filter_bar_itself_calls_the_layer():
    """`filter_bar` counts as a period filter only while it really calls one."""
    bar = ROOT / "src" / "dashboard" / "utils" / "meta_filter_bar.py"
    src = bar.read_text(encoding="utf-8").replace("def filter_bar(", "def _bar(")
    assert _uses_the_layer(src), "meta_filter_bar no longer calls the shared period filter"


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
    assert _redundant_defaults('f(db, default_override="all")') == 1
    assert _redundant_defaults('f(db, default_override="last_release")') == 0
    drawing = 'db.fetch_df("SELECT * FROM v_meta_daily"); charts.plotly_chart(fig)'
    assert _draws_daily_series(drawing) and not _uses_the_layer(drawing)
    assert _uses_the_layer("from src.dashboard.utils import filters\nw = filters.period(db)\n" + drawing)
    # R368 — importing the ACCOUNT filter is not filtering the period.
    assert not _uses_the_layer(
        "from src.dashboard.utils.filters import account_clause\n" + drawing)
    assert not _uses_the_layer("from src.dashboard.utils import filters\n" + drawing)
