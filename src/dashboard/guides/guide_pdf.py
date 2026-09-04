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
from src.dashboard.utils.os_hints import BOTH as _OS_BOTH, resolve_os_tokens
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
    # *italique* — APRÈS le gras, sinon `**x**` serait mangé de l'intérieur par ce
    # motif-ci. Le guide s'en servait déjà (« à droite du bouton *Suivre* ») et le
    # PDF sortait les astérisques telles quelles : la prose est écrite en markdown
    # pour Streamlit, et ce rendu-ci n'en connaissait qu'une moitié. Le motif exige
    # un caractère non-espace de chaque côté, pour qu'un astérisque isolé — une note
    # de bas de page, une multiplication — ne déclenche rien.
    t = re.sub(r"(?<!\*)\*(?!\s)([^*]+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", t)
    return t

# Layout decisions below are measured, not felt — see the 2026-09-03 session.
#
#   * `text-align: left` is DECLARED. It was already the rendered result (nothing set
#     it, so WeasyPrint used `start`), and it is the right value — Few, *Show Me the
#     Numbers* p.192: the hard left edge is what makes scanning efficient. Undeclared
#     correctness is one edit away from being lost. Justification is refused: it digs
#     white rivers in a 174 mm column of 12px Arial.
#   * `.caption` was `#888` at 10px = **3.5:1** on white, under the WCAG AA floor of
#     4.5:1 — and it is the text that captions every screenshot. `#595959` is 7.0:1.
#   * `orphans`/`widows` are what actually caused the reported "trous". `.platform {
#     page-break-inside: avoid }` alone pushes a whole platform block to the next page
#     when it does not fit, leaving a gap at the bottom. Keeping `avoid` (it prevents
#     worse) and adding stranded-line control is what closes them.
#   * `#1DB954` is Spotify's green and it was the brand colour of EVERY section,
#     including the Apple Music and YouTube ones. The chrome now uses a neutral ink;
#     Few, *Information Dashboard Design* §7.1.3 — delineate with the least visible
#     means that does the job.
#   * `word-break: break-all` split URLs mid-word anywhere. `overflow-wrap: anywhere`
#     breaks only where it must.
_INK = "#1f3a5f"      # chrome: headings, rules, buttons — ours, not a platform's
_INK_SOFT = "#54606e"  # secondary prose

_CSS = """
@page { size: A4; margin: 22mm 18mm; @bottom-center { content: counter(page); color: #595959; font-size: 9px; } }
body { font-family: Arial, Helvetica, sans-serif; color: #222; font-size: 12px; line-height: 1.5; text-align: left; orphans: 3; widows: 3; }
h1 { color: #1f3a5f; font-size: 22px; }
h2 { color: #1f3a5f; font-size: 16px; margin-top: 26px; border-bottom: 1px solid #1f3a5f; padding-bottom: 3px; break-after: avoid; }
.intro { color: #54606e; }
.step { margin: 8px 0; }
.step-num { color: #1f3a5f; font-weight: bold; }
.caption { color: #595959; font-size: 11px; font-style: italic; margin: 2px 0 10px; }
.screenshot { max-width: 100%; border: 1px solid #ddd; border-radius: 4px; margin-top: 4px; }
.missing-img { color: #b00; font-size: 10px; font-style: italic; }
.platform { page-break-inside: avoid; }
.goals { background: #f4f7fb; border-left: 3px solid #1f3a5f; padding: 10px 14px; margin: 14px 0 18px; }
.goals ul { margin: 6px 0 0 18px; padding: 0; }
.toc { margin: 4px 0 22px; }
.toc li { margin: 2px 0; }
table { border-collapse: collapse; width: 100%; margin-top: 10px; font-size: 11px; }
th, td { border: 1px solid #ddd; padding: 5px 7px; text-align: left; }
th { background: #f3f3f3; }
/* Clickable URLs stand out: green, underlined, with a soft highlight. */
a { color: #14532d; text-decoration: underline; background: #eefaf1; padding: 0 2px;
    border-radius: 2px; overflow-wrap: anywhere; }
/* Ce qu'il y a à coller. `.paste-head` porte l'action, la liste porte le détail —
   l'exemple factice y est une légende en italique, jamais une colonne de tableau
   aussi nette que le nom du champ (2026-09-04). */
.paste-head { margin: 12px 0 2px; font-weight: bold; color: #1f3a5f; }
ul.fields { margin: 2px 0 10px 18px; padding: 0; }
ul.fields li { margin: 4px 0; }
ul.fields .caption { margin: 0; display: block; }
.linkbar { margin: 12px 0 4px; }
.linkbtn { display: inline-block; background: #eef2f8; border: 1px solid #1f3a5f;
    color: #1f3a5f; padding: 6px 11px; border-radius: 5px; text-decoration: none;
    font-size: 11px; font-weight: bold; margin-right: 8px; }
.linkbtn.app { background: #1f3a5f; color: #ffffff; border-color: #1f3a5f; }
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


# UI chrome strings per language. The platform CONTENT comes from the FR/EN content
# modules; these are just the document scaffolding (titles, table headers, buttons).
_UI = {
    'fr': {
        'doc_h1': "Démarrer avec streaMLytics — API &amp; CSV",
        'doc_intro': ("Ce guide couvre les deux sources de données : "
                      "<strong>(1) les connecteurs API</strong>, à renseigner dans la page "
                      "« Credentials API », et <strong>(2) l'import des fichiers CSV</strong>, "
                      "via la page « Ajouter mes chiffres ». Le sommaire ci-dessous liste "
                      "les plateformes couvertes."),
        'goals_h': "À la fin de ce guide, vous aurez :",
        'goals': ("vos comptes connectés, et de la donnée qui arrive chaque nuit sans "
                  "que vous ayez à y revenir ;",
                  "vos écoutes Spotify et Apple visibles dans le tableau de bord ;",
                  "de quoi relier ce que vous dépensez en promo à ce que ça produit "
                  "en écoutes."),
        'part1': "Partie 1 — Connecteurs API",
        'part2': "Partie 2 — Import des fichiers CSV",
        'th_file': "Fichier", 'th_name': "Nom attendu", 'th_cols': "Colonnes",
        'th_field': "Champ", 'th_example': "Exemple (format)", 'th_note': "Note",
        'note': "Note", 'open_portal': "Ouvrir le portail {title}",
        'test_conn': "Tester la connexion dans streaMLytics",
        'paste_head': ("À coller dans l'encadré 👉 Saisir tes identifiants, "
                       "en haut de cet onglet :"),
        'ex_prefix': "ex.", 'ex_suffix': "exemple de forme, ne le copie pas",
    },
    'en': {
        'doc_h1': "Getting started with streaMLytics — API &amp; CSV",
        'doc_intro': ("This guide covers both data sources: "
                      "<strong>(1) the API connectors</strong>, to fill in on the "
                      "« API Credentials » page, and <strong>(2) CSV file import</strong>, "
                      "via the « Add my numbers » page. The outline below lists the "
                      "platforms covered."),
        'goals_h': "By the end of this guide you will have:",
        'goals': ("your accounts connected, and data arriving every night without you "
                  "coming back to it;",
                  "your Spotify and Apple listens visible on the dashboard;",
                  "what you need to tie promo spend to the listens it produces."),
        'part1': "Part 1 — API connectors",
        'part2': "Part 2 — CSV file import",
        'th_file': "File", 'th_name': "Expected name", 'th_cols': "Columns",
        'th_field': "Field", 'th_example': "Example (format)", 'th_note': "Note",
        'note': "Note", 'open_portal': "Open the {title} portal",
        'test_conn': "Test the connection in streaMLytics",
        'paste_head': ("To paste into the 👉 Enter your credentials box, "
                       "at the top of that tab:"),
        'ex_prefix': "e.g.", 'ex_suffix': "sample format, do not copy it",
    },
}


def _expected_table(guide: PlatformGuide, ui: dict) -> str:
    head = f"<tr><th>{ui['th_file']}</th><th>{ui['th_name']}</th><th>{ui['th_cols']}</th></tr>"
    body = "".join(
        f"<tr><td>{html.escape(e.label)}</td><td>{html.escape(e.filename_hint)}</td>"
        f"<td>{html.escape(', '.join(e.columns))}</td></tr>"
        for e in guide.expected
    )
    return f"<table>{head}{body}</table>"


def _fields_list(cred: PlatformCred, ui: dict) -> str:
    """Ce qu'il y a à coller — une liste, plus un tableau d'exemples factices.

    Même changement que sur l'écran (`credential_guides_st._render_fields_table`) et
    pour la même raison, signalée le 2026-09-04 : dans un tableau, l'exemple factice
    occupait une colonne aussi nette que le nom du champ, et se lisait comme une
    valeur à copier. Il passe en italique, précédé de `ex.` et suivi de la phrase qui
    dit ce qu'il est. Les deux surfaces doivent dire la même chose : le PDF est
    imprimé et relu loin de l'écran, un écart entre les deux n'est jamais rattrapé.
    """
    rows = []
    for f in cred.fields:
        lock = " 🔒" if f.secret else ""
        note = html.escape(_strip_emoji(f.note or ""))
        rows.append(
            f'<li><strong>{html.escape(f.label)}</strong>{lock}'
            + (f'<br/><span class="caption">{note}</span>' if note else "")
            + f'<br/><span class="caption"><em>{ui["ex_prefix"]} '
              f'{html.escape(f.example)}</em> — {ui["ex_suffix"]}</span></li>'
        )
    return (f'<p class="paste-head">{ui["paste_head"]}</p>'
            f'<ul class="fields">{"".join(rows)}</ul>')


def _render_guide_html(guide: PlatformGuide, ui: dict) -> str:
    """Render a CSV-import platform guide (steps + screenshots + expected files)."""
    parts = [f'<div class="platform"><h2>{html.escape(_strip_emoji(guide.title))}</h2>',
             f'<p class="intro">{_inline_md(guide.intro)}</p>']
    for i, step in enumerate(guide.steps, 1):
        parts.append(f'<div class="step"><span class="step-num">{i}.</span> '
                     f'{_inline_md(step.text)}</div>')
        if step.screenshot:
            parts.append(_img_tag(step.screenshot, step.caption))
    if guide.expected:
        parts.append(_expected_table(guide, ui))
    parts.append("</div>")
    return "".join(parts)


def _render_cred_html(cred: PlatformCred, ui: dict) -> str:
    """Render an API-credential guide from credential_guides (steps + screenshots + fields)."""
    parts = [f'<div class="platform"><h2>{html.escape(_strip_emoji(cred.title))}</h2>',
             f'<p class="intro">{_inline_md(resolve_os_tokens(cred.intro, _OS_BOTH))}</p>']
    for i, step in enumerate(cred.steps, 1):
        parts.append(f'<div class="step"><span class="step-num">{i}.</span> '
                     f'{_inline_md(resolve_os_tokens(step.text, _OS_BOTH))}</div>')
        if step.screenshot:
            parts.append(_img_tag(step.screenshot, step.caption, resolver=cred_screenshot_path))
    if cred.fields:
        parts.append(_fields_list(cred, ui))
    if cred.note:
        parts.append(f'<p class="caption">{ui["note"]} — {_inline_md(cred.note)}</p>')
    # `cred.admin_note` n'est délibérément PAS rendu : ce PDF est joint à l'e-mail de
    # bienvenue d'un artiste. Ce qui relève de l'exploitant — créer une app chez le
    # fournisseur, poser une variable d'environnement — n'a rien à y faire.
    # Highlighted action bar: open the portal + jump straight to the credentials page.
    app_base = os.environ.get("APP_BASE_URL", "http://localhost:8501").rstrip("/")
    portal = html.escape(cred.portal_url)
    title = html.escape(_strip_emoji(cred.title))
    parts.append(
        f'<div class="linkbar">'
        f'<a class="linkbtn" href="{portal}">{ui["open_portal"].format(title=title)}</a>'
        f'<a class="linkbtn app" href="{app_base}?page=credentials">{ui["test_conn"]}</a>'
        f'</div>'
    )
    parts.append("</div>")
    return "".join(parts)


def build_guide_html(lang: str = "fr") -> str:
    """Full standalone HTML document: API credentials + CSV import, in `lang`."""
    ui = _UI.get(lang, _UI["fr"])
    if lang == "en":
        from src.dashboard.content.credential_guides_en import CREDENTIAL_GUIDES_EN as creds
        from src.dashboard.content.csv_guides_en import CSV_GUIDES_EN as guides
    else:
        creds, guides = CREDENTIAL_GUIDES, CSV_GUIDES
    api_sections = "".join(_render_cred_html(c, ui) for c in creds)
    csv_sections = "".join(_render_guide_html(g, ui) for g in guides)
    # A reader who cannot see the end does not start. 16 pages arrived with no table
    # of contents, no page numbers and no statement of what the reader ends up with —
    # only a two-sentence intro that also happened to be out of date (it listed three
    # CSV platforms when there were four). The outline is DERIVED from the same tuples
    # the body renders, so it cannot go stale the way that sentence did.
    goals = (
        f"<div class='goals'><strong>{ui['goals_h']}</strong>"
        + "<ul>" + "".join(f"<li>{g}</li>" for g in ui["goals"]) + "</ul></div>"
    )
    toc = (
        "<div class='toc'><ol>"
        f"<li>{html.escape(_strip_emoji(ui['part1']))}<ul>"
        + "".join(f"<li>{html.escape(_strip_emoji(c.title))}</li>" for c in creds)
        + f"</ul></li><li>{html.escape(_strip_emoji(ui['part2']))}<ul>"
        + "".join(f"<li>{html.escape(_strip_emoji(g.title))}</li>" for g in guides)
        + "</ul></li></ol></div>"
    )
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>{_CSS}</style></head><body>"
        f"<h1>{ui['doc_h1']}</h1>"
        f"<p class='intro'>{ui['doc_intro']}</p>"
        f"{goals}{toc}"
        f"<h1 style='margin-top:30px;'>{ui['part1']}</h1>"
        f"{api_sections}"
        f"<h1 style='margin-top:30px;'>{ui['part2']}</h1>"
        f"{csv_sections}</body></html>"
    )


def output_pdf_path(lang: str = "fr") -> Path:
    """FR → onboarding_guide.pdf (default); EN → onboarding_guide_en.pdf."""
    from src.utils.config_loader import config_loader
    name = "onboarding_guide.pdf" if lang == "fr" else f"onboarding_guide_{lang}.pdf"
    return config_loader.project_root / "docs" / "guides" / name


def fingerprint_path() -> Path:
    """Where the fingerprint of the last rendered guide lives."""
    from src.utils.config_loader import config_loader
    return config_loader.project_root / "docs" / "guides" / ".guide_fingerprint"


def source_fingerprint() -> str:
    """A stable digest of everything the guide RENDERS, both languages.

    Why the rendered HTML and not the content dataclasses — measured 2026-09-03.
    The shipped `docs/guides/*.pdf` was 82 days behind its own sources: it still told
    artists to set `Redirect URI = http://127.0.0.1:8888/callback` and to copy a
    `Client Secret`, both deleted from the source in June. Six guards check the
    SOURCE; nothing compared the ARTEFACT, and the artefact is what the welcome e-mail
    attaches and what both download buttons serve.

    Hashing the dataclasses would have been wrong in both directions:

    * `PlatformCred.admin_note` exists in the source and is deliberately NOT rendered
      (see `_render_cred_html`), so editing it would turn this guard red for a PDF
      that did not change — the way a guard earns the right to be ignored;
    * the screenshots are base64-embedded, so a re-captured PNG changes the PDF while
      leaving every dataclass byte-identical. Only the rendered HTML sees both.

    Hashing the PDF itself would be worse still: WeasyPrint is not byte-reproducible
    across versions, so the guard would go red on a dependency bump and get disabled
    (`permanently-red-guard-reports-nothing`).

    The one substitution below exists because `_render_cred_html` embeds
    `APP_BASE_URL`, which legitimately differs between a laptop, CI and production.
    Left in, this digest would depend on where it was computed — a guard that is red
    for a reason that has nothing to do with the guide.
    """
    import hashlib

    app_base = os.environ.get("APP_BASE_URL", "http://localhost:8501").rstrip("/")
    joined = "\x00".join(build_guide_html(lang) for lang in ("fr", "en"))
    normalised = joined.replace(app_base, "{APP_BASE_URL}")
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def rendered_fingerprint() -> str:
    """A digest of the PDF FILES currently on disk, both languages.

    Separate from `source_fingerprint` on purpose, and the separation is the whole
    point — measured 2026-09-03, on the first version of this guard.

    That version stored only the source digest and compared it to the sources. It
    therefore answered "have the sources moved since someone last rebuilt?" — which
    is a proxy, not the question. Restoring the June PDFs while leaving the
    fingerprint file alone left it **green**, on exactly the defect it was written
    for. A predicate that fits the symptom instead of the question is this repo's
    most repeated defect (`a-guards-scope-is-the-defect`); this is its seventh.

    WeasyPrint's non-reproducibility is not an objection here: this digest is never
    compared ACROSS rebuilds, only against the value recorded when these very files
    were written. Both are rewritten together, so a rebuild can never make it red.
    """
    import hashlib

    h = hashlib.sha256()
    for lang in ("fr", "en"):
        path = output_pdf_path(lang)
        h.update(path.name.encode("utf-8"))
        h.update(path.read_bytes() if path.is_file() else b"<missing>")
    return h.hexdigest()


def write_fingerprint() -> Path:
    """Record both digests next to the PDFs. Called only after a real render."""
    target = fingerprint_path()
    # The trailing pragma is not decoration: `detect-secrets` (pre-commit) classes a
    # bare 64-char hex digest as a "Hex High Entropy String" and refuses the commit.
    # Marking it here rather than widening `.secrets.baseline` keeps the baseline
    # meaning "acknowledged secret" instead of "acknowledged noise", and it survives
    # every regeneration because the writer emits it. `read_fingerprint` strips it.
    pragma = "  # pragma: allowlist secret"
    target.write_text(
        f"source={source_fingerprint()}{pragma}\n"
        f"rendered={rendered_fingerprint()}{pragma}\n",
        encoding="utf-8",
    )
    return target


def read_fingerprint() -> dict[str, str]:
    """The recorded digests, or an empty mapping when the file is absent."""
    path = fingerprint_path()
    if not path.is_file():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("=")
        value = value.split("#", 1)[0]  # drop the allowlist pragma written above
        if value.strip():
            out[key.strip()] = value.strip()
    return out


def output_html_path(lang: str = "fr") -> Path:
    """Where the web version of the guide lives, served by Caddy at /guide."""
    from src.utils.config_loader import config_loader
    name = "index.html" if lang == "fr" else f"index_{lang}.html"
    return config_loader.project_root / "docs" / "guides" / name


_DATA_URI_RE = re.compile(r'data:image/png;base64,([A-Za-z0-9+/=]+)')


def _externalise_images(html_text: str, out_dir: Path) -> str:
    """Write the embedded PNGs as files and point the page at them.

    Measured 2026-09-03, on the page published an hour earlier: **98 % of its 978 KB
    was base64**, and base64 inflates a PNG by exactly 33 % (719 KB of image became
    957 KB of text). The prose and CSS are 20 KB. So a reader paid ~700 KB gzipped
    on EVERY visit for a document whose text is a rounding error, and a browser could
    cache none of it separately because it was one HTML blob.

    Files for the PAGE, base64 for the PDF — the asymmetry is the point. A PDF is
    mailed and downloaded, so it has to be self-contained; a page is served from a
    directory Caddy already exposes, where each image is cacheable on its own and
    unchanged images survive a guide edit.

    Named by content hash: two guides referencing the same screenshot write it once,
    and a re-render with no visual change produces byte-identical filenames, so the
    directory does not churn.
    """
    import base64
    import hashlib

    # `media/` et non `img/` : pendant la fenêtre où le préfixe `/guide` n'était
    # pas retiré, Caddy a répondu index.html sur chaque URL d'image, et
    # Cloudflare a mis CES réponses en cache pour 4 h. Renommer le répertoire
    # change toutes les URL d'un coup — un MISS garanti, sans credential de
    # purge. Les noms de fichiers restent des hashs de contenu.
    img_dir = out_dir / "media"
    img_dir.mkdir(parents=True, exist_ok=True)

    def _swap(match: re.Match) -> str:
        raw = base64.b64decode(match.group(1))
        name = f"{hashlib.sha256(raw).hexdigest()[:16]}.png"
        path = img_dir / name
        if not path.exists():
            path.write_bytes(raw)
        return f"media/{name}"

    return _DATA_URI_RE.sub(_swap, html_text)


def build_guide_html_page(lang: str = "fr", out: Path | None = None) -> Path:
    """Write the SAME html the PDF is made of, as a standalone web page.

    One source, three renderings — the page, the PDF, and the in-app expanders all
    read `content/credential_guides.py` and `content/csv_guides.py`. Chosen over
    "prettier PDF" for a reason the 2026-09-03 measurement made concrete: the shipped
    PDF had been 82 days stale, and **a document is corrected by redistributing it
    while a page is corrected by saving it**.

    Two consequences worth stating, because they are what the format buys:

    * the screenshots stop being capped by A4 geometry. In the PDF a capture narrower
      than the 174 mm column renders at its natural size, i.e. exactly 96 dpi and
      never more — 9 of the 25 land there. On a page they are just images.
    * links are clickable, and `?page=credentials` actually takes the reader there.

    Images stay base64-embedded rather than referenced: the file is then self-contained,
    so `file_server` has nothing to resolve and a copy of it anywhere still works.
    """
    target = out or output_html_path(lang)
    target.parent.mkdir(parents=True, exist_ok=True)
    html_text = _externalise_images(build_guide_html(lang), target.parent)
    # Trailing newline emitted here, not left to `end-of-file-fixer`: without it the
    # pre-commit hook rewrites the file after `make guide` has fingerprinted it, so
    # every commit would fail the artefact guard it just satisfied.
    target.write_text(html_text + "\n", encoding="utf-8")
    return target


def build_guide_pdf(lang: str = "fr", out: Path | None = None) -> Path:
    """Render the guide HTML to a PDF on disk. Returns the output path."""
    from weasyprint import HTML
    target = out or output_pdf_path(lang)
    target.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=build_guide_html(lang)).write_pdf(str(target))
    return target


if __name__ == "__main__":
    for _lang in ("fr", "en"):
        print(f"Guide PDF  ({_lang}) written to {build_guide_pdf(_lang)}")
        print(f"Guide page ({_lang}) written to {build_guide_html_page(_lang)}")
    # Written in the same breath as the PDFs, never separately: a fingerprint updated
    # on its own would certify an artefact nobody rebuilt.
    print(f"Guide fingerprint written to {write_fingerprint()}")
