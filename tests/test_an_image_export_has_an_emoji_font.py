"""Every image that exports charts installs an emoji font (R287).

Owner, 2026-09-28 (fiches 1 and 17): « les logos Spotify et YouTube, c'est des carrés ».
Plotly exports through kaleido, which only finds fonts through fontconfig: with no emoji font,
🎵 🎬 🚀 in a trace name or a title are drawn as empty squares — in the review dossier AND in
the artist's PDF report (measured: `fc-list | grep -ci emoji` = 0 in the production dashboard
container). ☁️ survived only because DejaVu happens to carry U+2601.

Does not cover: a developer workstation — kaleido reads ~/.fonts and /usr/share/fonts, not
~/.local/share/fonts (it resets XDG_DATA_HOME).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONT = "fonts-noto-color-emoji"
#: The images whose code exports figures to PNG/PDF: the dashboard (pdf_exporter, pdf_charts)
#: and Airflow (the onboarding_report DAG builds the artist PDF).
EXPORTING_IMAGES = ("Dockerfile", "Dockerfile.airflow")


def apt_packages(dockerfile_text: str) -> set[str]:
    """Every package named by an `apt-get install` of a RUN instruction. Pure."""
    text = dockerfile_text.replace("\\\n", " ")
    pkgs: set[str] = set()
    for run in re.findall(r"^RUN (.*)$", text, re.M):
        for seg in run.split("&&"):
            words = seg.split()
            if "apt-get" in words and "install" in words:
                pkgs |= {w for w in words[words.index("install") + 1:] if not w.startswith("-")}
    return pkgs


def test_every_exporting_image_installs_an_emoji_font():
    missing = [f for f in EXPORTING_IMAGES
               if FONT not in apt_packages((ROOT / f).read_text(encoding="utf-8"))]
    assert not missing, f"{missing} export charts without {FONT} — every emoji becomes a square"


def test_the_reader_sees_a_package_and_not_a_comment():
    """Non-vacuity: the package in an install line counts, the same word in a comment does not."""
    assert FONT in apt_packages(f"RUN apt-get update && apt-get install -y \\\n    {FONT} \\\n    gcc\n")
    assert FONT not in apt_packages(f"# {FONT} would fix it\nRUN apt-get install -y gcc\n")
