"""OS-dependent instruction tokens for the setup guides (Windows/Linux ↔ macOS).

Type: Utility
Uses: streamlit (selector + User-Agent sniffing only — the resolver stays pure)
Depends on: nothing
Persists in: st.session_state['_guide_os'] (per-session, never in DB)

Guides used to hardcode Windows shortcuts (`Ctrl+U`, `Ctrl+F`, `F12`). A macOS
artist following them literally is stuck: those keys do nothing there. Beta
session Grinch 2026-08-12 hit exactly that. Guide prose now carries tokens
(`{{VIEW_SOURCE}}`, `{{FIND}}`, `{{DEVTOOLS}}`…) that `resolve_os_tokens()`
substitutes at render time, so a single source of truth serves both platforms
and the PDF export.

Adding a token = one entry in _TOKENS. Any token left unresolved is caught by
tests/test_os_hints.py, which also forbids raw shortcut spellings in content.
"""
from __future__ import annotations

import re

WINDOWS = "windows"
MAC = "mac"
# Static renderings (the emailed PDF) cannot know the reader's machine: they spell
# both, Windows first.
BOTH = "both"

OS_LABELS = {
    WINDOWS: "💻 Windows / Linux",
    MAC: "🍎 macOS",
}

# token → (Windows/Linux rendering, macOS rendering)
_TOKENS: dict[str, tuple[str, str]] = {
    "MOD": ("Ctrl", "Cmd (⌘)"),
    "VIEW_SOURCE": ("Ctrl+U", "Cmd+Option+U (⌘⌥U)"),
    "FIND": ("Ctrl+F", "Cmd+F (⌘F)"),
    "COPY": ("Ctrl+C", "Cmd+C (⌘C)"),
    "PASTE": ("Ctrl+V", "Cmd+V (⌘V)"),
    "DEVTOOLS": ("F12", "Cmd+Option+I (⌘⌥I)"),
    "RIGHT_CLICK": ("clic droit", "clic droit (ou Ctrl + clic)"),
    "FILE_MANAGER": ("l'Explorateur de fichiers", "le Finder"),
    "DOWNLOADS_DIR": (
        "l'Explorateur → **Téléchargements**",
        "le Finder → **Téléchargements**",
    ),
}

_TOKEN_RE = re.compile(r"\{\{([A-Z_]+)\}\}")


def resolve_os_tokens(text: str, os_key: str = WINDOWS) -> str:
    """Substitute every {{TOKEN}} in `text` for the given OS.

    Pure function — no Streamlit. An unknown token is left verbatim so the test
    guard can spot it instead of it silently disappearing from a guide.
    """
    if not text:
        return text
    def _render(match) -> str:
        name = match.group(1)
        pair = _TOKENS.get(name)
        if pair is None:
            return match.group(0)
        win, mac = pair
        if os_key == BOTH:
            return win if win == mac else f"{win} (Mac : {mac})"
        return mac if os_key == MAC else win

    return _TOKEN_RE.sub(_render, text)


def unresolved_tokens(text: str) -> list[str]:
    """Tokens present in `text` that _TOKENS cannot resolve (test helper)."""
    return [n for n in _TOKEN_RE.findall(text or "") if n not in _TOKENS]


def detect_os_from_user_agent(user_agent: str | None) -> str:
    """Best-effort OS from a browser User-Agent. Defaults to WINDOWS."""
    ua = (user_agent or "").lower()
    if "mac os x" in ua or "macintosh" in ua:
        # iPadOS reports "Macintosh" too; both want the ⌘ spelling anyway.
        return MAC
    return WINDOWS


_STATE_KEY = "_guide_os"


def current_os() -> str:
    """The OS the guides should render for: explicit choice, else auto-detected."""
    import streamlit as st

    chosen = st.session_state.get(_STATE_KEY)
    if chosen in (WINDOWS, MAC):
        return chosen
    detected = WINDOWS
    try:  # st.context.headers is unavailable in bare-script / test contexts
        detected = detect_os_from_user_agent(st.context.headers.get("User-Agent"))
    except Exception:
        pass
    st.session_state[_STATE_KEY] = detected
    return detected


def os_selector(key: str = "os_selector") -> str:
    """Render the Windows/macOS switch and return the active OS.

    Placed at the top of any surface that shows keyboard-level instructions.
    """
    import streamlit as st
    from src.dashboard.utils.i18n import t

    active = current_os()
    options = [WINDOWS, MAC]
    label = t("guides.os_selector", "💻 Instructions adaptées à mon ordinateur :")
    try:
        picked = st.segmented_control(
            label, options, format_func=lambda o: OS_LABELS[o],
            default=active, key=key,
        )
    except Exception:  # older Streamlit — radio is always available
        picked = st.radio(
            label, options, format_func=lambda o: OS_LABELS[o],
            index=options.index(active), horizontal=True, key=key,
        )
    if picked in (WINDOWS, MAC) and picked != active:
        st.session_state[_STATE_KEY] = picked
        active = picked
    return active


def md(text: str) -> str:
    """Shorthand: resolve tokens for the session's current OS."""
    return resolve_os_tokens(text, current_os())
