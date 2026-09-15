"""La marque — le wordmark streaMLytics, rendu en data-URI.

Type: Utility
Uses: streamlit (cache), src/dashboard/assets/*.svg
Triggers: src/dashboard/app.py (barre latérale), src/dashboard/auth.py (page de connexion)
Persists in: nothing

Pourquoi ce module existe (2026-09-16)
--------------------------------------
`logo_html` vivait dans `src/dashboard/utils/__init__.py` et y portait un
`@st.cache_data`. Un décorateur est évalué À L'IMPORT : cette seule ligne forçait
`import streamlit` en tête du module, et donc **5,30 s** (dont 5,19 s de Streamlit)
pour quiconque voulait seulement `get_db_connection()` — c'est-à-dire 50 fichiers de
tests, l'API (`src/api/deps.py`), et tout script qui touche la base par cette porte.

Deux sorties étaient possibles : remplacer le cache par `functools.lru_cache`, ou
déplacer la fonction. La revue `code-critic` a tranché pour le déplacement, et la
raison vaut d'être écrite : `lru_cache` aurait CHANGÉ la sémantique — le bouton
« Clear cache » de Streamlit ne l'atteint pas — pour un bénéfice nul, les deux caches
se comportant identiquement sur une fonction pure de trois scalaires. Un déplacement
coûte le même effort et ne change rien d'observable.

Ce module garde donc `import streamlit` en tête, et c'est sans conséquence : rien de
ce qui a besoin de la base n'a besoin de la marque.
"""
from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


@st.cache_data
def logo_html(variant: str = "dark", max_width: int = 220, center: bool = False) -> str:
    """streaMLytics wordmark as a base64 data-URI <img> (SVG renders reliably).

    variant: 'dark' (dark text, light bg) | 'light' (white text, dark bg).
    """
    name = {
        "light": "logo_horizontal_light.svg",
        "dark": "logo_horizontal_dark.svg",
        "adaptive": "logo_horizontal_adaptive.svg",
    }.get(variant, "logo_horizontal_adaptive.svg")
    try:
        b64 = base64.b64encode((_ASSETS_DIR / name).read_bytes()).decode("ascii")
    except Exception:  # noqa: BLE001 — une marque absente ne fait pas tomber une page
        return ""
    img = (f'<img src="data:image/svg+xml;base64,{b64}" '
           f'style="width:100%;max-width:{max_width}px;" alt="streaMLytics"/>')
    if center:
        return f'<div style="text-align:center;margin:8px 0 18px 0;">{img}</div>'
    return img
