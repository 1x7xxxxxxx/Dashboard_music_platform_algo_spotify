#!/usr/bin/env python3
"""Build the animated streaMLytics avatar (Google account profile picture).

Type: Utility
Uses: PIL (Pillow)
Triggers: manual — `python3 tools/dev/make_avatar_gif.py`
Persists in: assets/brand/avatar_streamlytics.gif (+ .png for the still fallback)

Why this exists, and what it can and cannot buy — measured 2026-08-28.

R54: the moving image beside the alert mails is the SENDER's Google account profile
picture, not anything the application sends. Verified in the code: the three senders
emit no `<img>`, no `MIMEImage` and no remote URL, and `From:` is
`streaMLytics <noreply@streamlytics.fr>` (`src/utils/email_identity.py`).

**The inbox ROW is the one surface that does not animate.** Gmail holds frame 1 in the
dense message list and plays the animation only in expanded profile views (hover, the
contact card). Two independent sources say so and none contradicts it. So the design
rule here is not "make it move" — it is:

    frame 1 must be a complete, legible avatar on its own,

because frame 1 IS the inbox line. The motion is a bonus for the surfaces that show it.

Geometry follows the same constraint. Gmail crops the avatar to a circle, so the
artwork is drawn on a disc and every element stays inside the middle 70 % — a mark that
reads fine as a square loses its edges the moment it is used.

Source of truth for the shapes and colours: `src/dashboard/assets/logo_mark.svg`
(equalizer bars in the #1DB954 → #1ED760 gradient over #191414, white trend line). The
bars are redrawn here rather than rasterised so their heights can be animated; the
still frame reproduces the SVG's own bar heights exactly.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 256                      # square, ≥250 px — the practical Google minimum
FRAMES = 24
FRAME_MS = 80                   # ~1.9 s per loop, slow enough not to read as a glitch
OUT_DIR = Path(__file__).resolve().parents[2] / "assets" / "brand"

BG = (25, 20, 20)               # #191414
GREEN_LO = (29, 185, 84)        # #1DB954
GREEN_HI = (30, 215, 96)        # #1ED760
WHITE = (255, 255, 255)

# The SVG's own bar heights, on its 120-unit canvas: (x, y, w, h).
_SVG_BARS = [(20, 70, 13, 32), (39, 54, 13, 48), (58, 62, 13, 40), (77, 34, 13, 68)]
_SVG_CANVAS = 120.0

# Everything is drawn inside this fraction of the width, because Gmail crops to a
# circle and a corner-to-corner mark loses its corners.
SAFE = 0.70


def _lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _bar_heights(frame: int) -> list[float]:
    """Bar heights in SVG units. Frame 0 reproduces the static mark exactly.

    The still frame is not "the animation, paused" — it is the logo. A loop that
    drifts away from it would make the inbox line show something the brand never
    approved, which is the only frame most people ever see.
    """
    base = [h for *_, h in _SVG_BARS]
    if frame == 0:
        return base
    t = frame / FRAMES
    # Each bar breathes on its own phase, so the group reads as a level meter rather
    # than as one shape scaling.
    return [
        h * (1.0 + 0.28 * math.sin(2 * math.pi * (t + i * 0.22)))
        for i, h in enumerate(base)
    ]


def _draw(frame: int) -> Image.Image:
    img = Image.new("RGB", (SIZE, SIZE), BG)
    d = ImageDraw.Draw(img)
    d.ellipse((0, 0, SIZE - 1, SIZE - 1), fill=BG)

    scale = SIZE * SAFE / _SVG_CANVAS
    off = (SIZE - _SVG_CANVAS * scale) / 2

    def px(v):
        return off + v * scale

    heights = _bar_heights(frame)
    baseline = 102.0                    # the SVG's common bar bottom
    tops = []
    for (x, _y, w, _h), h in zip(_SVG_BARS, heights):
        top = baseline - h
        tops.append((px(x + w / 2), px(top)))
        # Vertical gradient across the bar group, matching the SVG's diagonal ramp.
        colour = _lerp(GREEN_LO, GREEN_HI, (x - 20) / 57)
        d.rounded_rectangle(
            (px(x), px(top), px(x + w), px(baseline)),
            radius=max(2, round(5 * scale)), fill=colour)

    # The trend line rides the bar tops, so it moves with them instead of floating.
    end = (px(100), px(24) + (tops[-1][1] - px(34)))
    d.line([(px(26), tops[0][1]), *tops[1:], end],
           fill=WHITE, width=max(2, round(4 * scale)), joint="curve")
    r_out, r_in = max(3, round(6 * scale)), max(2, round(3 * scale))
    d.ellipse((end[0] - r_out, end[1] - r_out, end[0] + r_out, end[1] + r_out), fill=WHITE)
    d.ellipse((end[0] - r_in, end[1] - r_in, end[0] + r_in, end[1] + r_in), fill=GREEN_LO)
    return img


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = [_draw(i) for i in range(FRAMES)]
    gif = OUT_DIR / "avatar_streamlytics.gif"
    png = OUT_DIR / "avatar_streamlytics.png"

    # `disposal=2` clears each frame: without it a shrinking bar leaves the taller
    # previous frame behind and the meter only ever grows.
    frames[0].save(gif, save_all=True, append_images=frames[1:], duration=FRAME_MS,
                   loop=0, disposal=2, optimize=True)
    frames[0].save(png)                 # the still fallback = frame 1, by construction

    print(f"{gif}  {gif.stat().st_size / 1024:.0f} KB  {FRAMES} frames  {SIZE}x{SIZE}")
    print(f"{png}  {png.stat().st_size / 1024:.0f} KB  (frame 1 — what the inbox row shows)")
    assert gif.stat().st_size < 1_000_000, "keep it under 1 MB"


if __name__ == "__main__":
    main()
