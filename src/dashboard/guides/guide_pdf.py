"""Static onboarding-guide PDF — second renderer of csv_guides (see csv_guides).

Type: Sub
Uses: weasyprint, base64, src.dashboard.content.csv_guides
Depends on: assets/csv_guides/*.png (optional — missing images degrade gracefully)
Persists in: docs/guides/csv_onboarding_guide.pdf

Dedicated to the instructional guide (artist-independent, image-heavy) — kept
separate from pdf_exporter.py, which is coupled to per-artist DB data. Build once
with `python -m src.dashboard.guides.guide_pdf` and commit the output; the welcome
email attaches it.
"""
import base64
import html
import re
from pathlib import Path

from src.dashboard.content.csv_guides import CSV_GUIDES, PlatformGuide, screenshot_path

# WeasyPrint's base font has no emoji glyphs (they render as tofu), so strip them
# from the PDF. The Streamlit renderer keeps emojis (its fonts support them).
_EMOJI_RE = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF✀-➿️⭐⬆]+"
)


def _strip_emoji(text: str) -> str:
    return re.sub(r"\s{2,}", " ", _EMOJI_RE.sub("", text)).strip()


def _inline_md(text: str) -> str:
    """Escape HTML then convert inline markdown (**bold**, `code`) the content uses."""
    t = html.escape(_strip_emoji(text))
    t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"`(.+?)`", r"<code>\1</code>", t)
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
"""


def _img_tag(filename: str, caption: str | None) -> str:
    """Base64-embed the screenshot (self-contained PDF), or a graceful placeholder."""
    path = screenshot_path(filename)
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


def _render_guide_html(guide: PlatformGuide) -> str:
    parts = [f'<div class="platform"><h2>{html.escape(_strip_emoji(guide.title))}</h2>',
             f'<p class="intro">{_inline_md(guide.intro)}</p>']
    for i, step in enumerate(guide.steps, 1):
        parts.append(f'<div class="step"><span class="step-num">{i}.</span> '
                     f'{_inline_md(step.text)}</div>')
        if step.screenshot:
            parts.append(_img_tag(step.screenshot, step.caption))
    parts.append(_expected_table(guide))
    parts.append("</div>")
    return "".join(parts)


def build_guide_html() -> str:
    """Full standalone HTML document for the guide, from CSV_GUIDES."""
    sections = "".join(_render_guide_html(g) for g in CSV_GUIDES)
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_CSS}</style></head><body>"
        "<h1>Importer vos données dans streaMLytics</h1>"
        "<p class='intro'>Ce guide explique comment télécharger vos fichiers CSV "
        "depuis Spotify for Artists, Apple Music for Artists et iMusician, puis les "
        "importer via la page « Import CSV ».</p>"
        f"{sections}</body></html>"
    )


def output_pdf_path() -> Path:
    from src.utils.config_loader import config_loader
    return config_loader.project_root / "docs" / "guides" / "csv_onboarding_guide.pdf"


def build_guide_pdf(out: Path | None = None) -> Path:
    """Render the guide HTML to a PDF on disk. Returns the output path."""
    from weasyprint import HTML
    target = out or output_pdf_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=build_guide_html()).write_pdf(str(target))
    return target


if __name__ == "__main__":
    print(f"Guide PDF written to {build_guide_pdf()}")
