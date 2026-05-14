#!/usr/bin/env python3
"""
generate-dev-docs.py — Layer 2 dev-docs automation
Scans a Python project and fills AUTO:MARKER_BEGIN/END sections in dev-doc templates.

Usage:
    python3 tools/generate-dev-docs.py --project-dir . --src-dir src/Application
    python3 tools/generate-dev-docs.py --project-dir . --src-dir src/app --dry-run --verbose

Only stdlib dependencies. No PyYAML, no requests, nothing to install.
"""

import argparse
import ast
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def detect_framework(src_dir: Path) -> str:
    """Return 'fastapi' | 'flask' | 'django' | 'generic' by scanning imports."""
    candidates = {"fastapi": 0, "flask": 0, "django": 0}
    for py_file in src_dir.rglob("*.py"):
        try:
            text = py_file.read_text(errors="replace")
        except OSError:
            continue
        if re.search(r"\bfrom fastapi\b|\bimport fastapi\b", text):
            candidates["fastapi"] += 1
        if re.search(r"\bfrom flask\b|\bimport flask\b", text):
            candidates["flask"] += 1
        if re.search(r"\bfrom django\b|\bimport django\b", text):
            candidates["django"] += 1
    winner = max(candidates, key=lambda k: candidates[k])
    return winner if candidates[winner] > 0 else "generic"


def detect_db(src_dir: Path) -> str:
    """Return 'sqlite' | 'postgres' | 'mysql' | 'none'."""
    scores = {"sqlite": 0, "postgres": 0, "mysql": 0}
    for py_file in src_dir.rglob("*.py"):
        try:
            text = py_file.read_text(errors="replace")
        except OSError:
            continue
        if re.search(r"\bsqlite3\b|<your-volume>\.db|\.db[\"']", text):
            scores["sqlite"] += 1
        if re.search(r"\bpsycopg2\b|postgresql\b", text):
            scores["postgres"] += 1
        if re.search(r"\bpymysql\b|mysqlconnector\b", text):
            scores["mysql"] += 1
    winner = max(scores, key=lambda k: scores[k])
    return winner if scores[winner] > 0 else "none"


def detect_ml(src_dir: Path) -> bool:
    """True if ML libraries found."""
    ml_keywords = r"\bsklearn\b|\bxgboost\b|\btorch\b|\btensorflow\b|\bkeras\b|\bmlflow\b|\bshap\b"
    for py_file in src_dir.rglob("*.py"):
        try:
            text = py_file.read_text(errors="replace")
        except OSError:
            continue
        if re.search(ml_keywords, text):
            return True
    return False


def detect_docker(project_dir: Path) -> bool:
    """True if docker-compose.yml or docker-compose.yaml exists."""
    return (
        (project_dir / "docker-compose.yml").exists()
        or (project_dir / "docker-compose.yaml").exists()
    )


# ---------------------------------------------------------------------------
# Extraction: FastAPI routes
# ---------------------------------------------------------------------------

def extract_fastapi_routes(src_dir: Path) -> list[dict]:
    """
    Extract FastAPI routes from @app.<method> and @router.<method> decorators.
    Returns list of {method, path, file, func, description}.
    """
    route_pattern = re.compile(
        r'@(?:app|router)\.(get|post|put|delete|patch|head|options)\s*\(\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )
    func_pattern = re.compile(r"async def (\w+)|def (\w+)")
    routes = []
    seen = set()

    for py_file in sorted(src_dir.rglob("*.py")):
        if "test" in py_file.parts:
            continue
        try:
            lines = py_file.read_text(errors="replace").splitlines()
        except OSError:
            continue

        for i, line in enumerate(lines):
            m = route_pattern.search(line)
            if not m:
                continue
            method = m.group(1).upper()
            path = m.group(2)
            # Find the function name on the next non-blank, non-decorator line
            func_name = ""
            for j in range(i + 1, min(i + 6, len(lines))):
                fm = func_pattern.search(lines[j])
                if fm:
                    func_name = fm.group(1) or fm.group(2)
                    break
            # Grab docstring if present
            description = ""
            if func_name:
                for j in range(i + 1, min(i + 10, len(lines))):
                    stripped = lines[j].strip()
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        description = stripped.strip('"\' ')
                        break

            key = (method, path)
            if key not in seen:
                seen.add(key)
                routes.append(
                    {
                        "method": method,
                        "path": path,
                        "file": str(py_file.relative_to(src_dir)),
                        "func": func_name,
                        "description": description,
                    }
                )

    return sorted(routes, key=lambda r: (r["path"], r["method"]))


# ---------------------------------------------------------------------------
# Extraction: Flask routes
# ---------------------------------------------------------------------------

def extract_flask_routes(src_dir: Path) -> list[dict]:
    """Extract Flask @app.route and @bp.route decorators."""
    route_pattern = re.compile(
        r'@(?:\w+)\.route\s*\(\s*["\']([^"\']+)["\'][^)]*(?:methods\s*=\s*\[([^\]]+)\])?',
        re.IGNORECASE,
    )
    func_pattern = re.compile(r"def (\w+)")
    routes = []
    seen = set()

    for py_file in sorted(src_dir.rglob("*.py")):
        if "test" in py_file.parts:
            continue
        try:
            lines = py_file.read_text(errors="replace").splitlines()
        except OSError:
            continue

        for i, line in enumerate(lines):
            m = route_pattern.search(line)
            if not m:
                continue
            path = m.group(1)
            raw_methods = m.group(2) or "GET"
            methods = [x.strip().strip("\"'").upper() for x in raw_methods.split(",")]
            func_name = ""
            for j in range(i + 1, min(i + 4, len(lines))):
                fm = func_pattern.search(lines[j])
                if fm:
                    func_name = fm.group(1)
                    break
            for method in methods:
                key = (method, path)
                if key not in seen:
                    seen.add(key)
                    routes.append(
                        {
                            "method": method,
                            "path": path,
                            "file": str(py_file.relative_to(src_dir)),
                            "func": func_name,
                            "description": "",
                        }
                    )

    return sorted(routes, key=lambda r: (r["path"], r["method"]))


# ---------------------------------------------------------------------------
# Extraction: SQL tables
# ---------------------------------------------------------------------------

def extract_sql_tables(src_dir: Path) -> list[dict]:
    """
    Extract table names from:
    - CREATE TABLE statements
    - SQLAlchemy __tablename__ attributes
    Returns list of {name, columns, source}.
    """
    create_pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?[`\"]?(\w+)[`\"]?\s*\(([^;]+)\)",
        re.IGNORECASE | re.DOTALL,
    )
    tablename_pattern = re.compile(r'__tablename__\s*=\s*["\'](\w+)["\']')
    tables = {}

    for py_file in sorted(src_dir.rglob("*.py")):
        if "test" in py_file.parts:
            continue
        try:
            text = py_file.read_text(errors="replace")
        except OSError:
            continue

        # CREATE TABLE
        for m in create_pattern.finditer(text):
            name = m.group(1)
            raw_cols = m.group(2)
            cols = []
            for col_line in raw_cols.splitlines():
                col_line = col_line.strip().rstrip(",")
                if not col_line or col_line.upper().startswith(("PRIMARY", "FOREIGN", "UNIQUE", "INDEX", "CHECK")):
                    continue
                col_parts = col_line.split()
                if col_parts:
                    cols.append(col_parts[0].strip("`\"'"))
            if name not in tables:
                tables[name] = {
                    "name": name,
                    "columns": cols,
                    "source": str(py_file.relative_to(src_dir)),
                }

        # SQLAlchemy __tablename__
        for m in tablename_pattern.finditer(text):
            name = m.group(1)
            if name not in tables:
                tables[name] = {
                    "name": name,
                    "columns": [],
                    "source": str(py_file.relative_to(src_dir)),
                }

    return sorted(tables.values(), key=lambda t: t["name"])


# ---------------------------------------------------------------------------
# Extraction: Module inventory
# ---------------------------------------------------------------------------

def build_module_inventory(src_dir: Path) -> list[dict]:
    """
    Return one dict per .py file (excluding tests/__init__/migrations):
    {file, description, key_functions, classes, size_lines}
    Description = first docstring or first comment or "".
    """
    inventory = []

    for py_file in sorted(src_dir.glob("*.py")):  # only top-level files
        if py_file.name.startswith("_"):
            continue
        try:
            source = py_file.read_text(errors="replace")
            lines = source.splitlines()
        except OSError:
            continue

        # Parse AST for docstrings, functions, classes
        description = ""
        key_functions = []
        classes = []
        try:
            tree = ast.parse(source)
            # Module docstring
            if (
                tree.body
                and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, (ast.Constant, ast.Str))
            ):
                doc = tree.body[0].value.s if isinstance(tree.body[0].value, ast.Str) else tree.body[0].value.value
                description = doc.strip().splitlines()[0][:120] if doc else ""

            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                    key_functions.append(node.name)
                elif isinstance(node, ast.AsyncFunctionDef) and not node.name.startswith("_"):
                    key_functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
        except SyntaxError:
            pass

        # Fallback: first comment line
        if not description:
            for line in lines[:5]:
                stripped = line.strip()
                if stripped.startswith("#"):
                    description = stripped.lstrip("#").strip()
                    break

        inventory.append(
            {
                "file": py_file.name,
                "description": description,
                "key_functions": key_functions[:10],  # top 10
                "classes": classes,
                "size_lines": len(lines),
            }
        )

    return inventory


# ---------------------------------------------------------------------------
# Extraction: Docker services
# ---------------------------------------------------------------------------

def extract_docker_services(project_dir: Path) -> list[dict]:
    """
    Pure-Python docker-compose.yml parser (no PyYAML).
    Returns list of {name, image, ports, volumes, environment}.
    """
    compose_file = project_dir / "docker-compose.yml"
    if not compose_file.exists():
        compose_file = project_dir / "docker-compose.yaml"
    if not compose_file.exists():
        return []

    try:
        lines = compose_file.read_text(errors="replace").splitlines()
    except OSError:
        return []

    services = []
    current_service = None
    in_services = False
    in_ports = False
    in_volumes = False
    in_environment = False
    service_indent = 2

    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        if stripped == "services:":
            in_services = True
            continue

        if not in_services:
            continue

        # Top-level sections after services:
        if indent == 0 and stripped and not stripped.startswith("#"):
            in_services = False
            continue

        # Service name detection (indent == service_indent, no leading -)
        if indent == service_indent and stripped and not stripped.startswith("-") and stripped.endswith(":"):
            if current_service:
                services.append(current_service)
            current_service = {
                "name": stripped.rstrip(":"),
                "image": "",
                "ports": [],
                "volumes": [],
                "environment": [],
            }
            in_ports = in_volumes = in_environment = False
            continue

        if current_service is None:
            continue

        # image:
        if stripped.startswith("image:"):
            current_service["image"] = stripped.split(":", 1)[1].strip()
            in_ports = in_volumes = in_environment = False
            continue

        # build: (record as image=<build>)
        if stripped.startswith("build:"):
            if not current_service["image"]:
                current_service["image"] = "<build>"
            in_ports = in_volumes = in_environment = False
            continue

        # ports:
        if stripped == "ports:":
            in_ports = True
            in_volumes = in_environment = False
            continue

        # volumes:
        if stripped == "volumes:":
            in_volumes = True
            in_ports = in_environment = False
            continue

        # environment:
        if stripped == "environment:":
            in_environment = True
            in_ports = in_volumes = False
            continue

        # Sub-key resets
        if stripped.endswith(":") and not stripped.startswith("-"):
            in_ports = in_volumes = in_environment = False

        # Collect list items
        if stripped.startswith("- "):
            value = stripped[2:].strip()
            if in_ports:
                current_service["ports"].append(value)
            elif in_volumes:
                current_service["volumes"].append(value)
            elif in_environment:
                current_service["environment"].append(value.split("=")[0])

    if current_service:
        services.append(current_service)

    return services


# ---------------------------------------------------------------------------
# Marker update
# ---------------------------------------------------------------------------

def update_marker(
    filepath: Path, marker: str, new_content: str, dry_run: bool = False, verbose: bool = False
) -> bool:
    """
    Replace content between <!-- AUTO:MARKER_BEGIN --> and <!-- AUTO:MARKER_END -->
    where MARKER matches the marker argument. Returns True if file was updated.
    """
    begin_tag = f"<!-- AUTO:{marker}_BEGIN -->"
    end_tag = f"<!-- AUTO:{marker}_END -->"

    try:
        text = filepath.read_text(errors="replace")
    except OSError:
        return False

    if begin_tag not in text or end_tag not in text:
        if verbose:
            print(f"    [skip] {filepath.name} — marker {marker} not found")
        return False

    pattern = re.compile(
        re.escape(begin_tag) + r".*?" + re.escape(end_tag),
        re.DOTALL,
    )

    replacement = f"{begin_tag}\n{new_content}\n{end_tag}"
    new_text, count = pattern.subn(replacement, text)

    if count == 0:
        return False

    if dry_run:
        if verbose:
            print(f"    [dry-run] would update {filepath} marker={marker}")
        return True

    filepath.write_text(new_text, encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def write_api_endpoints(
    dev_docs_dir: Path,
    routes: list[dict],
    project_name: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Fill AUTO:ROUTES marker in api/endpoints.md. Returns route count written."""
    endpoints_file = dev_docs_dir / "api" / "endpoints.md"
    if not endpoints_file.exists():
        return 0

    # Group by tag (first path segment)
    groups: dict[str, list] = {}
    for r in routes:
        parts = r["path"].strip("/").split("/")
        tag = parts[0] if parts else "root"
        groups.setdefault(tag, []).append(r)

    lines = [f"*Auto-generated {datetime.now().strftime('%Y-%m-%d')} — {len(routes)} routes*", ""]
    lines.append("| Method | Path | Function | Description |")
    lines.append("|--------|------|----------|-------------|")
    for r in routes:
        desc = r["description"] or r["func"]
        lines.append(f"| `{r['method']}` | `{r['path']}` | `{r['func']}` | {desc} |")

    lines.append("")
    lines.append("### Grouped by resource")
    for tag, tag_routes in sorted(groups.items()):
        lines.append(f"\n#### /{tag}")
        for r in tag_routes:
            lines.append(f"- `{r['method']} {r['path']}`  — {r['func']}")

    content = "\n".join(lines)
    updated = update_marker(endpoints_file, "ROUTES", content, dry_run=dry_run, verbose=verbose)
    if verbose and updated:
        print(f"  ✓ api/endpoints.md — {len(routes)} routes")
    return len(routes) if updated else 0


def write_scripts_reference(
    dev_docs_dir: Path,
    modules: list[dict],
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Fill AUTO:MODULES marker in architecture/scripts_reference.md."""
    ref_file = dev_docs_dir / "architecture" / "scripts_reference.md"
    if not ref_file.exists():
        return 0

    lines = [f"*Auto-generated {datetime.now().strftime('%Y-%m-%d')} — {len(modules)} modules*", ""]
    lines.append("| File | Lines | Description | Key functions |")
    lines.append("|------|-------|-------------|---------------|")
    for m in modules:
        funcs = ", ".join(f"`{f}()`" for f in m["key_functions"][:5])
        desc = m["description"] or "—"
        lines.append(f"| `{m['file']}` | {m['size_lines']} | {desc} | {funcs} |")

    content = "\n".join(lines)
    updated = update_marker(ref_file, "MODULES", content, dry_run=dry_run, verbose=verbose)
    if verbose and updated:
        print(f"  ✓ architecture/scripts_reference.md — {len(modules)} modules")
    return len(modules) if updated else 0


def write_database_schema(
    dev_docs_dir: Path,
    tables: list[dict],
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Fill AUTO:TABLES marker in architecture/database_schema.md."""
    schema_file = dev_docs_dir / "architecture" / "database_schema.md"
    if not schema_file.exists():
        return 0

    lines = [f"*Auto-generated {datetime.now().strftime('%Y-%m-%d')} — {len(tables)} tables*", ""]
    for t in tables:
        lines.append(f"### `{t['name']}`")
        lines.append(f"*Source: `{t['source']}`*")
        if t["columns"]:
            lines.append("")
            lines.append("| Column | Notes |")
            lines.append("|--------|-------|")
            for col in t["columns"]:
                lines.append(f"| `{col}` | [TODO] |")
        lines.append("")

    # Mermaid ERD stub
    lines.append("```mermaid")
    lines.append("erDiagram")
    for t in tables:
        lines.append(f"    {t['name'].upper()} {{")
        for col in t["columns"][:6]:
            lines.append(f"        string {col}")
        lines.append("    }")
    lines.append("```")

    content = "\n".join(lines)
    updated = update_marker(schema_file, "TABLES", content, dry_run=dry_run, verbose=verbose)
    if verbose and updated:
        print(f"  ✓ architecture/database_schema.md — {len(tables)} tables")
    return len(tables) if updated else 0


def write_docker_services(
    dev_docs_dir: Path,
    services: list[dict],
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """Fill AUTO:DOCKER marker in architecture/macro_architecture.md."""
    arch_file = dev_docs_dir / "architecture" / "macro_architecture.md"
    if not arch_file.exists():
        return 0

    lines = [f"*Auto-generated {datetime.now().strftime('%Y-%m-%d')} — {len(services)} services*", ""]
    lines.append("| Service | Image | Ports | Volumes |")
    lines.append("|---------|-------|-------|---------|")
    for s in services:
        ports = ", ".join(s["ports"][:3]) or "—"
        vols = ", ".join(s["volumes"][:3]) or "—"
        lines.append(f"| `{s['name']}` | `{s['image'] or '—'}` | {ports} | {vols} |")

    content = "\n".join(lines)
    updated = update_marker(arch_file, "DOCKER", content, dry_run=dry_run, verbose=verbose)
    if verbose and updated:
        print(f"  ✓ architecture/macro_architecture.md — {len(services)} services")
    return len(services) if updated else 0


def update_roadmap_stats(
    dev_docs_dir: Path,
    modules: list[dict],
    routes: list[dict],
    tables: list[dict],
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Fill AUTO:STATS marker in ROADMAP.md with a project snapshot."""
    roadmap_file = dev_docs_dir / "ROADMAP.md"
    if not roadmap_file.exists():
        return False

    lines = [
        f"*Auto-generated {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Python modules | {len(modules)} |",
        f"| API endpoints  | {len(routes)} |",
        f"| DB tables      | {len(tables)} |",
    ]
    content = "\n".join(lines)
    updated = update_marker(roadmap_file, "STATS", content, dry_run=dry_run, verbose=verbose)
    if verbose and updated:
        print(f"  ✓ ROADMAP.md — stats updated")
    return updated


# ---------------------------------------------------------------------------
# TODO counter
# ---------------------------------------------------------------------------

def write_gantt_chart(
    project_dir: Path,
    dev_docs_dir: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """
    Parse ROADMAP.md bricks and update the AUTO:GANTT_STATS marker in
    tools/gantt_project.md with a status summary table.

    Returns True if gantt_project.md was updated (or would be in dry-run).
    """
    roadmap_file = dev_docs_dir / "ROADMAP.md"
    gantt_file = project_dir / "tools" / "gantt_project.md"

    if not roadmap_file.exists():
        if verbose:
            print("  [skip] ROADMAP.md not found — cannot generate GANTT stats")
        return False
    if not gantt_file.exists():
        if verbose:
            print("  [skip] tools/gantt_project.md not found — create it first")
        return False

    text = roadmap_file.read_text(errors="replace")

    # Count bricks by status section
    # Sections: "Active P1 items", "Architecture validated", "Blocked", "## Completed"
    active: list[str] = []
    planned: list[str] = []
    blocked: list[str] = []
    completed: list[str] = []

    in_sprint = False
    in_completed = False
    brick_line = re.compile(r"-\s+Brick\s+([\w]+):\s+(.+)")

    for line in text.splitlines():
        stripped = line.strip()
        if "## Current Sprint" in stripped:
            in_sprint = True
            in_completed = False
        elif stripped.startswith("## ") and "Current Sprint" not in stripped:
            if "Completed" in stripped or "Done" in stripped:
                in_completed = True
            in_sprint = False if "Completed" not in stripped and "Done" not in stripped else in_sprint

        m = brick_line.match(stripped)
        if not m:
            continue
        num, desc = m.group(1), m.group(2)[:60]

        if in_completed:
            completed.append(f"Brick {num}")
        elif "Blocked" in text[max(0, text.find(line) - 200):text.find(line)]:
            blocked.append(f"Brick {num}")
        elif in_sprint:
            # Distinguish active P1 vs planned by checking surrounding context
            ctx_start = max(0, text.find(line) - 500)
            ctx = text[ctx_start:text.find(line)]
            if "Blocked / waiting" in ctx:
                blocked.append(f"Brick {num}")
            elif "Active P1" in ctx:
                active.append(f"Brick {num}")
            else:
                planned.append(f"Brick {num}")

    total = len(active) + len(planned) + len(blocked) + len(completed)
    lines = [
        f"*Auto-generated {datetime.now().strftime('%Y-%m-%d')} from ROADMAP.md*",
        "",
        f"| Status | Count | Bricks |",
        f"|--------|-------|--------|",
        f"| Active P1 | {len(active)} | {', '.join(active) or '—'} |",
        f"| Planned | {len(planned)} | {', '.join(planned) or '—'} |",
        f"| Blocked | {len(blocked)} | {', '.join(blocked) or '—'} |",
        f"| Completed | {len(completed)} | {', '.join(completed) if completed else '—'} |",
        f"| **Total** | **{total}** | |",
    ]
    content = "\n".join(lines)
    updated = update_marker(gantt_file, "GANTT_STATS", content, dry_run=dry_run, verbose=verbose)
    if verbose and updated:
        print(f"  ✓ tools/gantt_project.md — {total} bricks ({len(active)} active, {len(planned)} planned, {len(blocked)} blocked, {len(completed)} done)")
    return updated


def count_todos(dev_docs_dir: Path) -> dict[str, int]:
    """Count [TODO] occurrences in each dev-doc file."""
    result = {}
    for md_file in sorted(dev_docs_dir.rglob("*.md")):
        if "work-in-progress" in md_file.parts:
            continue
        try:
            text = md_file.read_text(errors="replace")
        except OSError:
            continue
        count = text.count("[TODO]")
        if count > 0:
            rel = str(md_file.relative_to(dev_docs_dir))
            result[rel] = count
    return result


# ---------------------------------------------------------------------------
# GANTT regeneration (--gantt)
# ---------------------------------------------------------------------------

# Status emoji → human label mapping (mirrors BRICKS.md Legend)
_STATUS_LABEL = {
    "✅": "Done",
    "🟡": "WIP",
    "🔵": "Unblocked",
    "⚪": "Blocked-upstream",
    "❌": "Hardware-blocked",
}


def _parse_bricks_summary(bricks_path: Path) -> list[dict]:
    """Extract brick rows from BRICKS.md Summary Table.

    Each row matches the pattern :
        | **<name>** | <title> | <track> | <status> | <prio> | <deps> | <close> | <effort> |

    Returns a list of dicts with keys name/title/track/status/effort.
    Robust to ✅ 2026-04-23 (status+date inline), 🟡 DRAFT, 🔵, ⚪, ❌.
    """
    if not bricks_path.exists():
        return []

    rows: list[dict] = []
    in_table = False
    for line in bricks_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Summary Table"):
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table:
            continue
        if not line.startswith("| **"):
            continue
        # Parse pipe-separated row
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 5:
            continue
        name = cells[0].strip("* ")
        title = cells[1]
        track = cells[2]
        status_cell = cells[3]
        # Extract first emoji from status cell (may also contain " 2026-04-23" inline)
        status = "?"
        for emoji in _STATUS_LABEL:
            if emoji in status_cell:
                status = emoji
                break
        effort = cells[-1] if len(cells) >= 8 else ""
        rows.append({
            "name": name,
            "title": title,
            "track": track,
            "status": status,
            "effort": effort,
        })
    return rows


def _render_gantt_stats(rows: list[dict]) -> str:
    """Render the AUTO:GANTT_STATS body (Markdown tables) from parsed rows."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Per-status totals
    by_status: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1

    # Per-track × status matrix
    tracks: dict[str, dict[str, int]] = {}
    for r in rows:
        t = r["track"]
        tracks.setdefault(t, {})
        tracks[t][r["status"]] = tracks[t].get(r["status"], 0) + 1

    lines = [f"*Updated {today} from `BRICKS.md` Summary Table*", ""]
    lines.append("| Status | Count | Label |")
    lines.append("|--------|-------|-------|")
    for emoji, label in _STATUS_LABEL.items():
        n = by_status.get(emoji, 0)
        lines.append(f"| {emoji} {label} | {n} | — |")
    total = sum(by_status.values())
    lines.append(f"| **Total** | **{total}** | — |")
    lines.append("")

    lines.append("Per-track distribution :")
    lines.append("")
    lines.append("| Track | ✅ Done | 🟡 WIP | 🔵 Unblocked | ⚪/❌ Blocked | Total |")
    lines.append("|-------|---------|--------|--------------|---------------|-------|")
    for track in sorted(tracks.keys()):
        st = tracks[track]
        done = st.get("✅", 0)
        wip = st.get("🟡", 0)
        unb = st.get("🔵", 0)
        blk = st.get("⚪", 0) + st.get("❌", 0)
        tot = done + wip + unb + blk
        lines.append(f"| `{track}` | {done} | {wip} | {unb} | {blk} | {tot} |")
    return "\n".join(lines)


def regenerate_gantt_stats(dev_docs_dir: Path, *, dry_run: bool, verbose: bool) -> int:
    """Rewrite the `<!-- AUTO:GANTT_STATS_BEGIN --> ... <!-- END -->` block
    in `GANTT.md` using the current BRICKS.md Summary Table. Exit 0 on success.
    """
    bricks_path = dev_docs_dir / "BRICKS.md"
    gantt_path = dev_docs_dir / "GANTT.md"

    if not bricks_path.exists():
        print(f"ERROR: {bricks_path} not found — cannot regenerate gantt stats", file=sys.stderr)
        return 1
    if not gantt_path.exists():
        print(f"ERROR: {gantt_path} not found — run setup-claude-code.sh to scaffold it", file=sys.stderr)
        return 1

    rows = _parse_bricks_summary(bricks_path)
    if not rows:
        print(f"WARNING: parsed 0 brick rows from {bricks_path} — markers may be malformed", file=sys.stderr)
        return 1

    print(f"Parsed {len(rows)} bricks from {bricks_path.name}")
    if verbose:
        for r in rows:
            print(f"  {r['status']} {r['name']:35s} track={r['track']:<12s} effort={r['effort']}")

    content = gantt_path.read_text(encoding="utf-8")
    begin_marker = "<!-- AUTO:GANTT_STATS_BEGIN -->"
    end_marker = "<!-- AUTO:GANTT_STATS_END -->"
    if begin_marker not in content or end_marker not in content:
        print(f"ERROR: markers {begin_marker} / {end_marker} not both found in {gantt_path}", file=sys.stderr)
        return 1

    stats_body = _render_gantt_stats(rows)
    before, _, rest = content.partition(begin_marker)
    _, _, after = rest.partition(end_marker)
    new_content = f"{before}{begin_marker}\n{stats_body}\n{end_marker}{after}"

    if dry_run:
        print(f"[dry-run] would rewrite GANTT_STATS block in {gantt_path}")
        return 0

    gantt_path.write_text(new_content, encoding="utf-8")
    print(f"✅ GANTT_STATS block updated in {gantt_path}")
    return 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fill AUTO:MARKER sections in dev-doc templates from code analysis."
    )
    parser.add_argument(
        "--project-dir",
        default=".",
        help="Project root directory (default: current dir)",
    )
    parser.add_argument(
        "--src-dir",
        default=None,
        help="Source directory containing .py files (default: auto-detect)",
    )
    parser.add_argument(
        "--dev-docs-dir",
        default=None,
        help="Dev-docs directory (default: <project-dir>/.claude/dev-docs)",
    )
    parser.add_argument(
        "--framework",
        choices=["fastapi", "flask", "django", "generic"],
        default=None,
        help="Force framework (default: auto-detect)",
    )
    parser.add_argument(
        "--db",
        choices=["sqlite", "postgres", "mysql", "none"],
        default=None,
        help="Force database type (default: auto-detect)",
    )
    parser.add_argument(
        "--has-ml",
        action="store_true",
        default=None,
        help="Force ML detection on",
    )
    parser.add_argument(
        "--has-docker",
        action="store_true",
        default=None,
        help="Force Docker detection on",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyse and report without writing any file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show per-file update messages",
    )
    parser.add_argument(
        "--project-name",
        default=None,
        help="Project name for display (default: project-dir basename)",
    )
    parser.add_argument(
        "--gantt",
        action="store_true",
        help="Regenerate the AUTO:GANTT_STATS block in .claude/dev-docs/GANTT.md "
             "from BRICKS.md Summary Table. Leaves the Mermaid chart body untouched.",
    )
    args = parser.parse_args()

    project_dir = Path(args.project_dir).resolve()
    if not project_dir.is_dir():
        print(f"ERROR: --project-dir '{project_dir}' is not a directory", file=sys.stderr)
        return 1

    # Auto-detect src_dir
    if args.src_dir:
        src_dir = (project_dir / args.src_dir).resolve()
    else:
        # Common conventions
        for candidate in ["src/Application", "src/app", "src", "app", "."]:
            candidate_path = project_dir / candidate
            if candidate_path.is_dir() and any(candidate_path.glob("*.py")):
                src_dir = candidate_path.resolve()
                break
        else:
            src_dir = project_dir

    dev_docs_dir = Path(args.dev_docs_dir).resolve() if args.dev_docs_dir else project_dir / ".claude" / "dev-docs"

    project_name = args.project_name or project_dir.name

    # Detection
    framework = args.framework or detect_framework(src_dir)
    db = args.db or detect_db(src_dir)
    has_ml = args.has_ml if args.has_ml is not None else detect_ml(src_dir)
    has_docker = args.has_docker if args.has_docker is not None else detect_docker(project_dir)

    # Header
    print(f"\ngenerate-dev-docs — {project_name}")
    print(f"  Project dir : {project_dir}")
    print(f"  Source dir  : {src_dir}")
    print(f"  Dev-docs dir: {dev_docs_dir}")
    print(f"  Framework   : {framework}")
    print(f"  Database    : {db}")
    print(f"  ML detected : {'yes' if has_ml else 'no'}")
    print(f"  Docker      : {'yes' if has_docker else 'no'}")
    if args.dry_run:
        print("  Mode        : DRY RUN (no files written)")
    print()

    if not dev_docs_dir.exists():
        print(
            f"WARNING: dev-docs dir '{dev_docs_dir}' does not exist.\n"
            "Run setup-claude-code.sh first to create templates, then re-run this script.",
            file=sys.stderr,
        )
        return 1

    # ── Gantt-only mode : update AUTO:GANTT_STATS block from BRICKS.md ──
    if args.gantt:
        return regenerate_gantt_stats(dev_docs_dir, dry_run=args.dry_run, verbose=args.verbose)

    # Extraction
    print("Extracting...")
    routes: list[dict] = []
    if framework == "fastapi":
        routes = extract_fastapi_routes(src_dir)
    elif framework == "flask":
        routes = extract_flask_routes(src_dir)
    print(f"  Routes  : {len(routes)}")

    tables = extract_sql_tables(src_dir)
    print(f"  Tables  : {len(tables)}")

    modules = build_module_inventory(src_dir)
    print(f"  Modules : {len(modules)}")

    services: list[dict] = []
    if has_docker:
        services = extract_docker_services(project_dir)
    print(f"  Services: {len(services)}")
    print()

    # Write / update
    print("Updating dev-docs...")
    updated_count = 0

    if routes and framework != "generic":
        n = write_api_endpoints(
            dev_docs_dir, routes, project_name, dry_run=args.dry_run, verbose=True
        )
        if n:
            updated_count += 1

    if modules:
        n = write_scripts_reference(
            dev_docs_dir, modules, dry_run=args.dry_run, verbose=True
        )
        if n:
            updated_count += 1

    if tables:
        n = write_database_schema(
            dev_docs_dir, tables, dry_run=args.dry_run, verbose=True
        )
        if n:
            updated_count += 1

    if services:
        n = write_docker_services(
            dev_docs_dir, services, dry_run=args.dry_run, verbose=True
        )
        if n:
            updated_count += 1

    update_roadmap_stats(
        dev_docs_dir, modules, routes, tables, dry_run=args.dry_run, verbose=True
    )

    if args.gantt:
        write_gantt_chart(project_dir, dev_docs_dir, dry_run=args.dry_run, verbose=True)

    print()

    # TODO report
    todos = count_todos(dev_docs_dir)
    if todos:
        total_todos = sum(todos.values())
        print(f"Remaining [TODO] — {total_todos} items require Layer 3 (dev-docs-architect agent):")
        max_path = max(len(p) for p in todos)
        for path, count in sorted(todos.items(), key=lambda x: -x[1]):
            print(f"  {path:<{max_path}}   {count} TODO(s)")
        print()
        print("Next step: run /dev-docs-init to let the dev-docs-architect agent fill the rest.")
    else:
        print("All [TODO] markers resolved — dev-docs are fully populated.")
        print("Optional: run /dev-docs-init for Mermaid diagram verification.")

    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
