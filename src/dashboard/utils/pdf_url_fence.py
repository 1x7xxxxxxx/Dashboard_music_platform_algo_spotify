"""The one `url_fetcher` every WeasyPrint render in this repo passes.

Type: Utility
Uses: weasyprint.urls.URLFetcher (≥ 70) or default_url_fetcher (< 70)
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


def _legacy_fence(url: str, timeout: int = 10, ssl_context=None):
    """WeasyPrint < 70: a plain function, `data:` served by `default_url_fetcher`."""
    if url.startswith("data:"):
        from weasyprint.urls import default_url_fetcher

        return default_url_fetcher(url, timeout=timeout, ssl_context=ssl_context)
    raise ValueError(f"blocked non-data resource in PDF render: {url[:60]}")


def _build_fence():
    """The fence for the INSTALLED WeasyPrint.

    ⚠️ WeasyPrint 70 (R267, 2026-09-28, upgraded for PYSEC-2026-3940) removed
    `default_url_fetcher` and calls `url_fetcher._fail_on_errors` when a fetch raises: a
    plain function made EVERY blocked resource crash the render with an AttributeError
    instead of dropping it. The requirement files pin `weasyprint>=62.0`, so the next image
    build would have met it in production. From 70 on, the fence is a `URLFetcher` whose
    only allowed protocol is `data` — the library's own gate, raising ValueError on the rest.
    """
    try:
        from weasyprint.urls import URLFetcher
    except ImportError:
        return _legacy_fence

    class _DataOnly(URLFetcher):
        def __init__(self):
            super().__init__(allowed_protocols={"data"}, fail_on_errors=False)

    return _DataOnly()


class _LazyFence:
    """Built on first use: importing this module must not import WeasyPrint."""

    _fence = None

    def __call__(self, url, *args, **kwargs):
        return self._get()(url, *args, **kwargs)

    def __getattr__(self, name):          # `_fail_on_errors`, `fetch`… for WeasyPrint 70
        return getattr(self._get(), name)

    def _get(self):
        if _LazyFence._fence is None:
            _LazyFence._fence = _build_fence()
        return _LazyFence._fence


no_remote_resources = _LazyFence()
