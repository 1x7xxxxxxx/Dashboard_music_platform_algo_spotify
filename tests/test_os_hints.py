"""Guard — setup guides must not hardcode one operating system's shortcuts.

Error class `guide-windows-only-shortcut`: guide prose spelled `Ctrl+U`, `Ctrl+F`
and `F12` literally. On macOS those keys do nothing, so a Mac artist following
the SoundCloud guide cannot find their User ID at all (beta session Grinch,
2026-08-12 — the tester was on a Mac).

Content now carries {{TOKEN}} placeholders resolved per-OS at render time. These
tests fail if a raw shortcut comes back, or if a token has no rendering.
"""
import re
from pathlib import Path

import pytest

from src.dashboard.utils.os_hints import (
    BOTH,
    MAC,
    WINDOWS,
    detect_os_from_user_agent,
    resolve_os_tokens,
    unresolved_tokens,
)

_ROOT = Path(__file__).resolve().parents[1]

# Every surface whose prose reaches an artist as setup instructions.
_CONTENT_FILES = [
    "src/dashboard/content/credential_guides.py",
    "src/dashboard/content/credential_guides_en.py",
    "src/dashboard/content/csv_guides.py",
    "src/dashboard/content/csv_guides_en.py",
    "src/dashboard/views/credentials/_platform_soundcloud.py",
    "src/dashboard/views/credentials/_platform_youtube.py",
    "src/dashboard/views/credentials/_platform_spotify.py",
    "src/dashboard/views/credentials/_platform_meta.py",
    "src/dashboard/utils/i18n_catalog/credentials.py",
]

# Raw spellings that must go through a token instead.
_FORBIDDEN = re.compile(r"\b(Ctrl\+[A-Z]|F12|Cmd\+[A-Z]|⌘[A-Z⌥])")


@pytest.mark.parametrize("rel", _CONTENT_FILES)
def test_no_raw_os_shortcut_in_guide_content(rel):
    """A shortcut written literally serves exactly one of the two OS families."""
    path = _ROOT / rel
    if not path.exists():  # a renamed file must not silently drop the guard
        pytest.fail(f"{rel} is listed in the guard but does not exist")
    offenders = [
        f"{rel}:{i}: {line.strip()[:90]}"
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if _FORBIDDEN.search(line) and "os_hints" not in line
    ]
    assert not offenders, (
        "Hardcoded OS shortcut(s) — use a {{TOKEN}} from os_hints._TOKENS:\n"
        + "\n".join(offenders)
    )


@pytest.mark.parametrize("rel", _CONTENT_FILES)
def test_every_token_used_in_content_resolves(rel):
    text = (_ROOT / rel).read_text(encoding="utf-8")
    assert not unresolved_tokens(text), (
        f"{rel} uses token(s) with no rendering in os_hints._TOKENS: "
        f"{unresolved_tokens(text)}"
    )


def test_tokens_render_differently_per_os():
    src = "Affiche le code source ({{VIEW_SOURCE}}), cherche ({{FIND}})."
    win = resolve_os_tokens(src, WINDOWS)
    mac = resolve_os_tokens(src, MAC)
    assert "Ctrl+U" in win and "Ctrl+F" in win
    assert "Cmd+Option+U" in mac and "Cmd+F" in mac
    assert "Ctrl+" not in mac
    assert "{{" not in win and "{{" not in mac


def test_both_mode_spells_the_two_families():
    """The emailed PDF cannot know the reader's machine."""
    out = resolve_os_tokens("Ouvre les outils ({{DEVTOOLS}}).", BOTH)
    assert "F12" in out and "Cmd+Option+I" in out


def test_unknown_token_is_left_visible_not_swallowed():
    assert resolve_os_tokens("{{NOPE}}", MAC) == "{{NOPE}}"
    assert unresolved_tokens("{{NOPE}}") == ["NOPE"]


@pytest.mark.parametrize("ua,expected", [
    ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36", MAC),
    ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", WINDOWS),
    ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36", WINDOWS),
    (None, WINDOWS),
    ("", WINDOWS),
])
def test_user_agent_detection(ua, expected):
    assert detect_os_from_user_agent(ua) == expected


def test_the_soundcloud_guide_asks_for_no_keyboard_gesture_at_all():
    """The step that blocked the beta tester no longer exists — that is the fix.

    This test used to assert the Mac spelling of "view page source" was present, which
    was right while the guide asked an artist to read a page's HTML. On 2026-09-03 the
    step was removed entirely: the artist pastes the link to their profile and the
    server resolves the id through SoundCloud's own `/resolve` endpoint.

    Asserting the ABSENCE of every OS-specific gesture is the stronger claim. A guide
    with no shortcut in it cannot spell one wrong for half its readers, which is what
    `guide-single-os-shortcut` is about; the per-OS token machinery stays tested by the
    cases above, on the guides that still need it (YouTube, Meta).
    """
    from src.dashboard.content.credential_guides import CREDENTIAL_GUIDES

    sc = next(g for g in CREDENTIAL_GUIDES if g.key == "soundcloud")
    for os_family in (MAC, WINDOWS):
        joined = " ".join(resolve_os_tokens(s.text, os_family) for s in sc.steps)
        for shortcut in ("Ctrl+", "Cmd+", "⌘", "F12"):
            assert shortcut not in joined, (
                f"the SoundCloud guide spells {shortcut!r} again. It needs no keyboard "
                "gesture: the artist pastes their profile link and the id is resolved "
                "server-side."
            )
        assert "{{" not in joined, "an unresolved OS token survived into the text"
