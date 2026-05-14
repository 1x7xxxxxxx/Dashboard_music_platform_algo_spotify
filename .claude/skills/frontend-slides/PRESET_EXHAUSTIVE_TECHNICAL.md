---
rex: []
---

# Preset — "Exhaustive Technical" deck

Frozen reference for generating long technical reference decks (80–200 slides)
from a Markdown source — checklists, ML/SoftEng documentation, audit reports.

This preset bypasses Phases 1 and 2 of the standard `frontend-slides` workflow
(content discovery + style discovery): all answers are fixed below. Go straight
to Phase 3 generation.

> **When to use this preset** — User asks: "generate slides from this checklist
> / .md / reference doc, exhaustive, technical, corporate-friendly". Mandate:
> "1000 slides OK if needed". The reader is an engineer, not a stakeholder.

---

## Frozen Phase 1 answers

| Field | Value |
|------|-------|
| Purpose | Teaching / Tutorial reference (single source of truth for the topic) |
| Length | Long (typically 80–200 slides) — never collapse content to save count |
| Content source | Pre-existing Markdown file with `<!-- SLIDE_BRIEF ... -->` block at top |
| Inline editing | **No** — keep the file lean, ship as static deliverable |
| Images | None — all visuals via inline SVG (no external assets) |

---

## Frozen Phase 2 answers — visual identity

### Palette (dark mode aerospace sober)

```css
:root {
    --bg-primary:        #1F1F1F;   /* charcoal */
    --bg-surface:        #2A2A2A;   /* card / panel */
    --bg-surface-2:      #333333;   /* table header */
    --border:            #3A3A3A;
    --border-soft:       #2F2F2F;
    --text-primary:      #F0F0F0;
    --text-secondary:    #B5B5B5;
    --text-muted:        #888888;
    --accent-navy:       #6BAEDF;   /* titles, info, links */
    --accent-navy-dark:  #1F3A5F;   /* gradients only */
    --accent-orange:     #E87C5C;   /* warnings, anti-patterns */
    --accent-orange-dark:#C44A1F;
    --accent-green:      #5BB585;   /* do-this, gates, validations */
    --accent-green-dark: #2E7D5B;
    --code-bg:           #181818;
}
```

### Typography

- **Body / titles:** IBM Plex Sans (300, 400, 500, 600, 700) via Google Fonts
- **Code / monospace:** IBM Plex Mono (400, 500)
- **Why IBM Plex:** corporate-grade, more distinctive than Inter, Apache 2.0
  licensed, Google-Fonts-hosted (no installation, fast CDN)

### Animation policy — **NONE**

- The `.reveal` class is a CSS no-op (`opacity: 1; transform: none; transition: none;`)
- Content appears immediately when a slide enters the viewport
- Rationale: staggered fade-ins introduced perceived latency on scroll;
  technical readers want immediate access to content

### Forbidden visual elements

- Emoji (anywhere in slides)
- Neon, fluorescent, oversaturated colors
- 3D effects, drop shadows beyond subtle elevation
- Stock photos, clipart, jupyter notebook screenshots
- "AI-generated" aesthetics: purple gradients, generic icons, glassmorphism

### Acceptable badges (text-only with border)

```html
<span class="badge info">METHOD</span>
<span class="badge do">DO</span>
<span class="badge warn">WARN / WATCH / CRITICAL / MANDATORY / EXPENSIVE / LEGACY</span>
```

---

## Frozen Phase 3 — structure rules

### Slide count target

Aim for **80–200 slides per deck**. Density follows from the source:
- 1 slide per checklist row (e.g. items 4.1 to 4.14 → 14 slides)
- 1 slide per algorithm in a comparison table (do not collapse table rows)
- 1 slide per Mermaid diagram (full width, dedicated slide)
- 1 slide per code snippet (do not split a snippet across slides)
- 1 illustration SVG slide after each pedagogically critical concept

### Required slide types

| Type | When | Content |
|------|------|---------|
| **Cover** | First slide | Deck title (200 weight, large) + subtitle + `v X.Y.Z` + slide count + nav hint |
| **TOC** | Slide 1 | Card grid linking to each section |
| **Section intro** | Before each `## §N` block | Big section number (200 weight) + 1-sentence description + roadmap pills |
| **Checklist row** | Per item in a § table | Title = item name + badge, body = expanded bullets (`<ul class="bullet-list">`) |
| **Algorithm card** | Per algo in a tier list | Card grid (cols-2 or cols-3), each card with meta tag + title + body |
| **Code snippet** | When source contains a fenced block | One snippet per slide, manual syntax highlighting (`.kw`/`.str`/`.com`/`.num` spans) |
| **Mermaid** | Per source flowchart/sequence | Dedicated slide with `<div class="mermaid-host"><div class="mermaid">...</div></div>` |
| **SVG illustration** | After each critical concept | Inline SVG ~50–120 lines, viewBox `0 0 1100 380` typical |
| **Section recap** | Last slide of each § | 5–7 take-aways with do/warn class on `<li>` |
| **Closing** | Last 2–3 slides | Final recap, cross-references, resources |

### Content density per slide

| Slide type | Max content |
|-----------|-------------|
| Cover | 1 title + 1 subtitle + 1 meta line + 1 hint |
| TOC | 1 heading + ≤ 6 cards |
| Section intro | 1 huge number + 1 title + 1 lede + ≤ 14 pills |
| Checklist row | 1 title + 1 lede + ≤ 7 bullets |
| Algorithm card | 1 title + ≤ 4 cards (cols-2) or ≤ 6 cards (cols-3) |
| Code snippet | 1 title + ≤ 18 lines of code |
| Mermaid | 1 title + 1 diagram (full host) |
| SVG illustration | 1 title + 1 SVG + 1 caption |
| Recap | 1 title + ≤ 7 bullets |

If content exceeds the limit → split into 2 or 3 slides (e.g. "Vocabulary 1/2",
"Vocabulary 2/2"). **Never cram, never scroll.**

---

## Phase 3 — required HTML scaffold

### Mermaid setup (CRITICAL — defeats the cropping bug)

```javascript
mermaid.initialize({
    startOnLoad: false,
    theme: 'dark',
    themeVariables: { /* match palette */ },
    flowchart: { htmlLabels: true, curve: 'basis', useMaxWidth: false },
});

function fitOneSVG(svg) {
    const host = svg.closest('.mermaid-host');
    if (!host) return;
    try {
        const bbox = svg.getBBox();
        if (bbox.width > 0 && bbox.height > 0) {
            const pad = 12;
            svg.setAttribute('viewBox',
                `${bbox.x - pad} ${bbox.y - pad} ${bbox.width + 2*pad} ${bbox.height + 2*pad}`);
        }
    } catch (e) {}
    svg.removeAttribute('width');
    svg.removeAttribute('height');
    svg.setAttribute('preserveAspectRatio', 'xMidYMid meet');
    svg.style.display = 'block';
    const r = host.getBoundingClientRect();
    const cs = getComputedStyle(host);
    const padX = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
    const padY = parseFloat(cs.paddingTop) + parseFloat(cs.paddingBottom);
    const availW = r.width - padX, availH = r.height - padY;
    if (availW <= 0 || availH <= 0) return;
    const vb = (svg.getAttribute('viewBox') || '0 0 1 1').split(/\s+/).map(Number);
    const ratio = (vb[2] || 1) / (vb[3] || 1);
    let w = availW, h = availW / ratio;
    if (h > availH) { h = availH; w = availH * ratio; }
    svg.style.width = Math.floor(w) + 'px';
    svg.style.height = Math.floor(h) + 'px';
    svg.style.maxWidth = 'none';
    svg.style.maxHeight = 'none';
}

async function fitMermaidSVGs() {
    await mermaid.run({ querySelector: '.mermaid' });
    await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)));
    document.querySelectorAll('.mermaid-host svg').forEach(fitOneSVG);
}

let _fitDebounce;
window.addEventListener('resize', () => {
    clearTimeout(_fitDebounce);
    _fitDebounce = setTimeout(() =>
        document.querySelectorAll('.mermaid-host svg').forEach(fitOneSVG), 120);
});

document.addEventListener('DOMContentLoaded', async () => {
    await fitMermaidSVGs();
    new SlidePresentation();
});
```

This three-mechanism stack defeats Mermaid 10's intrinsic sizing:
1. `getBBox()` recompute → viewBox always encloses all content (foreignObjects too)
2. Strip inline `width`/`height` attributes Mermaid stamps on the SVG
3. Compute pixel size from container box, preserving aspect ratio
4. Re-fit on resize (fullscreen toggle, window resize)

### Navigation class (SlidePresentation)

Required JS controller — see existing implementation for full code:
- Keyboard: `←/→/↑/↓/Space/PgUp/PgDn/Home/End/F` (fullscreen)
- Touch: vertical swipe ≥ 50 px
- IntersectionObserver to track current slide
- Progress bar at top (gradient navy → green)
- Slide number bottom-right (`NNN / TOTAL`)
- URL hash `#sN` for direct linking

### Viewport-fit CSS (mandatory base)

Include the FULL contents of `viewport-base.css` from this skill — it locks
each `.slide` to `100vh / 100dvh` and uses `clamp()` everywhere for responsive
scaling. Do not skip this step.

### `.reveal` no-op rule (mandatory for this preset)

```css
/* Per Exhaustive Technical preset: animations removed for snappier scroll. */
.reveal { opacity: 1; transform: none; transition: none; }
```

---

## SLIDE_BRIEF block — required source-file header

Every Markdown source for this preset must begin with a YAML-style HTML comment
that drives the generation:

```markdown
<!--
SLIDE_BRIEF
=================================================================
deck_id: NN_topic_name
audience: <one line — who reads this>
goal: <2-3 lines — what the deck must achieve, scope, exhaustivity mandate>

style:
  - corporate / aerospace sober palette (charcoal + navy/orange/green)
  - IBM Plex Sans + IBM Plex Mono
  - no emoji, no neon, no animation
  - max 7 bullets per slide; if more, split

structure:
  - cover + TOC + section intros + per-row slides + recap + closing
  - per checklist row: ONE slide
  - per algorithm: ONE comparison + ONE "when to use"
  - per Mermaid: ONE full-width slide
  - per code snippet: ONE slide

avoid:
  - any project-specific reference (substitute neutral terms)

output: slides/NN_topic_name.html (single self-contained file)
=================================================================
-->

# Topic title

Body of the source markdown follows...
```

---

## SVG illustrations — required at pedagogically critical concepts

Every concept where a picture clarifies more than text gets a dedicated
illustration slide. Patterns to follow:

| Concept | Illustration type | Approx viewBox |
|---------|------------------|----------------|
| Loss curves (over/under/sweet) | 3 mini-charts side-by-side | `0 0 1200 380` |
| Bias-variance tradeoff | U-curve with shaded zones | `0 0 900 420` |
| Loss landscape with multi-init | Wavy curve + N starting points | `0 0 900 420` |
| Confusion matrix | 2×2 colored grid + side metrics | `0 0 900 460` |
| ROC vs PR comparison | Two charts side-by-side | `0 0 1100 420` |
| Calibration curves | Diagonal + 2 bowed curves | `0 0 900 420` |
| Causal DAG patterns | Node-edge diagrams (3 panels) | `0 0 1100 380` |
| Scree + cumulative variance | Bar chart + line chart | `0 0 1100 400` |
| Reduction algos comparison | 3 scatter mini-panels | `0 0 1200 380` |
| K-Means iterations | 4 frames init → converged | `0 0 1200 360` |
| Silhouette plot | Horizontal bars per cluster | `0 0 1000 380` |
| Convolution operation | Input + kernel + output cells | `0 0 1100 380` |
| Sliding window | Signal + colored windows | `0 0 1100 380` |
| Time-domain → FFT | Two charts with arrow between | `0 0 1100 360` |
| Probabilistic forecast | Line + confidence ribbon | `0 0 1000 380` |

Each SVG:
- Inline (no external `src=`)
- Wrapped in `<div style="flex:1; min-height:0; display:flex; align-items:center; justify-content:center;">`
- `style="width:100%; height:100%; max-height:62vh;"` on the `<svg>`
- Title above, optional caption below in `<p style="text-align:center; font-size:var(--small-size); color:var(--text-muted);">`
- Use palette CSS variables hardcoded (SVG can't read CSS vars from parent — copy hex values)
- Define arrow markers in `<defs>` once per SVG: `<marker id="arr" ...>`

---

## Generation workflow with this preset

Skip Phases 1 and 2 of the standard skill. Execute directly:

1. **Read** the source `.md` file end-to-end (ensure the `SLIDE_BRIEF` block is present).
2. **Plan** the slide breakdown from the source's table of contents — count expected slides.
3. **Generate** the HTML skeleton with the frozen palette + typography + viewport CSS + Mermaid setup + SlidePresentation JS.
4. **Insert slides in batches via Edit** — use unique `<!-- ===== SLIDE NN — name ===== -->` comments as anchors. Do not write the entire file in one call (too large for a single Write).
5. **Add SVG illustrations** at every pedagogically critical concept (use the table above).
6. **Verify** with: HTML parser, slide count, no project-specific references (`grep -ciE "(|<your CNC>|<your organization>|...)"` should return 0 — substitute with neutral terms like "the edge device", "the time-series store", "the PLC reader").

---

## Pre-flight checklist before delivering

- [ ] HTML parses (`python3 -c "from html.parser import HTMLParser; HTMLParser().feed(open('out.html').read())"`)
- [ ] Slide count matches the planned breakdown (`grep -c '<section class="slide'`)
- [ ] Zero project-specific terms in output
- [ ] Mermaid `fitOneSVG`/`fitMermaidSVGs` present and called from `DOMContentLoaded`
- [ ] `.reveal` rule is no-op (no staggered animations)
- [ ] Viewport-base CSS included in full
- [ ] All SVG illustrations use viewBox + `preserveAspectRatio` (no fixed pixel dimensions)
- [ ] `prefers-reduced-motion` respected (already in viewport-base.css)
- [ ] Hard-reload test confirmed all 4 Mermaid diagrams render full (no crop)

---

## Reference deliverable

The project's `slides/03_model_training.html` (170 slides, 273 KB,
4 600 lines) is the canonical reference for this preset. Inspect it as the
source of truth when in doubt about layout or styling decisions.
