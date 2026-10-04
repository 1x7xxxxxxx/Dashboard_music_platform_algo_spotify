"""« MRR total » veut dire la même chose sur toutes les pages qui l'affichent.

Type: Test
Uses: ast
Depends on: src/utils/mrr, src/dashboard/views/{admin,billing,revenue_forecast}.py
Persists in: nothing

Pourquoi ce garde existe
------------------------
Mesuré le 2026-09-18 : le MRR était calculé à **trois endroits**, avec **deux réponses**
sous le même libellé.

    admin.py:544-546        WHERE a.status = 'active'                  SQL
    billing.py:322-331      WHERE asub.status = 'active'               SQL
    revenue_forecast.py     status ∈ {'active','trialing'} ET price>0  pandas

Dès qu'un abonnement passait en `trialing` — et l'admin parle explicitement d'« essai de
bienvenue » — deux pages affichaient deux nombres différents sous le même mot. « Artistes
payants » aussi.

⚠️ **Et aucune des trois n'excluait les locataires techniques**, alors que le compteur
« Artistes actifs », QUATRE LIGNES plus haut dans le même écran, les excluait. Deux
nombres de la même page se contredisaient.
"""
from __future__ import annotations

import ast
import contextlib
import re
import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.mrr import (  # noqa: E402
    MRR_COLUMNS, MRR_LABEL, MRR_STATUSES, mrr_by_plan_sql, mrr_params,
)

_SURFACES = (
    "src/dashboard/views/admin.py",
    "src/dashboard/views/billing.py",
    "src/dashboard/views/revenue_forecast.py",
)


def test_the_single_definition_counts_trials() -> None:
    """La décision du 2026-09-20, écrite là où elle s'applique."""
    assert "trialing" in MRR_STATUSES and "active" in MRR_STATUSES


def test_the_single_definition_excludes_technical_tenants() -> None:
    """Le prédicat vient de `tenant_kind`, et il est bien dans la requête."""
    sql = mrr_by_plan_sql()
    assert "is_canary" in sql and "is_sandbox" in sql, (
        "la requête du MRR n'exclut pas les locataires techniques — elle compterait les "
        "canaris et le bac à sable comme du revenu, pendant que le compteur d'artistes "
        "de la même page les exclut.")


def _litteraux_qui_filtrent(arbre: ast.AST) -> list[str]:
    """Les `'trialing'` qui SERVENT À DÉCIDER, pas ceux qui servent à afficher.

    ⚠️ La première version de ce prédicat cherchait le littéral n'importe où. Elle a
    accusé `billing.py:156`, qui écrit `'trialing': '🟡'` — une table d'ICÔNES par
    statut, qui doit évidemment nommer tous les statuts. C'est la même erreur que ce
    dépôt a mesurée onze fois cette semaine : chercher une FORME D'ÉCRITURE là où la
    classe parle d'une PROPRIÉTÉ. Ici la propriété est « ce littéral décide-t-il de ce
    qui compte », et elle se lit dans la POSITION du nœud :

      * une comparaison (`status == 'trialing'`)                    → il décide
      * un argument d'appartenance (`.isin([...])`, `in (...)`)     → il décide
      * une CLÉ de dictionnaire (`{'trialing': '🟡'}`)              → il affiche
      * une valeur de dictionnaire                                  → il affiche
    """
    fautifs: list[str] = []
    cles_de_dict: set[int] = set()
    for n in ast.walk(arbre):
        if isinstance(n, ast.Dict):
            cles_de_dict.update(id(k) for k in n.keys if k is not None)
            cles_de_dict.update(id(v) for v in n.values)

    def _chaines(noeud) -> list[ast.Constant]:
        return [x for x in ast.walk(noeud)
                if isinstance(x, ast.Constant) and x.value in ("trialing", "active")]

    for n in ast.walk(arbre):
        if isinstance(n, ast.Compare):
            for c in _chaines(n):
                if id(c) not in cles_de_dict:
                    fautifs.append(f"comparaison sur {c.value!r} (l.{c.lineno})")
        elif isinstance(n, ast.Call):
            nom = getattr(n.func, "attr", "") or getattr(n.func, "id", "")
            if nom in ("isin", "in_", "any_"):
                for c in _chaines(n):
                    fautifs.append(f"appartenance à {c.value!r} (l.{c.lineno})")
    return fautifs


@pytest.mark.parametrize("rel", _SURFACES)
def test_no_surface_decides_the_status_set_by_hand(rel: str) -> None:
    """LE GARDE. Un statut qui DÉCIDE du MRR, hors du module unique.

    Lu à l'AST : un commentaire qui explique le défaut contient les mots, et un prédicat
    textuel rougirait sur sa propre documentation.
    """
    texte = (ROOT / rel).read_text(encoding="utf-8")
    fautifs = _litteraux_qui_filtrent(ast.parse(texte))
    for m in re.finditer(r"status\s*=\s*'active'", texte):
        if not texte[:m.start()].rsplit("\n", 1)[-1].lstrip().startswith("#"):
            fautifs.append(f"filtre SQL `{m.group(0)}`")
    assert not fautifs, (
        f"{rel} décide lui-même de ce qui compte dans le MRR : {fautifs}.\n"
        "C'est ainsi que deux pages ont affiché deux nombres sous le même mot. "
        "Importer `MRR_STATUSES` / `mrr_by_plan_sql()` depuis `src/utils/mrr.py`.")


def test_the_predicate_tells_a_filter_from_an_icon_table() -> None:
    """AUTO-PREUVE des deux sens, sur du code SYNTHÉTIQUE.

    Sans elle, un prédicat qui n'accuse plus RIEN passerait le test ci-dessus.
    """
    filtre = ast.parse("x = df[df['status'].isin(['active', 'trialing'])]")
    icones = ast.parse("ICONES = {'trialing': '🟡', 'active': '🟢'}")
    assert _litteraux_qui_filtrent(filtre), (
        "le prédicat ne voit pas un `.isin(['active','trialing'])` — c'est exactement la "
        "forme qu'il existe pour attraper.")
    assert not _litteraux_qui_filtrent(icones), (
        "le prédicat accuse une table d'icônes par statut, qui doit nommer tous les "
        "statuts. C'est le faux positif qui l'a fait resserrer.")


@pytest.mark.parametrize("rel", _SURFACES)
def test_every_surface_reads_the_single_definition(rel: str) -> None:
    """ANTI-VACUITÉ. Ne pas épeler ne suffit pas — encore faut-il LIRE la définition."""
    texte = (ROOT / rel).read_text(encoding="utf-8")
    assert re.search(r"from src\.utils\.mrr import", texte), (
        f"{rel} n'importe rien de `src/utils/mrr.py`. Il peut ne plus épeler les statuts "
        "tout en calculant le MRR autrement — le test ci-dessus serait vert pour rien.")


def test_the_query_runs_against_the_real_schema() -> None:
    """Le SQL composé doit être exécutable — une requête qui lève n'affiche rien.

    ⚠️ Ce test EXÉCUTE la requête. La version précédente de ce garde se serait contentée
    de lire le texte, et un alias oublié (`is_canary` au lieu de `sa.is_canary` dans une
    requête jointe) ne se voit qu'à l'exécution.
    """
    from src.database.postgres_handler import PostgresHandler
    try:
        db = PostgresHandler.from_env_or_config()
    except Exception:                          # noqa: BLE001
        pytest.skip("base injoignable")
    try:
        df = db.fetch_df(mrr_by_plan_sql(), mrr_params())
    finally:
        db.close()
    # The SHAPE, not only "it runs" (R369): the previous version discarded the result, so
    # a fourth column inserted at index 1 left this test green for 14 days.
    assert tuple(df.columns) == MRR_COLUMNS, (
        f"the MRR query returns {tuple(df.columns)} but `MRR_COLUMNS` declares "
        f"{MRR_COLUMNS} — update the contract with the query, never one without the other.")


# ── R369 — the consumers read the result BY NAME, on a row of the REAL shape ─────────────
#
# Measured 2026-10-04: R140 (5ddd7f6c) gave `mrr_by_plan_sql()` a 4th column,
# `price_monthly`, at index 1. Both callers were switched to the helper by their CALL and
# not by their SHAPE: `billing.py` and `admin.py` kept `sum(r[2])` for the MRR (now the
# artist count), `sum(int(r[1]))` for the paying artists (now the price), and a 3-name
# `pd.DataFrame` that raises "3 columns passed, passed data had 4 columns". Nothing saw it
# for 14 days: the schema test above ran the query and threw the result away, and the
# render smoke test skips in CI (empty DB) and only crashes once a PAYING human exists.
#
# So this half needs no database. The row is built FROM THE SQL TEXT: each SELECT item's
# expression is mapped to what psycopg2 returns for it (`numeric` -> Decimal, `COUNT` ->
# int). Retyping the columns here would be circular: the stub would agree with the
# constant it is meant to check, and swapping two aliases in `mrr.py` would never reach
# the consumer.

#: What psycopg2 returns for each SELECT expression, for ONE premium plan at 10.00 EUR
#: with three human subscribers. An expression not listed (a column added later) is None.
_PSYCOPG2_VALUE = {
    "sp.name": "premium",
    "sp.price_monthly": Decimal("10.00"),
    "COUNT(*)": 3,
    "SUM(sp.price_monthly)": Decimal("30.00"),
}


def _select_items(sql: str) -> list[tuple[str, str]]:
    """`(expression, alias)` of the outer SELECT list, read from the SQL text."""
    m = re.search(r"\bSELECT\b(.*?)\bFROM\b", sql, re.S | re.I)
    assert m, "no SELECT ... FROM in the MRR query"
    items, depth, cur = [], 0, ""
    for ch in m.group(1):
        depth += (ch == "(") - (ch == ")")
        if ch == "," and depth == 0:
            items.append(cur)
            cur = ""
        else:
            cur += ch
    items.append(cur)
    out = []
    for item in items:
        mm = re.fullmatch(r"\s*(.*?)\s+AS\s+(\w+)\s*", item, re.S | re.I)
        assert mm, f"SELECT item without an alias: {item.strip()!r} — consumers read by name"
        out.append((re.sub(r"\s+", " ", mm.group(1)), mm.group(2)))
    return out


def test_the_declared_columns_are_the_select_list() -> None:
    """`MRR_COLUMNS` is pinned to the SQL text, and each name to its MEANING — in CI.

    The DB pin above skips without a database; this one does not. Swapping `AS artists`
    and `AS mrr` keeps the names and their order, so only the expression check sees it.
    """
    items = _select_items(mrr_by_plan_sql())
    assert tuple(a for _, a in items) == MRR_COLUMNS, (
        f"SELECT aliases {[a for _, a in items]} != MRR_COLUMNS {MRR_COLUMNS}")
    meaning = {a: e for e, a in items}
    assert meaning["artists"] == "COUNT(*)", f"`artists` is {meaning['artists']!r}"
    assert meaning["mrr"] == "SUM(sp.price_monthly)", f"`mrr` is {meaning['mrr']!r}"


class _StubDB:
    """Answers the MRR query with one row of its REAL shape, in both read methods."""

    def __init__(self, other_rows: list[tuple]) -> None:
        self._sql = mrr_by_plan_sql()
        items = _select_items(self._sql)
        self._cols = [a for _, a in items]
        self._rows = [tuple(_PSYCOPG2_VALUE.get(e) for e, _ in items)]
        self._other = other_rows

    def fetch_query(self, query: str, params: tuple | None = None) -> list[tuple]:
        return list(self._rows) if query == self._sql else list(self._other)

    def fetch_df(self, query: str, params: tuple | None = None):
        import pandas as pd
        assert query == self._sql, f"unexpected fetch_df: {query[:80]!r}"
        return pd.DataFrame(self._rows, columns=self._cols)  # as PostgresHandler.fetch_df


class _St:
    """A Streamlit stand-in that records what a view SHOWS."""

    def __init__(self) -> None:
        self.metrics: dict[str, object] = {}
        self.frames: list = []

    def metric(self, label, value, *a, **k) -> None:
        self.metrics[label] = value

    def dataframe(self, df, *a, **k) -> None:
        self.frames.append(df)

    def columns(self, spec, *a, **k) -> list:
        return [self] * (spec if isinstance(spec, int) else len(spec))

    def expander(self, *a, **k):
        return contextlib.nullcontext()

    def __getattr__(self, name: str):
        return lambda *a, **k: None


def _default_label(key: str, default: str | None = None, **_) -> str:
    return default if default is not None else key


def test_billing_reads_the_mrr_by_meaning(monkeypatch) -> None:
    """LE GARDE (consumer 1/2). One premium row, 3 artists at 10 EUR — what billing shows."""
    from src.dashboard.views import billing
    st = _St()
    monkeypatch.setattr(billing, "st", st)
    monkeypatch.setattr(billing, "t", _default_label)
    billing._show_admin_view(_StubDB([("A", "premium", "premium", "active", None, None)]))
    assert st.metrics.get(MRR_LABEL) == "30.00 €", st.metrics
    assert st.metrics.get("Artistes payants") == 3, st.metrics
    assert st.metrics.get("ARPU") == "10.00 €", st.metrics
    assert list(st.frames[-1].iloc[0]) == ["premium", 3, 30.0], st.frames[-1]


def test_admin_reads_the_mrr_by_meaning(monkeypatch) -> None:
    """LE GARDE (consumer 2/2) — and the margin section receives the MRR, not a count."""
    from src.dashboard.views import admin, admin_activation
    st = _St()
    costs: list = []
    monkeypatch.setattr(admin, "st", st)
    monkeypatch.setattr(admin, "t", _default_label)
    monkeypatch.setattr(admin_activation, "_render_activation", lambda db: None)
    monkeypatch.setattr(admin, "_render_costs", lambda db, mrr: costs.append(mrr))
    admin._render_supervision(_StubDB([(0, 0, 0, 0)]))
    assert st.metrics.get(MRR_LABEL) == "30.00 €", st.metrics
    assert st.metrics.get("Abonnés payants") == 3, st.metrics
    assert st.metrics.get("ARPU") == "10.00 €", st.metrics
    assert list(st.frames[-1].iloc[0]) == ["premium", 3, 30.0], st.frames[-1]
    assert costs == [30.0] and isinstance(costs[0], float), (
        f"`_render_costs` received {costs!r} — the margin is computed against it")
