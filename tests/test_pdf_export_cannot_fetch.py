"""Guard — the PDF renderer fetches nothing but inline data.

Error class `server-side-render-fetches-tenant-chosen-urls`.

WeasyPrint's default `url_fetcher` registers http/https/ftp/**file** handlers with
`allowed_protocols=None`. `HTML(string=…)` with no fetcher therefore turns any
`<img src>` surviving into the report into a request made BY THE SERVER.

A free-plan tenant had two ways to plant one, both fully theirs:
  * upload a CSV named `<img src="http://attacker/">_20251129.csv` — `parse_timeline`
    takes the song name from the filename STEM and, unlike `parse_songs_global`,
    never calls `canonical_song()`;
  * rename their own Meta campaign, which `meta_ads_api_daily` writes verbatim.

Then Export PDF. `http://` reached 127.0.0.1 and the compose network from inside the
container (blind SSRF, redirects followed); `file:///…` embedded an arbitrary
server-side image into the PDF they downloaded. An admin generating any tenant's
report fired it in the admin's session.

Two controls, because either alone is one mistake from failing: escape the value,
and refuse the fetch.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REPORT = ROOT / "src/dashboard/utils/pdf_exporter/_report.py"


def test_the_renderer_declares_a_url_fetcher() -> None:
    tree = ast.parse(REPORT.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "HTML":
            kw = {k.arg for k in node.keywords}
            assert "url_fetcher" in kw, (
                f"line {node.lineno}: HTML(string=…) with no url_fetcher — WeasyPrint "
                f"will fetch http/https/ftp/file for any src in the document"
            )
            return
    pytest.fail("no HTML(...) call found — has the renderer moved?")


def test_the_fetcher_allows_only_data_uris() -> None:
    from src.dashboard.utils.pdf_exporter._report import _no_remote_resources

    for url in ("http://127.0.0.1:8080/", "https://attacker.tld/a",
                "file:///etc/passwd", "ftp://x/y",
                "//attacker.tld/a", "HTTP://attacker.tld"):
        with pytest.raises(Exception):
            _no_remote_resources(url)


def test_a_tenant_song_name_cannot_carry_markup() -> None:
    from src.dashboard.utils.pdf_exporter._renderers import _esc

    out = _esc('<img src="http://attacker.tld/a">')
    assert "<img" not in out
    assert "&lt;img" in out


def test_every_tenant_controlled_value_is_escaped() -> None:
    """AST: the specific sinks the audit named, pinned so they cannot silently revert.

    Targeted, not blanket. This file also interpolates markup it built itself —
    badges, probability bars, row blocks — and escaping those breaks the render (I
    tried; the golden snapshot caught it). The rule is about the VALUES a tenant can
    set, not about every `{}` in the file.
    """
    src = (ROOT / "src/dashboard/utils/pdf_exporter/_renderers.py").read_text(encoding="utf-8")
    tree = ast.parse(src)

    # Expressions that carry a value a tenant chose: a song name (CSV filename stem)
    # or a campaign name (their own Meta account).
    TENANT_EXPRS = {"s['song']", "s[0]", "_trunc(c, 46)"}
    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        markup = "<" in "".join(v.value for v in node.values if isinstance(v, ast.Constant))
        if not markup:
            continue
        for v in node.values:
            if not isinstance(v, ast.FormattedValue):
                continue
            expr = ast.unparse(v.value)
            if expr in TENANT_EXPRS:
                offenders.append((node.lineno, expr))
    assert not offenders, (
        f"tenant-controlled value interpolated into HTML unescaped: {offenders}. "
        f"These reach a server-side render; wrap them in _esc()."
    )


def test_the_escape_sinks_still_exist() -> None:
    """If the renderers stop interpolating these at all, the test above goes vacuous."""
    src = (ROOT / "src/dashboard/utils/pdf_exporter/_renderers.py").read_text(encoding="utf-8")
    for expr in ("_esc(s['song'])", "_esc(s[0])", "_esc(_trunc(c, 46))"):
        assert expr in src, f"{expr} is gone — the guard above now protects nothing"
