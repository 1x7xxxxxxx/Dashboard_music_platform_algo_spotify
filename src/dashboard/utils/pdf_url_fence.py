"""The one `url_fetcher` every WeasyPrint render in this repo passes.

Type: Utility
Uses: weasyprint.urls.default_url_fetcher
Triggers: every `HTML(string=…).write_pdf()` in `src/`
Depends on: weasyprint (optional at import time — the import is lazy)
Persists in: nothing

Pourquoi un module à lui seul
-----------------------------
La clôture vivait dans `pdf_exporter/_report.py`, **passée à UN appel sur trois**.
Les deux autres — `guides/guide_pdf.py` et `utils/guide_assets.py` — rendaient sans
elle. Aucun des deux ne touche à de la donnée de locataire aujourd'hui, donc il n'y
avait pas de défaut vivant ; il y avait une clôture qui était la propriété d'un SITE
au lieu d'être la propriété du GESTE, et un site de plus la perdait.

⚠️ `pdf_from_html` est le cas qui décide : elle rend un HTML **quelconque**, elle
n'a aucun appelant en production, et elle est maintenue en vie par un test qui
vérifie qu'elle est mise en cache. Une fonction sans clôture, sans appelant et avec
un test : c'est exactement la forme qui sera branchée un jour sans qu'on relise sa
sécurité.

Ce que ça ne coûte rien
-----------------------
Les trois rendus embarquent leurs images en `data:` — les captures du guide font
~1,6 Mo de base64 (`guide_pdf.py:136-138`), et les figures du rapport sont produites
en base64 par les renderers. La clôture laisse passer `data:` et rien d'autre.

---
rex: []
---
"""
from __future__ import annotations


def no_remote_resources(url: str, timeout: int = 10, ssl_context=None):
    """url_fetcher that serves nothing but inline `data:` URIs.

    Anything else raises, and WeasyPrint drops the element rather than fetching it.
    """
    if url.startswith("data:"):
        from weasyprint.urls import default_url_fetcher

        return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)
    raise ValueError(f"blocked non-data resource in PDF render: {url[:60]}")
