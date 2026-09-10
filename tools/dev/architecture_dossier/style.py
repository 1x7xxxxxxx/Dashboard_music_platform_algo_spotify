CSS = """
@page {
  size: A4; margin: 18mm 16mm 20mm 16mm;
  @bottom-center { content: counter(page) " / " counter(pages);
    font: 8pt Helvetica, Arial, sans-serif; color: #9a9a97; }
  @bottom-left { content: "streaMLytics — architecture et qualité des données";
    font: 8pt Helvetica, Arial, sans-serif; color: #c0c0bc; }
}
@page :first { @bottom-center { content: ""; } @bottom-left { content: ""; } }

* { box-sizing: border-box; }
body { font: 10.2pt/1.55 Helvetica, Arial, sans-serif; color: #1a1a19; margin: 0; }

h1 { font-size: 21pt; line-height: 1.15; margin: 0 0 4mm; letter-spacing: -.3pt; }
h2 { font-size: 14pt; margin: 9mm 0 3mm; padding-bottom: 1.5mm;
     border-bottom: 2px solid #2a78d6; break-after: avoid; letter-spacing: -.2pt; }
h3 { font-size: 11.2pt; margin: 6mm 0 2mm; color: #2a78d6; break-after: avoid; }
h4 { font-size: 10pt; margin: 4mm 0 1.5mm; color: #1a1a19; break-after: avoid; }
p  { margin: 0 0 2.6mm; }
ul, ol { margin: 0 0 2.6mm; padding-left: 5mm; }
li { margin-bottom: 1.2mm; }
strong { font-weight: 700; }
code { font: 8.8pt "DejaVu Sans Mono", monospace; background: #f4f4f1;
       padding: .3mm 1mm; border-radius: 1mm; }

/* ── Couverture ────────────────────────────────────────────────── */
.cover { height: 245mm; display: flex; flex-direction: column; justify-content: center; }
.cover .kicker { font-size: 9pt; letter-spacing: 2pt; text-transform: uppercase;
                 color: #6b6b68; margin-bottom: 6mm; }
.cover h1 { font-size: 30pt; line-height: 1.08; margin-bottom: 6mm; }
.cover .sub { font-size: 12pt; color: #6b6b68; line-height: 1.5; max-width: 130mm; }
.cover .meta { margin-top: 14mm; font-size: 9pt; color: #9a9a97;
               border-top: 1px solid #d8d8d4; padding-top: 3mm; }
.band { display: flex; margin: 8mm 0 0; height: 4mm; }
.band i { flex: 1; }

/* ── Figures ───────────────────────────────────────────────────── */
.fig { margin: 4mm 0 5mm; text-align: center; break-inside: avoid; }
.fig svg { max-width: 100%; height: auto; }
.caption { font-size: 8.4pt; color: #6b6b68; margin: -3mm 0 5mm; text-align: center;
           font-style: italic; }

/* ── Tableaux ──────────────────────────────────────────────────── */
/* Les tableaux longs se RÉPARTISSENT : les interdire de couper laissait des
   demi-pages vides. Les lignes, elles, restent insécables. */
table { width: 100%; border-collapse: collapse; margin: 3mm 0 5mm; font-size: 8.9pt; }
thead { display: table-header-group; }
tr { break-inside: avoid; }
th { text-align: left; background: #f4f4f1; font-weight: 700; font-size: 8.4pt;
     text-transform: uppercase; letter-spacing: .3pt; color: #4a4a47; }
th, td { border: 1px solid #e2e2de; padding: 1.6mm 2mm; vertical-align: top; }
tbody tr:nth-child(even) { background: #fbfbf9; }
td.num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }

/* ── Encadrés ──────────────────────────────────────────────────── */
.box { border-left: 3px solid #2a78d6; background: #f7fafd; padding: 3mm 4mm;
       margin: 4mm 0; break-inside: avoid; }
.box.warn { border-left-color: #eb6834; background: #fef6f2; }
.box.ok   { border-left-color: #1baf7a; background: #f2fbf7; }
.box.key  { border-left-color: #eda100; background: #fdf9ef; }
.box .lbl { font-size: 8pt; text-transform: uppercase; letter-spacing: 1pt;
            color: #6b6b68; margin-bottom: 1.5mm; font-weight: 700; }
.box p:last-child { margin-bottom: 0; }

/* ── Chiffres marquants ────────────────────────────────────────── */
.stats { display: flex; gap: 3mm; margin: 4mm 0 5mm; break-inside: avoid; }
.stat { flex: 1; border: 1px solid #e2e2de; border-top: 3px solid #2a78d6;
        padding: 2.5mm 3mm; background: #fbfbf9; }
.stat .v { font-size: 15pt; font-weight: 700; line-height: 1.1;
           font-variant-numeric: tabular-nums; }
.stat .k { font-size: 7.8pt; color: #6b6b68; line-height: 1.35; margin-top: 1mm; }
.stat.bad  { border-top-color: #eb6834; } .stat.bad .v  { color: #eb6834; }
.stat.good { border-top-color: #1baf7a; } .stat.good .v { color: #1baf7a; }

.pill { display: inline-block; font-size: 7.6pt; font-weight: 700; padding: .4mm 1.6mm;
        border-radius: 1mm; letter-spacing: .2pt; }
.pill.b { background: #f0e6d8; color: #7a5a2a; }
.pill.s { background: #e6ecf2; color: #3d5a72; }
.pill.g { background: #fdf1d6; color: #8a6410; }

.quad { margin: 4mm 0 6mm; break-inside: avoid; }
.qgrid { display: grid; grid-template-columns: 1fr 1fr; grid-template-rows: 46mm 40mm;
         border: 1px solid #c8c8c4; }
.qcell { position: relative; border: .5px solid #e2e2de; }
.q2 { background: #f2f8fd; } .q1 { background: #fdf9ef; }
.q3 { background: #fbfbf9; } .q4 { background: #fdf5f1; }
.qlbl { position: absolute; top: 2mm; left: 0; right: 0; text-align: center;
        font-size: 8pt; font-weight: 700; letter-spacing: .3pt; color: #6b6b68;
        text-transform: uppercase; }
.qi { position: absolute; font-size: 8.4pt; line-height: 1.25; max-width: 62%;
      padding-left: 3mm; color: #1a1a19; }
.qi::before { content: "●"; position: absolute; left: 0; top: -.2mm;
              font-size: 6pt; color: #2a78d6; }
.q1 .qi::before { color: #eda100; } .q3 .qi::before { color: #9a9a97; }
.q4 .qi::before { color: #eb6834; }
.qaxis { display: flex; justify-content: space-between; font-size: 8pt; color: #9a9a97;
         margin-top: 1.5mm; }
/* Pas de `writing-mode` : WeasyPrint le rend en miroir. Les libellés d'axe
   vertical sont donc posés à plat, au-dessus et au-dessous de la grille. */
.qtop, .qbot { font-size: 8pt; color: #9a9a97; letter-spacing: .2pt; }
.qtop { margin-bottom: 1mm; } .qbot { margin-top: 1mm; }

/* Frise horaire, décalée par MARGE et non par `left` : WeasyPrint ne résout pas
   `position:absolute; left:%` à l'intérieur d'un élément de ligne, et tous les
   repères se retrouvaient empilés à l'origine. */
.tl { margin: 4mm 0 6mm; break-inside: avoid; }
.trow { display: flex; align-items: baseline; height: 5.6mm; }
.tname { width: 40mm; min-width: 40mm; font-size: 8.6pt; text-align: right;
         padding-right: 3mm; white-space: nowrap; }
.ttrack { flex: 1; border-bottom: .5px dotted #ebebe7; padding-bottom: 1mm; }
.tmark { font-size: 7.8pt; color: #4a4a47; white-space: nowrap; }
.tmark i { display: inline-block; width: 2.2mm; height: 2.2mm; border-radius: 50%;
           margin-right: 1.2mm; }
.taxis .ttrack { border-bottom: 1px solid #d8d8d4; }
.ttick { font-size: 7.6pt; color: #9a9a97; white-space: nowrap; }
.tmark.col i, .tleg .col::before { background: #2a78d6; }
.tmark.cal i, .tleg .cal::before { background: #1baf7a; }
.tmark.rel i, .tleg .rel::before { background: #eda100; }
.tmark.sur i, .tleg .sur::before { background: #eb6834; }
.tleg { margin: 2.5mm 0 0 40mm; font-size: 7.8pt; color: #6b6b68; }
.tleg span { margin-right: 5mm; }
.tleg span::before { content: ""; display: inline-block; width: 2.2mm; height: 2.2mm;
                     border-radius: 50%; margin-right: 1.2mm; }

.newpage { break-before: page; }
.tight { margin-top: -1mm; }
.lead { font-size: 11pt; color: #4a4a47; margin-bottom: 4mm; }

/* ── Sommaire ──────────────────────────────────────────────────── */
.toc ol { list-style: none; padding-left: 0; counter-reset: s; }
.toc li { counter-increment: s; padding: 1.1mm 0; border-bottom: 1px dotted #e2e2de;
          font-size: 9.6pt; }
.toc li::before { content: counter(s) ". "; color: #2a78d6; font-weight: 700; }
.toc li .d { color: #6b6b68; font-size: 8.6pt; display: block; padding-left: 5mm; }
"""
