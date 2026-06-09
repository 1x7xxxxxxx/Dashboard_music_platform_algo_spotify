"""Static onboarding-guide PDF — second renderer of csv_guides (see csv_guides).

Type: Sub
Uses: weasyprint, base64, src.dashboard.content.csv_guides
Depends on: assets/csv_guides/*.png (optional — missing images degrade gracefully)
Persists in: docs/guides/onboarding_guide.pdf

Dedicated to the instructional guide (artist-independent, image-heavy) — kept
separate from pdf_exporter.py, which is coupled to per-artist DB data. Build once
with `python -m src.dashboard.guides.guide_pdf` and commit the output; the welcome
email attaches it.
"""
import base64
import html
import os
import re
from pathlib import Path

from src.dashboard.content.csv_guides import (
    CSV_GUIDES, PlatformGuide, screenshot_path,
)
from src.dashboard.content.credential_guides import (
    CREDENTIAL_GUIDES, PlatformCred,
)
from src.dashboard.content.credential_guides import screenshot_path as cred_screenshot_path

# WeasyPrint's base font has no emoji glyphs (they render as tofu), so strip them
# from the PDF. The Streamlit renderer keeps emojis (its fonts support them).
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF✀-➿️⭐⬆]+"
)


def _strip_emoji(text: str) -> str:
    return re.sub(r"\s{2,}", " ", _EMOJI_RE.sub("", text)).strip()


_BARE_URL_RE = re.compile(r'(?<![">=/])\bhttps?://[^\s<)"]+')


def _inline_md(text: str) -> str:
    """Escape HTML then convert inline markdown (links, `code`, bare URLs, **bold**).

    Order matters: markdown links → code spans → bare URLs → bold. Converting code
    spans before bare URLs keeps backtick-wrapped throwaway URLs (e.g. the bidon
    Spotify callback) as <code>, not clickable links.
    """
    t = html.escape(_strip_emoji(text))
    # [label](https://url) → <a href>label</a> (credential_guides uses markdown links).
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
    # Bare https:// URLs not already inside an href/code → clickable. The lookbehind
    # skips matches preceded by " > = / (already part of an emitted <a>/<code>).
    t = _BARE_URL_RE.sub(lambda m: f'<a href="{m.group(0)}">{m.group(0)}</a>', t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    return t

_CSS = """
@page { size: A4; margin: 22mm 18mm; }
body { font-family: Arial, Helvetica, sans-serif; color: #222; font-size: 12px; line-height: 1.5; }
h1 { color: #1DB954; font-size: 22px; }
h2 { color: #1DB954; font-size: 16px; margin-top: 26px; border-bottom: 1px solid #1DB954; padding-bottom: 3px; }
.intro { color: #444; }
.step { margin: 8px 0; }
.step-num { color: #1DB954; font-weight: bold; }
.caption { color: #888; font-size: 10px; font-style: italic; margin: 2px 0 10px; }
.screenshot { max-width: 100%; border: 1px solid #ddd; border-radius: 4px; margin-top: 4px; }
.missing-img { color: #b00; font-size: 10px; font-style: italic; }
.platform { page-break-inside: avoid; }
table { border-collapse: collapse; width: 100%; margin-top: 10px; font-size: 11px; }
th, td { border: 1px solid #ddd; padding: 5px 7px; text-align: left; }
th { background: #f3f3f3; }
/* Clickable URLs stand out: green, underlined, with a soft highlight. */
a { color: #0a7d33; text-decoration: underline; background: #eafff0; padding: 0 2px;
    border-radius: 2px; word-break: break-all; }
.linkbar { margin: 12px 0 4px; }
.linkbtn { display: inline-block; background: #eafff0; border: 1px solid #1DB954;
    color: #0a7d33; padding: 6px 11px; border-radius: 5px; text-decoration: none;
    font-size: 11px; font-weight: bold; margin-right: 8px; }
.linkbtn.app { background: #1DB954; color: #ffffff; border-color: #1DB954; }
"""


def _img_tag(filename: str, caption: str | None, resolver=None) -> str:
    """Base64-embed the screenshot (self-contained PDF), or a graceful placeholder.

    `resolver` picks the asset root: csv_guides.screenshot_path (assets/csv_guides/)
    or credential_guides.screenshot_path (assets/credential_guide/). Resolved late
    (via the module global) so tests can monkeypatch `screenshot_path`.
    """
    resolve = resolver or screenshot_path
    path = resolve(filename)
    if not path.exists():
        return f'<div class="missing-img">[capture à venir : {html.escape(filename)}]</div>'
    b64 = base64.b64encode(path.read_bytes()).decode("ascii")
    cap = f'<div class="caption">{html.escape(_strip_emoji(caption))}</div>' if caption else ""
    return f'<img class="screenshot" src="data:image/png;base64,{b64}"/>{cap}'


def _expected_table(guide: PlatformGuide) -> str:
    head = "<tr><th>Fichier</th><th>Nom attendu</th><th>Colonnes</th></tr>"
    body = "".join(
        f"<tr><td>{html.escape(e.label)}</td><td>{html.escape(e.filename_hint)}</td>"
        f"<td>{html.escape(', '.join(e.columns))}</td></tr>"
        for e in guide.expected
    )
    return f"<table>{head}{body}</table>"


def _fields_table(cred: PlatformCred) -> str:
    head = "<tr><th>Champ</th><th>Exemple (format)</th><th>Note</th></tr>"
    body = "".join(
        f"<tr><td>{html.escape(f.label)}{' 🔒' if f.secret else ''}</td>"
        f"<td><code>{html.escape(f.example)}</code></td>"
        f"<td>{html.escape(_strip_emoji(f.note or ''))}</td></tr>"
        for f in cred.fields
    )
    return f"<table>{head}{body}</table>"


def _render_guide_html(guide: PlatformGuide) -> str:
    """Render a CSV-import platform guide (steps + screenshots + expected files)."""
    parts = [f'<div class="platform"><h2>{html.escape(_strip_emoji(guide.title))}</h2>',
             f'<p class="intro">{_inline_md(guide.intro)}</p>']
    for i, step in enumerate(guide.steps, 1):
        parts.append(f'<div class="step"><span class="step-num">{i}.</span> '
                     f'{_inline_md(step.text)}</div>')
        if step.screenshot:
            parts.append(_img_tag(step.screenshot, step.caption))
    if guide.expected:
        parts.append(_expected_table(guide))
    parts.append("</div>")
    return "".join(parts)


def _render_cred_html(cred: PlatformCred) -> str:
    """Render an API-credential guide from credential_guides (steps + screenshots + fields)."""
    parts = [f'<div class="platform"><h2>{html.escape(_strip_emoji(cred.title))}</h2>',
             f'<p class="intro">{_inline_md(cred.intro)}</p>']
    for i, step in enumerate(cred.steps, 1):
        parts.append(f'<div class="step"><span class="step-num">{i}.</span> '
                     f'{_inline_md(step.text)}</div>')
        if step.screenshot:
            parts.append(_img_tag(step.screenshot, step.caption, resolver=cred_screenshot_path))
    if cred.fields:
        parts.append(_fields_table(cred))
    if cred.note:
        parts.append(f'<p class="caption">Note — {_inline_md(cred.note)}</p>')
    # Highlighted action bar: open the portal + jump straight to "Tester la connexion".
    app_base = os.environ.get("APP_BASE_URL", "http://localhost:8501").rstrip("/")
    portal = html.escape(cred.portal_url)
    parts.append(
        f'<div class="linkbar">'
        f'<a class="linkbtn" href="{portal}">Ouvrir le portail {html.escape(_strip_emoji(cred.title))}</a>'
        f'<a class="linkbtn app" href="{app_base}?page=credentials">'
        f'Tester la connexion dans streaMLytics</a>'
        f'</div>'
    )
    parts.append("</div>")
    return "".join(parts)


def build_guide_html() -> str:
    """Full standalone HTML document: API credentials (credential_guides) + CSV import."""
    api_sections = "".join(_render_cred_html(c) for c in CREDENTIAL_GUIDES)
    csv_sections = "".join(_render_guide_html(g) for g in CSV_GUIDES)
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_CSS}</style></head><body>"
        "<h1>Démarrer avec streaMLytics — API &amp; CSV</h1>"
        "<p class='intro'>Ce guide couvre les deux sources de données : "
        "<strong>(1) les connecteurs API</strong> (Spotify, YouTube, SoundCloud, "
        "Meta/Instagram) à renseigner dans la page « Credentials API », et "
        "<strong>(2) l'import des fichiers CSV</strong> (Spotify for Artists, Apple Music, "
        "iMusician) via la page « Import CSV ».</p>"
        "<h1 style='margin-top:30px;'>Partie 1 — Connecteurs API</h1>"
        f"{api_sections}"
        "<h1 style='margin-top:30px;'>Partie 2 — Import des fichiers CSV</h1>"
        f"{csv_sections}</body></html>"
    )


def output_pdf_path() -> Path:
    from src.utils.config_loader import config_loader
    return config_loader.project_root / "docs" / "guides" / "onboarding_guide.pdf"


def build_guide_pdf(out: Path | None = None) -> Path:
    """Render the guide HTML to a PDF on disk. Returns the output path."""
    from weasyprint import HTML
    target = out or output_pdf_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=build_guide_html()).write_pdf(str(target))
    return target


if __name__ == "__main__":
    print(f"Guide PDF written to {build_guide_pdf()}")
