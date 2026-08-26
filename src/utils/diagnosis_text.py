"""How a probe's diagnosis is re-rendered for the surface that shows it.

Type: Utility
Uses: html, re (stdlib only — must import from a DAG, a CLI and a Streamlit view)
Triggers: alert_monitor, status_matrix, tools/artist_preflight
Depends on: nothing
Persists in: nothing

Why this module exists — measured 2026-08-26 on the nightly PRODUCTION alert.

The connection probes author their diagnosis in a small markdown dialect: `**bold**`
around the identifier at fault, a blank line, then the bullets that say what to DO.
Three surfaces consume it, and only one of them speaks that dialect:

  * the credentials form  → `st.error(msg)`, markdown. Correct — and it is the one
                            surface that only ever runs because a human already clicked.
  * the nightly e-mail    → an HTML `<td>`: `\\n` collapses, `**` shows as asterisks.
  * `artist_preflight`    → one terminal line per platform.

`platform_probes.probe` reconciled the three by keeping `splitlines()[0]` — the first
line. That is the half naming the SYMPTOM. The half it dropped is the half naming the
GESTURE. On the alert of 2026-08-26 it cost both red rows their fix:

    Benken / Meta        kept    "act_65390907 inaccessible … (#200) … for details"
                         dropped "→ le compte n'a pas été partagé avec l'app
                                  (Business Manager → … → permission Annonceur)"
    GRiNCH / SoundCloud  kept    "… aucun titre public … Deux cas :"
                         dropped the two cases.

A sentence that ends on "Deux cas :" and then enumerates nothing is worse than no
sentence at all: it tells the reader an answer exists and withholds it.

So the flattening is removed at the source, and each surface renders what it can show.
The rule this encodes: **the renderer adapts to the message, never the message to the
renderer.** There is one author and three readers, and only the author knows which half
of the sentence is the actionable one.
"""
from __future__ import annotations

import re
from html import escape

# `**bold**` — the dialect the probes actually author. Non-greedy so two emphasised
# runs on one line stay two.
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)

# What a diagnosis may hold before it is treated as a runaway platform echo. The store
# is a TEXT column, so this bounds a pathological API response — not the message: the
# longest authored diagnosis in this repo is ~400 characters. The old cap was 300,
# which is why it bit an authored string in the first place.
MAX_LEN = 2000


def clamp(message: str, limit: int = MAX_LEN) -> str:
    """Bound a message without silently losing its end.

    A cut that lands mid-sentence reads as a complete sentence — the shape that made
    the first line of a two-part diagnosis look like the whole diagnosis. When a cap
    fires it must be legible in the text itself, so the ellipsis is not decoration.
    """
    text = str(message or "")
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def as_html(message: str) -> str:
    """The diagnosis as an HTML fragment: escaped first, then emphasis, then breaks.

    Escaping BEFORE the markdown pass is what makes this safe to hand a platform's own
    error text — Meta's `(#200)` answers embed URLs and have carried `<` — while still
    rendering the emphasis WE authored. Doing it the other way round would let a
    platform's message close our `<td>`.
    """
    out = escape(str(message or ""))
    out = _BOLD.sub(r"<b>\1</b>", out)
    return out.replace("\n", "<br>")


def as_markdown(message: str) -> str:
    """The diagnosis for a markdown surface (`st.caption`, `st.error`).

    Only the line breaks need help here: a single `\\n` is not a break in markdown, so
    the two bullets of the SoundCloud diagnosis would run into one another. Two
    trailing spaces make it a hard break. `**` is already the right dialect.
    """
    return "\n".join(
        line + "  " if line.strip() else line
        for line in str(message or "").split("\n")
    )


def as_console(message: str, indent: str = "     ") -> str:
    """The diagnosis for a terminal: every line kept, continuations indented.

    `artist_preflight` truncated to `splitlines()[0][:140]` so its one-line-per-platform
    layout would hold. The layout is worth keeping; losing the gesture is not the price
    for it — so the first line stays on the platform's line and the rest sits under it.
    """
    lines = [ln.rstrip() for ln in _BOLD.sub(r"\1", str(message or "")).split("\n")]
    kept = [ln for ln in lines if ln.strip()]
    return ("\n" + indent).join(kept)
