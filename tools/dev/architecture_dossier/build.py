#!/usr/bin/env python3
"""Rend le dossier en PDF : mermaid -> SVG -> HTML -> WeasyPrint."""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SVG = HERE / "svg"
SVG.mkdir(exist_ok=True)

# Palette du dépôt, déjà validée (ΔE) pour la figure de l'accueil.
BLUE, ORANGE, AQUA, AMBER = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, MUTED, RULE = "#1a1a19", "#6b6b68", "#d8d8d4"

MERMAID_CONF = HERE / "mermaid.json"
MERMAID_CONF.write_text('''{
  "theme": "base",
  "themeVariables": {
    "fontFamily": "Helvetica, Arial, sans-serif",
    "fontSize": "16px",
    "primaryColor": "#eef3fa",
    "primaryTextColor": "#1a1a19",
    "primaryBorderColor": "#2a78d6",
    "lineColor": "#6b6b68",
    "secondaryColor": "#eaf6f1",
    "tertiaryColor": "#fdf3e3",
    "clusterBkg": "#fbfbf9",
    "clusterBorder": "#d8d8d4"
  },
  "htmlLabels": false,
  "flowchart": {"curve": "basis", "htmlLabels": false, "padding": 10, "useMaxWidth": true},
  "sequence": {"actorMargin": 40}
}''', encoding="utf-8")


def render(code: str) -> str:
    """Rend un bloc mermaid en SVG inline, avec cache par empreinte."""
    key = hashlib.sha256(code.encode()).hexdigest()[:16]
    out = SVG / f"{key}.svg"
    if not out.exists():
        src = SVG / f"{key}.mmd"
        src.write_text(code, encoding="utf-8")
        r = subprocess.run(
            ["mmdc", "-i", str(src), "-o", str(out), "-b", "transparent",
             "-c", str(MERMAID_CONF), "-w", "980"],
            capture_output=True, text=True)
        if not out.exists():
            print("MERMAID KO:", r.stderr[-400:], file=sys.stderr)
            print("---- bloc ----\n", code, file=sys.stderr)
            raise SystemExit(1)
    svg = out.read_text(encoding="utf-8")
    # WeasyPrint veut une largeur exploitable : on retire le width:100% et on garde
    # le viewBox pour que le SVG se mette à l'échelle de la colonne.
    svg = re.sub(r'width="100%"', '', svg, count=1)
    svg = re.sub(r'style="max-width:[^"]*"', 'style="width:100%;height:auto"', svg, count=1)
    return svg


def expand(html: str) -> str:
    """Remplace chaque <mermaid>…</mermaid> par son SVG."""
    def _one(m):
        return f'<div class="fig">{render(m.group(1).strip())}</div>'
    return re.sub(r"<mermaid>(.*?)</mermaid>", _one, html, flags=re.S)
