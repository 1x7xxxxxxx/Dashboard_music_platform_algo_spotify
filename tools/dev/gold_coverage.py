#!/usr/bin/env python3
"""Write the map of what every figure, tile and PDF chart actually reads.

Type: Utility
Uses: ast, hashlib, re — nothing else. **No database, no import of `src/`.**
Triggers: `make gold-coverage`, `make gold-coverage-check`, CI step 8
Depends on: migrations/*.sql, init_db.sql, src/**/*.py
Persists in: .claude/dev-docs/gold-coverage.md

Why this exists
---------------
On 2026-09-12 a ratchet certified « eight platforms at zero aggregates outside the
gold layer ». It was true of the three directories it scanned and false of the
repository: twelve aggregates lived in `kpi_helpers.py` and `pdf_charts.py`, which
its `_SURFACES` did not name. The defect was not in the predicate — it was in
nobody having a MAP of what reads what.

This writes that map. Generated, never edited: a 90-line inventory kept by hand is
stale at the third commit, and a stale inventory reads exactly like a complete one.

The one rule that makes it worth reading
----------------------------------------
**An attribution is published only when there is a proven def-use path from a SQL
read to the figure.** Everything else says so. Three separate mechanisms enforce it:

  * a f-string placeholder in `FROM` position becomes an opaque sentinel, so
    `FROM {tbl} WHERE x` can never yield the table `where`. A prototype of this
    script invented `tbl:where` and `tbl:daily_diff` before the sentinel existed;
  * every identifier emitted as a source must exist in `migrations/` ∪
    `init_db.sql`. That kills CTE names, aliases and subquery labels at the root;
  * what the enclosing function happens to read, with no path to the figure, is
    published in a separate column whose header denies the claim. It is never
    merged into the source column.

A document that guesses is worse than a document that admits a gap, because the
gap is the thing you would have acted on.

What it deliberately does not do
--------------------------------
It does not execute anything, it does not read the database, and it does not
resolve values. It reads structure. Every limit is counted and named in the
document's own « Ce que ce document ne sait pas » section, placed BEFORE the
tables — a disclosure that follows the data is a disclosure nobody reads.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / ".claude" / "dev-docs" / "gold-coverage.md"

# ── ce qu'on lit ───────────────────────────────────────────────────────────
_SQL_DIRS = ("migrations",)
_SQL_EXTRA = ("init_db.sql",)
_PY_ROOTS = ("src",)

# Les PORTES : les modules dont le travail EST de lire les faits et d'en faire une
# règle. Une tranche qui les atteint s'arrête là — elles ont leur propre tableau.
_DOOR_MODULES = {
    "src.dashboard.utils.platform_timeseries",
    "src.dashboard.utils.kpi_helpers",
}

_EXECUTORS = {"fetch_df", "fetch_query", "fetch_one", "fetch_all", "execute_query"}

_FIGURE_CALLS = {"plotly_chart", "pyplot", "bar_chart", "line_chart",
                 "area_chart", "altair_chart", "map", "graphviz_chart"}

# Les arguments qui ne portent PAS de donnée. Suivre `title=t("…")` mène dans
# `i18n.t`, dont les 2 397 appelants font basculer quatorze figures en
# « indéterminée » pour une raison purement décorative.
_PRESENTATION_KW = {
    "title", "labels", "name", "color_discrete_sequence", "color_discrete_map",
    "hovertemplate", "key", "help", "subplot_titles", "text", "use_container_width",
    "height", "width", "caption", "label", "delta_color", "template", "theme",
    "border", "hide_index", "column_config", "unsafe_allow_html", "icon",
}
_STOP_CALLS = {
    "t", "_t", "translate", "escape", "format", "str", "int", "float", "len",
    "print", "round", "f", "fmt_eur", "fmt_int", "_fmt", "gettext", "range",
    "sorted", "enumerate", "zip", "isinstance", "getattr", "super",
}

_SENTINEL = "\x00DYN\x00"

_AGG_RE = re.compile(r"\b(SUM|AVG|MIN|MAX|COUNT)\s*\(", re.I)

# ── la portée de l'AUTRE cliquet, recopiée ici pour pouvoir dire ce qu'il NE
# regarde pas. Une règle recopiée diverge : `tests/test_the_gold_coverage_only_
# improves.py` compare ces deux déclarations et rougit si elles s'écartent.
_RATCHET_SURFACES = ("src/dashboard/views", "src/dashboard/utils", "src/api/routers")
_RATCHET_DOORS = ("src/dashboard/utils/platform_timeseries.py",)
_RATCHET_FACTS = frozenset({
    "s4a_song_timeline", "s4a_audience", "s4a_songs_global",
    "youtube_video_stats", "youtube_channel_history",
    "soundcloud_tracks_daily",
    "apple_songs_performance", "apple_songs_history",
    "instagram_daily_stats", "instagram_media",
    "meta_insights", "meta_insights_performance_day",
    "meta_insights_performance",
    "hypeddit_daily_stats",
    "imusician_monthly_revenue", "distrokid_monthly_revenue", "sacem_statement",
})


def _watched_by_ratchet(rel: str, table: str) -> bool:
    """Le cliquet des agrégats verrait-il une somme ici, sur cette table ?"""
    if rel in _RATCHET_DOORS:
        return False
    if not any(rel.startswith(r + "/") for r in _RATCHET_SURFACES):
        return False
    return table in _RATCHET_FACTS

_MAX_HOPS = 2
_MAX_CALLERS = 3

# ── vocabulaire fermé de la confiance ──────────────────────────────────────
DIRECT = "directe"
LIFTED = "portée"
MANY = "plusieurs amonts"
OFFDB = "hors base"
UNKNOWN = "indéterminée"


# ═══════════════════════════════════════════════════════════════════════════
# Passe A — la couche or, lue dans le SQL
# ═══════════════════════════════════════════════════════════════════════════

def _sql_statements(text: str):
    """Split on `;` outside strings, dollar-quotes and comments.

    A PL/pgSQL body is full of `;` inside `$$ … $$`; splitting naively cuts
    `gold_apple_lifetime` into fifteen fragments and loses its FROM clauses.
    """
    out, buf, i, n = [], [], 0, len(text)
    while i < n:
        c = text[i]
        if c == "-" and text.startswith("--", i):
            j = text.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and text.startswith("/*", i):
            j = text.find("*/", i)
            i = n if j < 0 else j + 2
            continue
        if c == "'":
            j = i + 1
            while j < n:
                if text[j] == "'":
                    if j + 1 < n and text[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            buf.append(text[i:j + 1])
            i = j + 1
            continue
        if c == "$":
            m = re.match(r"\$[a-zA-Z_]*\$", text[i:])
            if m:
                tag = m.group(0)
                j = text.find(tag, i + len(tag))
                j = n if j < 0 else j + len(tag)
                buf.append(text[i:j])
                i = j
                continue
        if c == ";":
            out.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    if "".join(buf).strip():
        out.append("".join(buf))
    return out


_CREATE_RE = re.compile(
    r"\bCREATE\s+(?:OR\s+REPLACE\s+)?(?:MATERIALIZED\s+)?"
    r"(TABLE|VIEW|FUNCTION)\s+(?:IF\s+NOT\s+EXISTS\s+)?"
    r"(?:public\.)?([a-zA-Z_][a-zA-Z0-9_]*)", re.I)
_FROM_RE = re.compile(r"\b(?:FROM|JOIN)\s+(?:public\.)?([a-zA-Z_][a-zA-Z0-9_]*)", re.I)
_CTE_RE = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\s+AS\s*\(", re.I)


@dataclass
class GoldObject:
    kind: str                      # 'vue' | 'fonction'
    name: str
    origin: str                    # migration retenue
    superseded: list[str] = field(default_factory=list)
    reads: set[str] = field(default_factory=set)
    consumers: set[str] = field(default_factory=set)


def scan_sql() -> tuple[dict[str, GoldObject], set[str]]:
    files: list[Path] = []
    for d in _SQL_DIRS:
        files += sorted((ROOT / d).glob("*.sql"))
    for f in _SQL_EXTRA:
        if (ROOT / f).exists():
            files.append(ROOT / f)

    known: set[str] = set()
    gold: dict[str, GoldObject] = {}
    bodies: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for stmt in _sql_statements(text):
            m = _CREATE_RE.search(stmt)
            if not m:
                continue
            kind, name = m.group(1).upper(), m.group(2)
            known.add(name)
            if kind == "VIEW" and name.startswith("v_"):
                bodies[name].append((rel, stmt))
            elif kind == "FUNCTION" and name.startswith("gold_"):
                bodies[name].append((rel, stmt))

    for name, defs in bodies.items():
        rel, stmt = defs[-1]          # la DERNIÈRE par ordre de fichier gagne
        ctes = {c.lower() for c in _CTE_RE.findall(stmt)}
        reads = {r for r in _FROM_RE.findall(stmt)
                 if r.lower() not in ctes and r in known and r != name}
        reads |= {g for g in known
                  if g.startswith("gold_") and g != name
                  and re.search(rf"\b{g}\s*\(", stmt)}
        gold[name] = GoldObject(
            kind="fonction" if name.startswith("gold_") else "vue",
            name=name, origin=rel,
            superseded=[r for r, _ in defs[:-1]],
            reads=reads)
    return gold, known


# ═══════════════════════════════════════════════════════════════════════════
# Passe B — l'index Python
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PyFile:
    rel: str
    tree: ast.AST
    docstrings: set[int]
    parent: dict[int, ast.AST]
    imports: dict[str, str]              # nom local -> module.qualname
    funcs: dict[str, ast.FunctionDef]    # nom -> def (le dernier gagne)
    consts: dict[str, ast.AST] = field(default_factory=dict)
    """Les affectations de NIVEAU MODULE.

    `platform_timeseries.py` range ses requêtes dans `_SQL_LEVELS` et consorts. Une
    tranche qui ne regarde que la portée de la fonction ne les voit pas — et la
    première version de ce script a donc affirmé que la PORTE ne lisait aucune vue
    or, ce qui est exactement l'inverse de son travail.
    """


def _module_name(rel: str) -> str:
    return rel[:-3].replace("/", ".")


def load_python() -> dict[str, PyFile]:
    out: dict[str, PyFile] = {}
    for r in _PY_ROOTS:
        for path in sorted((ROOT / r).rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            rel = path.relative_to(ROOT).as_posix()
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError):
                continue
            docs = set()
            for n in ast.walk(tree):
                if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                  ast.AsyncFunctionDef)) and n.body:
                    first = n.body[0]
                    if (isinstance(first, ast.Expr)
                            and isinstance(first.value, ast.Constant)
                            and isinstance(first.value.value, str)):
                        docs.add(id(first.value))
            parent: dict[int, ast.AST] = {}
            for n in ast.walk(tree):
                for ch in ast.iter_child_nodes(n):
                    parent[id(ch)] = n
            imports: dict[str, str] = {}
            funcs: dict[str, ast.FunctionDef] = {}
            here = _module_name(rel)
            for n in ast.walk(tree):
                if isinstance(n, ast.Import):
                    for a in n.names:
                        imports[a.asname or a.name.split(".")[0]] = a.name
                elif isinstance(n, ast.ImportFrom):
                    mod = n.module or ""
                    if n.level:                      # relatif
                        base = here.rsplit(".", n.level)[0]
                        mod = f"{base}.{mod}" if mod else base
                    for a in n.names:
                        imports[a.asname or a.name] = f"{mod}.{a.name}"
                elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    funcs[n.name] = n
            consts: dict[str, ast.AST] = {}
            for stmt in tree.body:
                if isinstance(stmt, ast.Assign):
                    for t in stmt.targets:
                        if isinstance(t, ast.Name):
                            consts[t.id] = stmt.value
                elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
                    if isinstance(stmt.target, ast.Name):
                        consts[stmt.target.id] = stmt.value
            out[rel] = PyFile(rel, tree, docs, parent, imports, funcs, consts)
    return out


def build_call_index(files: dict[str, PyFile]) -> dict[str, list[tuple[str, ast.AST, ast.Call]]]:
    """qualname de la fonction appelée -> [(fichier, fonction appelante, appel)]."""
    idx: dict[str, list] = defaultdict(list)
    for rel, pf in files.items():
        here = _module_name(rel)
        for fn in _iter_functions(pf.tree):
            for node in ast.walk(fn):
                if not isinstance(node, ast.Call):
                    continue
                q = _qualify(node.func, pf, here)
                if q:
                    idx[q].append((rel, fn, node))
    return idx


def _iter_functions(tree):
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield n


def sql_wrappers(files: dict[str, PyFile]) -> dict[str, int]:
    """`module.fonction -> rang de l'argument qui porte le SQL`, par point fixe.

    ⚠️ Ceci n'est pas un raffinement : sans lui, `platform_timeseries` — LA PORTE —
    paraissait ne lire aucune vue or, parce qu'elle n'appelle jamais `fetch_query`
    en direct. Elle passe par `_q`, `_rows`, `_rows3`. Une chaîne d'enveloppes
    d'un cran suffit à rendre un exécuteur invisible, et c'est précisément le
    module dont le document affirme qu'il porte toutes les règles.

    Une fonction est une enveloppe quand elle passe l'UN DE SES PROPRES PARAMÈTRES
    en première position d'un exécuteur (ou d'une enveloppe déjà connue).
    """
    found: dict[str, int] = {}
    for _ in range(4):                       # la profondeur réelle ici est 2
        grew = False
        for rel, pf in files.items():
            here = _module_name(rel)
            for fn in _iter_functions(pf.tree):
                qual = f"{here}.{fn.name}"
                if qual in found:
                    continue
                a = fn.args
                names = [x.arg for x in list(a.posonlyargs) + list(a.args)]
                hit = None
                for node in ast.walk(fn):
                    if not isinstance(node, ast.Call) or not node.args:
                        continue
                    attr = getattr(node.func, "attr", None)
                    inner = _qualify(node.func, pf, here)
                    pos = 0 if attr in _EXECUTORS else found.get(inner or "", None)
                    if pos is None or pos >= len(node.args):
                        continue
                    carried = node.args[pos]
                    if isinstance(carried, ast.Name) and carried.id in names:
                        hit = names.index(carried.id)
                        break
                if hit is not None:
                    found[qual] = hit
                    grew = True
        if not grew:
            break
    return found


def _qualify(func: ast.AST, pf: PyFile, here: str) -> str | None:
    """`module.fonction` quand on peut le résoudre, sinon None."""
    if isinstance(func, ast.Name):
        if func.id in pf.imports:
            return pf.imports[func.id]
        if func.id in pf.funcs:
            return f"{here}.{func.id}"
        return None
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        base = pf.imports.get(func.value.id)
        if base:
            return f"{base}.{func.attr}"
    return None


# ═══════════════════════════════════════════════════════════════════════════
# Passe C — la tranche arrière
# ═══════════════════════════════════════════════════════════════════════════

def _stmt_paths(fn: ast.AST) -> dict[int, tuple]:
    """id(nœud) -> chemin de blocs, pour le filtre de dominance (§ dominance)."""
    paths: dict[int, tuple] = {}

    def walk_block(block: list, prefix: tuple):
        for i, stmt in enumerate(block):
            here = prefix + ((id(block), i),)
            for node in ast.walk(stmt):
                paths.setdefault(id(node), here)
            for fname in ("body", "orelse", "finalbody"):
                sub = getattr(stmt, fname, None)
                if isinstance(sub, list) and sub and isinstance(sub[0], ast.stmt):
                    walk_block(sub, here)
            for h in getattr(stmt, "handlers", []) or []:
                walk_block(h.body, here)
    walk_block(list(getattr(fn, "body", [])), ())
    return paths


def _dominates(p: tuple, q: tuple) -> bool:
    for (bp, ip), (bq, iq) in zip(p, q):
        if bp != bq:
            return False                      # branches exclusives du même nœud
        if ip < iq:
            return True
        if ip > iq:
            return False
    return len(p) <= len(q)


@dataclass
class Scope:
    fn: ast.AST
    defs: dict[str, list[tuple[int, ast.AST]]]
    mut: dict[str, list[tuple[int, ast.Call]]]
    params: set[str]
    paths: dict[int, tuple]


def build_scope(fn: ast.AST) -> Scope:
    defs: dict[str, list] = defaultdict(list)
    mut: dict[str, list] = defaultdict(list)
    params: set[str] = set()
    a = getattr(fn, "args", None)
    if a:
        for arg in list(a.posonlyargs) + list(a.args) + list(a.kwonlyargs):
            params.add(arg.arg)
        if a.vararg:
            params.add(a.vararg.arg)
        if a.kwarg:
            params.add(a.kwarg.arg)

    def bind(target: ast.AST, value: ast.AST):
        if isinstance(target, ast.Name):
            defs[target.id].append((getattr(target, "lineno", 0), value))
        elif isinstance(target, (ast.Tuple, ast.List)):
            for el in target.elts:
                bind(el, value)
        elif isinstance(target, ast.Subscript):
            base = target.value
            if isinstance(base, ast.Name):
                defs[base.id].append((getattr(target, "lineno", 0), value))
        elif isinstance(target, ast.Attribute):
            if isinstance(target.value, ast.Name):
                defs[target.value.id].append((getattr(target, "lineno", 0), value))

    for node in ast.walk(fn):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node is not fn:
            continue
        if isinstance(node, ast.Assign):
            for t in node.targets:
                bind(t, node.value)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and node.value is not None:
            bind(node.target, node.value)
        elif isinstance(node, ast.NamedExpr):
            bind(node.target, node.value)
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            bind(node.target, node.iter)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    bind(item.optional_vars, item.context_expr)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp, ast.DictComp)):
            for gen in node.generators:
                bind(gen.target, gen.iter)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            recv = node.func.value
            if isinstance(recv, ast.Name) and node.func.attr in (
                    "append", "extend", "add", "update", "add_trace", "add_traces",
                    "setdefault", "insert", "add_scatter", "add_bar"):
                mut[recv.id].append((node.lineno, node))
    return Scope(fn, defs, mut, params, _stmt_paths(fn))


def _sql_text(node: ast.AST, scope: Scope, pf: PyFile) -> str | None:
    """Le SQL littéral d'une expression, avec sentinelle sur toute interpolation."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return None if id(node) in pf.docstrings else node.value
    if isinstance(node, ast.JoinedStr):
        parts = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            else:
                parts.append(_SENTINEL)
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _sql_text(node.left, scope, pf)
        right = _sql_text(node.right, scope, pf)
        if left is None and right is None:
            return None
        return (left or _SENTINEL) + (right or _SENTINEL)
    if isinstance(node, ast.Name):
        cands = [v for _, v in (scope.defs.get(node.id) or [])]
        if not cands and node.id in pf.consts:
            cands = [pf.consts[node.id]]
        texts = [t for t in (_sql_text(v, scope, pf) for v in cands) if t]
        return texts[-1] if texts else None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
            and node.func.attr in ("format", "join", "strip"):
        return _SENTINEL
    return None


@dataclass
class Slice:
    sources: set[tuple[str, str]] = field(default_factory=set)   # (genre, nom)
    flags: set[str] = field(default_factory=set)
    hops: list[str] = field(default_factory=list)
    branched: bool = False


class Slicer:
    def __init__(self, files, call_index, gold, known, wrappers):
        self.files = files
        self.calls = call_index
        self.gold = gold
        self.known = known
        self.wrappers = wrappers

    def sql_arg(self, call: ast.Call, pf: PyFile, here: str):
        """L'expression SQL de cet appel s'il exécute quelque chose, sinon None."""
        attr = getattr(call.func, "attr", None)
        if attr in _EXECUTORS:
            if call.args:
                return call.args[0]
            for kw in call.keywords:
                if kw.arg in ("query", "sql"):
                    return kw.value
            return ast.Constant(value="")
        pos = self.wrappers.get(_qualify(call.func, pf, here) or "")
        if pos is not None and pos < len(call.args):
            return call.args[pos]
        return None

    # ── lecture d'un exécuteur SQL ────────────────────────────────────────
    def _read_sql(self, arg, scope: Scope, pf: PyFile, out: Slice):
        text = _sql_text(arg, scope, pf) if arg is not None else None
        if not text:
            out.flags.add("sql-dynamique")
            return
        ctes = {c.lower() for c in _CTE_RE.findall(text)}
        seen_any = False
        for ident in _FROM_RE.findall(text):
            if ident.startswith("\x00") or _SENTINEL in ident:
                out.flags.add("sql-dynamique")
                continue
            if ident.lower() in ctes:
                continue
            if ident in self.known:
                kind = ("vue_or" if ident in self.gold and self.gold[ident].kind == "vue"
                        else "fonction_or" if ident in self.gold else "table_brute")
                out.sources.add((kind, ident))
                seen_any = True
            else:
                out.flags.add(f"identifiant-non-résolu:{ident}")
        for g in self.gold:
            if g.startswith("gold_") and re.search(rf"\b{g}\s*\(", text):
                out.sources.add(("fonction_or", g))
                seen_any = True
        if _SENTINEL in text and re.search(r"\b(?:FROM|JOIN)\s*$",
                                           text.split(_SENTINEL)[0].rstrip(), re.I):
            out.flags.add("sql-dynamique")
        if not seen_any and _SENTINEL in text:
            out.flags.add("sql-dynamique")

    # ── la tranche ────────────────────────────────────────────────────────
    def slice(self, rel: str, fn: ast.AST, seeds: list[ast.AST],
              anchor: ast.AST, hop: int = 0,
              visited: frozenset = frozenset()) -> Slice:
        out = Slice()
        pf = self.files[rel]
        scope = build_scope(fn)
        here = _module_name(rel)
        target_path = scope.paths.get(id(anchor), ())
        work = list(seeds)
        seen_nodes: set[int] = set()

        while work:
            node = work.pop()
            if node is None or id(node) in seen_nodes:
                continue
            seen_nodes.add(id(node))

            if isinstance(node, ast.Name):
                cands = [(ln, v) for ln, v in scope.defs.get(node.id, [])
                         if _dominates(scope.paths.get(id(v), ()), target_path)]
                if len(cands) > 1:
                    out.branched = True
                for _, v in cands:
                    work.append(v)
                for ln, m in scope.mut.get(node.id, []):
                    if _dominates(scope.paths.get(id(m), ()), target_path):
                        work.extend(self._carriers(m))
                if not cands and node.id in scope.params:
                    self._lift(rel, fn, node.id, out, hop, visited)
                continue

            if isinstance(node, ast.Call):
                fname = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                arg = self.sql_arg(node, pf, here)
                if arg is not None:
                    self._read_sql(arg, scope, pf, out)
                    continue
                q = _qualify(node.func, pf, here)
                if q and any(q.startswith(d + ".") for d in _DOOR_MODULES):
                    out.sources.add(("porte", q))
                    continue
                if fname in _STOP_CALLS:
                    continue
                if q and hop < _MAX_HOPS:
                    tgt = self._definition(q)
                    if tgt is not None:
                        trel, tfn = tgt
                        key = (trel, tfn.name)
                        if key not in visited:
                            sub = self._returns(trel, tfn, hop + 1, visited | {key})
                            out.sources |= sub.sources
                            out.flags |= sub.flags
                            out.branched |= sub.branched
                            continue
                work.extend(self._carriers(node))
                continue

            for child in ast.iter_child_nodes(node):
                work.append(child)
        return out

    def _carriers(self, call: ast.Call) -> list[ast.AST]:
        out: list[ast.AST] = []
        if isinstance(call.func, ast.Attribute):
            out.append(call.func.value)
        out.extend(call.args)
        for kw in call.keywords:
            if kw.arg not in _PRESENTATION_KW:
                out.append(kw.value)
        return out

    def _definition(self, qual: str):
        mod, _, name = qual.rpartition(".")
        rel = mod.replace(".", "/") + ".py"
        pf = self.files.get(rel)
        if pf and name in pf.funcs:
            return rel, pf.funcs[name]
        return None

    def _returns(self, rel: str, fn: ast.AST, hop: int, visited) -> Slice:
        out = Slice()
        rets = [n.value for n in ast.walk(fn)
                if isinstance(n, ast.Return) and n.value is not None]
        for r in rets:
            sub = self.slice(rel, fn, [r], r, hop, visited)
            out.sources |= sub.sources
            out.flags |= sub.flags
            out.branched |= sub.branched
        if not rets:
            out.flags.add("sans-retour")
        return out

    def _lift(self, rel: str, fn: ast.AST, param: str, out: Slice,
              hop: int, visited):
        if hop >= _MAX_HOPS:
            out.flags.add("profondeur")
            return
        here = _module_name(rel)
        sites = self.calls.get(f"{here}.{fn.name}", [])
        if not sites:
            out.flags.add("sans-appelant")
            return
        if len(sites) > _MAX_CALLERS:
            out.flags.add("appelants-multiples")
            return
        if len(sites) > 1:
            out.branched = True
        for crel, cfn, call in sites:
            key = (crel, cfn.name, param)
            if key in visited:
                continue
            actual = self._actual(call, fn, param)
            if actual is None:
                out.flags.add("clé-à-l-exécution")
                continue
            sub = self.slice(crel, cfn, [actual], call, hop + 1, visited | {key})
            out.sources |= sub.sources
            out.flags |= sub.flags
            out.branched |= sub.branched
            out.hops.append(f"{crel.rsplit('/', 1)[-1]}::{cfn.name}")

    @staticmethod
    def _actual(call: ast.Call, fn: ast.AST, param: str):
        a = getattr(fn, "args", None)
        if a is None:
            return None
        names = [x.arg for x in list(a.posonlyargs) + list(a.args)]
        for kw in call.keywords:
            if kw.arg == param:
                return kw.value
        if param in names:
            i = names.index(param)
            if i < len(call.args):
                return call.args[i]
        return None


@dataclass
class Read:
    rel: str
    line: int
    relations: frozenset
    aggregates: bool
    door: bool


def all_reads(files, slicer) -> list[Read]:
    """Chaque lecture SQL de `src/`, où qu'elle soit.

    ⚠️ Ceci ne se déduit PAS des tranches. La première version comptait les
    lecteurs d'une vue or à partir des seules surfaces atteintes, et a donc
    déclaré `v_meta_spend_totals` « sans consommateur » alors que
    `meta_breakdowns.py:263` la lit — dans une f-string, au fond d'une fonction
    qu'aucune tranche de figure ne traverse. Une affirmation d'absence tirée d'un
    balayage partiel est exactement le défaut que ce document existe pour nommer.
    """
    out: list[Read] = []
    for rel, pf in sorted(files.items()):
        here = _module_name(rel)
        door = here in _DOOR_MODULES
        for fn in list(_iter_functions(pf.tree)) + [pf.tree]:
            scope = build_scope(fn)
            for node in ast.walk(fn):
                if not isinstance(node, ast.Call):
                    continue
                if _enclosing(pf, node) is not (fn if fn is not pf.tree else None):
                    continue
                arg = slicer.sql_arg(node, pf, here)
                if arg is None:
                    continue
                tmp = Slice()
                slicer._read_sql(arg, scope, pf, tmp)
                if not tmp.sources:
                    continue
                text = _sql_text(arg, scope, pf) or ""
                out.append(Read(rel, node.lineno,
                                frozenset(n for _, n in tmp.sources),
                                bool(_AGG_RE.search(text)), door))
    return out


def verdict(sl: Slice) -> str:
    if sl.flags and not sl.sources:
        return UNKNOWN
    if not sl.sources:
        return OFFDB
    if sl.branched:
        return MANY
    if sl.hops:
        return f"{LIFTED} ({len(set(sl.hops))} saut{'s' if len(set(sl.hops)) > 1 else ''})"
    return DIRECT


def layer_of(sl: Slice) -> str:
    kinds = {k for k, _ in sl.sources}
    if not kinds:
        return "—"
    gold = kinds & {"vue_or", "fonction_or"}
    raw = kinds & {"table_brute"}
    door = kinds & {"porte"}
    if raw and (gold or door):
        return "mixte"
    if raw:
        return "brut"
    return "or"


# ═══════════════════════════════════════════════════════════════════════════
# Les surfaces
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class Surface:
    kind: str                  # 'figure' | 'tuile' | 'pdf'
    rel: str
    line: int
    fn: str
    what: str
    visible: str
    sl: Slice
    neighbourhood: set[str] = field(default_factory=set)


def _enclosing(pf: PyFile, node: ast.AST):
    cur = pf.parent.get(id(node))
    while cur is not None and not isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
        cur = pf.parent.get(id(cur))
    return cur


def _visibility(pf: PyFile, node: ast.AST) -> str:
    cur = pf.parent.get(id(node))
    seen = "à l'écran"
    while cur is not None:
        if isinstance(cur, (ast.With, ast.AsyncWith)):
            for item in cur.items:
                ctx = item.context_expr
                if isinstance(ctx, ast.Call):
                    a = getattr(ctx.func, "attr", "")
                    if a == "expander":
                        return "un clic"
                    if a in ("tabs", "container", "popover"):
                        seen = "autre onglet"
                if isinstance(ctx, ast.Subscript):
                    seen = "autre onglet"
        cur = pf.parent.get(id(cur))
    return seen


def _column_receivers(fn: ast.AST) -> set[str]:
    """Les noms liés à `st.columns(...)` / `st.tabs(...)`, receveurs légitimes."""
    out: set[str] = set()

    def note(target, value):
        if not (isinstance(value, ast.Call)
                and getattr(value.func, "attr", "") in ("columns", "tabs")):
            return
        if isinstance(target, ast.Name):
            out.add(target.id)
        elif isinstance(target, (ast.Tuple, ast.List)):
            for el in target.elts:
                if isinstance(el, ast.Name):
                    out.add(el.id)

    for n in ast.walk(fn):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                note(t, n.value)
    return out


def collect_surfaces(files, slicer) -> list[Surface]:
    out: list[Surface] = []
    for rel, pf in sorted(files.items()):
        if not rel.startswith("src/dashboard/"):
            continue
        for fn in _iter_functions(pf.tree):
            cols = _column_receivers(fn)
            for node in ast.walk(fn):
                if not (isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Attribute)):
                    continue
                attr = node.func.attr
                recv = node.func.value
                recv_txt = recv.id if isinstance(recv, ast.Name) else (
                    ast.unparse(recv) if isinstance(recv, (ast.Subscript, ast.Attribute))
                    else "?")
                if _enclosing(pf, node) is not fn:
                    continue
                if attr in _FIGURE_CALLS and recv_txt == "st":
                    seeds = [a for a in node.args[:1]]
                    sl = slicer.slice(rel, fn, seeds, node)
                    out.append(Surface("figure", rel, node.lineno, fn.name,
                                       attr, _visibility(pf, node), sl))
                elif attr == "metric":
                    base = recv_txt.split("[")[0]
                    if recv_txt != "st" and base not in cols:
                        sl = Slice(flags={"receveur-inconnu"})
                        out.append(Surface("tuile", rel, node.lineno, fn.name,
                                           f"{recv_txt}.metric", _visibility(pf, node), sl))
                        continue
                    # Le LIBELLÉ n'est pas une donnée : le suivre mène dans `i18n.t`
                    # et ses 2 397 appelants. Seuls `value` et `delta` sont des graines.
                    seeds = list(node.args[1:])
                    for kw in node.keywords:
                        if kw.arg in ("value", "delta"):
                            seeds.append(kw.value)
                    label = _label_of(node)
                    sl = slicer.slice(rel, fn, seeds, node)
                    out.append(Surface("tuile", rel, node.lineno, fn.name,
                                       label, _visibility(pf, node), sl))
    return out


def _label_of(node: ast.Call) -> str:
    arg = node.args[0] if node.args else None
    for kw in node.keywords:
        if kw.arg == "label":
            arg = kw.value
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return arg.value[:40]
    if isinstance(arg, ast.Call) and getattr(arg.func, "id", "") in ("t", "_t"):
        for a in arg.args:
            if isinstance(a, ast.Constant) and isinstance(a.value, str):
                return a.value[:40]
    return "—"


def collect_pdf(files, slicer) -> list[Surface]:
    """Les figures PDF, prises à leur SITE DE CÂBLAGE, pas dans `pdf_charts`.

    Les 29 fonctions de `pdf_charts.py` reçoivent toutes leurs données en
    paramètre : y trancher meurt par construction. Le câblage est centralisé dans
    `_report.py`, et c'est là que la chaîne commence.
    """
    out: list[Surface] = []
    rel = "src/dashboard/utils/pdf_exporter/_report.py"
    pf = files.get(rel)
    if pf is None:
        return out
    for fn in _iter_functions(pf.tree):
        for node in ast.walk(fn):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "pdf_charts"):
                continue
            seeds = [a for a in node.args] + [
                kw.value for kw in node.keywords if kw.arg not in _PRESENTATION_KW]
            sl = slicer.slice(rel, fn, seeds, node)
            out.append(Surface("pdf", rel, node.lineno, fn.name,
                               f"pdf_charts.{node.func.attr}", "PDF", sl))
    return out


def neighbourhood(files, slicer, surfaces):
    """Ce que la fonction englobante lit, SANS lien prouvé — colonne séparée."""
    cache: dict[tuple[str, str], set[str]] = {}
    for s in surfaces:
        key = (s.rel, s.fn)
        if key not in cache:
            pf = files[s.rel]
            fn = pf.funcs.get(s.fn)
            if fn is None:
                fn = next((f for f in _iter_functions(pf.tree) if f.name == s.fn), None)
            found: set[str] = set()
            if fn is not None:
                scope = build_scope(fn)
                here = _module_name(s.rel)
                for node in ast.walk(fn):
                    if isinstance(node, ast.Call):
                        arg = slicer.sql_arg(node, pf, here)
                        if arg is None:
                            continue
                        tmp = Slice()
                        slicer._read_sql(arg, scope, pf, tmp)
                        found |= {n for _, n in tmp.sources}
            cache[key] = found
        s.neighbourhood = cache[key] - {n for _, n in s.sl.sources}


# ═══════════════════════════════════════════════════════════════════════════
# Le rendu
# ═══════════════════════════════════════════════════════════════════════════

_LIMITS = [
    ("sql-dynamique",
     "requête ou table assemblée hors littéral — indécidable sans exécuter"),
    ("identifiant-non-résolu",
     "un nom capté dans un FROM qui n'existe ni en migration ni dans init_db.sql "
     "(CTE, alias, sous-requête) — écarté plutôt que publié"),
    ("appelants-multiples",
     "rendu partagé par plus de trois appelants : un site, N jeux de données"),
    ("profondeur",
     f"chaîne de plus de {_MAX_HOPS} sauts — plafond assumé"),
    ("sans-appelant",
     "fonction dont aucun appel n'est résoluble statiquement"),
    ("clé-à-l-exécution",
     "argument passé par **kwargs, partial, ou conteneur indexé par une variable"),
    ("receveur-inconnu",
     "`X.metric(...)` où X n'est lié ni à st.columns ni à st.tabs — compté, pas deviné"),
    ("sans-retour",
     "fonction traversée qui ne retourne rien d'attribuable"),
]


def _fmt_sources(sl: Slice) -> str:
    if not sl.sources:
        return "—"
    order = {"vue_or": 0, "fonction_or": 1, "porte": 2, "table_brute": 3}
    items = sorted(sl.sources, key=lambda s: (order.get(s[0], 9), s[1]))
    return " · ".join(
        (f"`{n.rsplit('.', 1)[-1]}()`" if k == "porte" else f"`{n}`")
        for k, n in items)


def _fmt_flags(sl: Slice) -> str:
    if not sl.flags:
        return ""
    return " · ".join(sorted(f.split(":")[0] for f in sl.flags))


def _table(rows: list[list[str]], head: list[str]) -> list[str]:
    out = ["| " + " | ".join(head) + " |",
           "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(c.replace("|", "\\|") for c in r) + " |" for r in rows]
    return out


def _surface_rows(surfaces: list[Surface]) -> list[list[str]]:
    def rank(s: Surface):
        v = verdict(s.sl)
        return (0 if v == UNKNOWN else 1 if v == MANY else 2, s.rel, s.line)
    rows = []
    for s in sorted(surfaces, key=rank):
        v = verdict(s.sl)
        mark = "⚠️ " if v == UNKNOWN else ""
        nb = " · ".join(f"?`{n}`" for n in sorted(s.neighbourhood)) or "—"
        rows.append([
            f"{mark}`{s.rel.split('src/dashboard/')[-1]}:{s.line}`",
            f"`{s.fn}`", s.what, s.visible,
            _fmt_sources(s.sl), layer_of(s.sl), v,
            _fmt_flags(s.sl) or "—", nb,
        ])
    return rows


_HEAD = ["fichier:ligne", "fonction", "surface", "visible",
         "source établie", "couche", "confiance", "motif",
         "lu dans la même fonction (aucun lien prouvé)"]


def render(gold, surfaces, files, reads) -> str:
    figs = [s for s in surfaces if s.kind == "figure"]
    tiles = [s for s in surfaces if s.kind == "tuile"]
    pdfs = [s for s in surfaces if s.kind == "pdf"]

    def counts(group):
        v = [verdict(s.sl) for s in group]
        return (len(group),
                sum(1 for x in v if x == UNKNOWN),
                sum(1 for x in v if x == OFFDB),
                sum(1 for x in v if x == MANY))

    flag_counts: dict[str, int] = defaultdict(int)
    for s in surfaces:
        for f in s.sl.flags:
            flag_counts[f.split(":")[0]] += 1

    L = [
        "# Couverture de la couche or",
        "",
        "<!-- GÉNÉRÉ par `tools/dev/gold_coverage.py` — toute édition à la main est "
        "perdue à la prochaine exécution. `make gold-coverage` -->",
        "",
        "Ce document répond à une seule question, pour chaque figure, chaque tuile et "
        "chaque figure du PDF : **quelle donnée dessine-t-elle, et passe-t-elle par la "
        "couche or ?**",
        "",
        "Il est écrit par une machine qui lit `migrations/*.sql`, `init_db.sql` et "
        "l'AST de `src/`. Elle n'exécute rien, ne lit aucune base, et **ne porte aucun "
        "horodatage** — deux exécutions sur le même arbre rendent exactement les mêmes "
        "octets, ce qui est la seule façon pour `--check` de dire quelque chose.",
        "",
        "## Ce que ce document ne sait pas",
        "",
        "Lis cette section avant les tableaux. Un aveu placé après la donnée est un "
        "aveu que personne ne lit.",
        "",
        "Une attribution n'est publiée que s'il existe un **chemin def-use prouvé** "
        "entre une lecture SQL et la surface. Quand il n'y en a pas, la colonne "
        "« source établie » vaut `—` et la ligne porte un motif. Elle n'est **jamais** "
        "remplie par ce que la fonction lit à côté : cette colonne-là existe, elle est "
        "la dernière, et son en-tête dit qu'elle ne prouve rien.",
        "",
    ]
    L += _table(
        [[f"`{k}`", d, str(flag_counts.get(k, 0))] for k, d in _LIMITS],
        ["motif", "ce qu'il veut dire", "occurrences"])
    L += [
        "",
        "Cinq mots de confiance, et rien d'autre :",
        "",
        f"- **{DIRECT}** — la tranche est restée dans une fonction et a atteint un "
        "exécuteur à SQL littéral, ou une porte.",
        f"- **{LIFTED} (N sauts)** — N relèvements de paramètre, **chacun vers un "
        "appelant unique**.",
        f"- **{MANY}** — plusieurs définitions ou plusieurs appelants : l'union est "
        "listée, aucune n'est choisie.",
        f"- **{OFFDB}** — la tranche s'est terminée proprement sans lecture de base "
        "(CSV déposé, artefact ML, appel REST). **Ce n'est pas un échec.**",
        f"- **{UNKNOWN}** — la tranche est tronquée. Toujours accompagnée d'un motif, "
        "et triée **en tête** de son tableau.",
        "",
        "## La couche or",
        "",
    ]
    grows = sorted(gold.values(), key=lambda g: (g.kind, g.name))
    L += _table(
        [[f"`{g.name}`", g.kind, f"`{g.origin}`",
          " · ".join(f"`{r}`" for r in sorted(g.reads)) or "—",
          str(len(g.consumers)),
          " · ".join(f"`{s}`" for s in g.superseded) or "—"]
         for g in grows],
        ["objet", "genre", "définie par", "lit", "surfaces qui la lisent",
         "définitions supplantées"])

    for title, group, note in (
        ("Les figures d'écran", figs,
         "Une ligne par **site de code**, pas par figure rendue : une figure dans une "
         "boucle est un site et N images."),
        ("Les tuiles", tiles,
         "`st.metric` n'est que 17 des 207 tuiles du produit ; les 190 autres passent "
         "par une poignée de colonne (`c1.metric`). Un inventaire qui n'aurait compté "
         "que le receveur `st` décrirait 8 % du produit."),
        ("Les figures du PDF", pdfs,
         "Prises à leur site de câblage dans `_report.py` : les fonctions de "
         "`pdf_charts.py` reçoivent tout en paramètre, y trancher ne dirait rien."),
    ):
        n, unk, off, many = counts(group)
        L += [
            "", f"## {title}", "", note, "",
            f"**{n - unk - off} sur {n}** portent une source établie ; **{unk}** "
            f"sont déclarées indéterminées et listées en tête ; {off} sont hors base "
            f"par nature — la tranche a fini proprement sans lire la base — et {many} "
            f"des attribuées ont plusieurs amonts.", "",
        ]
        L += _table(_surface_rows(group), _HEAD)

    unread = sorted(g.name for g in gold.values()
                    if not any(g.name in r.relations for r in reads))
    gold_reads = {t: g.name for g in gold.values() for t in g.reads
                  if not t.startswith(("v_", "gold_"))}
    covered: dict[str, list[Read]] = defaultdict(list)
    for r in reads:
        if r.door:
            continue
        for t in r.relations:
            if t in gold_reads:
                covered[t].append(r)
    L += [
        "", "## Ce qui n'est atteint par rien", "",
        "C'est la vraie valeur de ce document. Les deux tableaux ne disent pas la "
        "même chose et il ne faut pas les lire pareil.", "",
        "**Vues or que rien ne lit dans `src/` :** "
        + (" · ".join(f"`{n}`" for n in unread) if unread else "aucune")
        + ". Une vue or sans lecteur est du travail gelé — soit la surface qui "
        "devait la lire ne l'a jamais fait, soit la vue n'avait pas lieu d'être.", "",
        "Le second tableau liste les **tables brutes encore lues hors des portes**, "
        "alors qu'une vue or couvre le même grain. Ce n'est pas une liste de "
        "défauts : une lecture non agrégée — un catalogue, une date de dernier "
        "relevé, une liste de titres — n'a pas de définition à centraliser.", "",
        "**La colonne qui compte est « dont hors cliquet ».** "
        "`tests/test_the_metrics_layer_only_grows.py` tient les agrégats à zéro, "
        "mais seulement sur les répertoires qu'il nomme "
        + " · ".join(f"`{r}`" for r in _RATCHET_SURFACES)
        + " et sur les tables de sa propre liste de faits. Un agrégat hors de ces "
        "deux périmètres n'est gardé par rien. C'est exactement la forme du défaut "
        "du 2026-09-12 : le cliquet disait zéro, douze agrégats vivaient dans un "
        "répertoire qu'il ne nommait pas. Ces lignes-là sont les suivantes à "
        "regarder — chacune est soit un agrégat à repointer, soit un `MIN`/`MAX`/"
        "`COUNT` d'inventaire qui n'a rien à centraliser.", "",
    ]
    unguarded = sum(1 for rs in covered.values() for r in rs
                    if r.aggregates
                    and not _watched_by_ratchet(r.rel, next(iter(r.relations & set(gold_reads)))))
    if covered:
        rows = []
        for t, rs in sorted(covered.items()):
            agg = [r for r in rs if r.aggregates]
            blind = [r for r in agg if not _watched_by_ratchet(r.rel, t)]
            rows.append([
                f"`{t}`", f"`{gold_reads[t]}`", str(len(rs)),
                str(len(agg)) if agg else "—",
                f"**{len(blind)}**" if blind else "0",
                " · ".join(sorted({f"{r.rel.split('src/')[-1]}:{r.line}"
                                   for r in (blind or agg or rs)})[:8]),
            ])
        rows.sort(key=lambda r: -int(r[4].strip("*") or 0))
        L += _table(rows, ["table brute", "vue or qui la couvre", "lectures",
                           "agrégeantes", "dont hors cliquet",
                           "où (les hors-cliquet d'abord)"])
    else:
        L += ["Aucune table brute couverte par une vue or n'est lue ailleurs.", ""]

    n_f, u_f, _, _ = counts(figs)
    n_t, u_t, _, _ = counts(tiles)
    n_p, u_p, _, _ = counts(pdfs)
    L += [
        "", "## Les chiffres gelés", "",
        "Ces compteurs sont écrits par la machine. Le cliquet "
        "`tests/test_the_gold_coverage_only_improves.py` les compare à un plafond "
        "posé **à** la mesure, jamais au-dessus.", "",
        f"<!-- gold-coverage-figures: total={n_f} unknown={u_f} -->",
        f"<!-- gold-coverage-tiles: total={n_t} unknown={u_t} -->",
        f"<!-- gold-coverage-pdf: total={n_p} unknown={u_p} -->",
        f"<!-- gold-coverage-gold-objects: total={len(gold)} orphans={len(unread)} -->",
        f"<!-- gold-coverage-unguarded-aggregates: total={unguarded} -->",
        "",
    ]
    body = "\n".join(L).rstrip("\n") + "\n"
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return body + f"\n<!-- gold-coverage: sha256={digest} -->\n"


# ═══════════════════════════════════════════════════════════════════════════

def build() -> str:
    gold, known = scan_sql()
    files = load_python()
    calls = build_call_index(files)
    slicer = Slicer(files, calls, gold, known, sql_wrappers(files))
    surfaces = collect_surfaces(files, slicer) + collect_pdf(files, slicer)
    neighbourhood(files, slicer, surfaces)
    for s in surfaces:
        for _, name in s.sl.sources:
            if name in gold:
                gold[name].consumers.add(f"{s.rel}:{s.line}")
    # Une porte qui lit une vue or compte comme consommatrice de cette vue.
    for rel, pf in files.items():
        if _module_name(rel) not in _DOOR_MODULES:
            continue
        here = _module_name(rel)
        for fn in _iter_functions(pf.tree):
            scope = build_scope(fn)
            for node in ast.walk(fn):
                if not isinstance(node, ast.Call):
                    continue
                arg = slicer.sql_arg(node, pf, here)
                if arg is None:
                    continue
                tmp = Slice()
                slicer._read_sql(arg, scope, pf, tmp)
                for _, name in tmp.sources:
                    if name in gold:
                        gold[name].consumers.add(f"{rel}:{node.lineno}")
    reads = all_reads(files, slicer)
    for r in reads:
        for name in r.relations:
            if name in gold:
                gold[name].consumers.add(f"{r.rel}:{r.line}")
    return render(gold, surfaces, files, reads)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="sort ≠ 0 si le document sur le disque n'est pas celui-ci")
    args = ap.parse_args()
    fresh = build()
    if args.check:
        current = DOC.read_text(encoding="utf-8") if DOC.exists() else ""
        if current == fresh:
            return 0
        diff = "".join(difflib.unified_diff(
            current.splitlines(keepends=True), fresh.splitlines(keepends=True),
            fromfile="sur le disque", tofile="ce que le dépôt dit", n=1))
        sys.stderr.write(
            "`.claude/dev-docs/gold-coverage.md` ne décrit plus le dépôt.\n"
            "Remède : make gold-coverage\n\n" + diff[:8000] + "\n")
        return 1
    DOC.parent.mkdir(parents=True, exist_ok=True)
    DOC.write_text(fresh, encoding="utf-8")
    print(f"écrit : {DOC.relative_to(ROOT)} ({len(fresh.splitlines())} lignes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
