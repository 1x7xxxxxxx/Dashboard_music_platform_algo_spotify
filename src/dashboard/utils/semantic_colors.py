"""Les couleurs qui veulent dire quelque chose — bon, mauvais, attention, neutre.

Type: Utility
Uses: src/dashboard/utils/colorimetry (pour le garde, pas à l'exécution)
Depends on: rien
Persists in: nothing

Pourquoi ce module existe
-------------------------
Mesuré le 2026-09-17 : la paire dominante du parc de figures est **vert `#1DB954`
contre un rouge**, c'est-à-dire « bon/mauvais » encodé en TEINTE SEULE. C'est le canal
que la deuteranopie détruit — 8 % des hommes. Écrire `marker_color="#1DB954"` à la main
est le geste qui produit ça, et il le produira encore tant qu'il n'y a rien d'autre à
saisir. Ce module est ce qu'on saisit à la place :

    from src.dashboard.utils.semantic_colors import BON, MAUVAIS
    fig.add_trace(go.Bar(..., marker_color=BON))
    fig.add_trace(go.Bar(..., marker_color=MAUVAIS))

⚠️ **LE CHIFFRE QUI RÉSUME TOUT R133.** `#a32929` — un rouge parfaitement ordinaire —
contre `#27751a` — un vert parfaitement ordinaire — est à **ΔE 1,6** en deuteranopie.
Balayage par clarté et par saturation, le 2026-09-18 : un rouge dont la clarté est celle
du vert échoue à TOUTES les saturations (60 %, 75 %, 90 %). Il ne devient attribuable
qu'en s'éloignant en CLARTÉ — plus sombre que L* 24, ou plus clair que L* 59.

    L* 37  #a32929  ΔE  1,6      L* 65  #e08585  ΔE 23,1
    L* 41  #b82e2e  ΔE  3,4      L* 70  #e69999  ΔE 27,3
    L* 46  #cc3333  ΔE  8,6      L* 22  #661919  ΔE 15,2

**La séparation ne vient donc pas de la teinte. Elle vient de la clarté.** « Prendre un
rouge plus rouge » ne marche pas, et c'est exactement ce qui a été essayé le 2026-09-08
sur la palette de plateformes : les couleurs de marque EXACTES étaient à ΔE 4,6.

Comment ces quatre-là ont été obtenues
--------------------------------------
Par mesure, pas par goût — la règle du dépôt est qu'une palette se mesure. Balayage HSL
(teinte × clarté × saturation) contraint de trois façons : la bande de clarté du mode
clair (0,43–0,77), les familles de TEINTE que le sens impose (`bon` vert, `mauvais`
rouge, `attention` ambre, `neutre` ardoise), et le plancher de 15 sur les six paires en
vision normale, deuteranopie ET protanopie.

⚠️ **L'optimum brut a été REFUSÉ, et le refus est chiffré.** Maximiser la pire paire
pousse `mauvais` à `#f4d7da`, L* 88,4 — un rose quasi blanc, qui lirait comme un fond.
Pire paire 27,5 contre 18,2 pour le choix retenu : **on paie 9,3 de marge pour que
`MAUVAIS` lise encore comme un rouge.** C'est une décision de sens, pas une contrainte,
et elle est écrite ici pour pouvoir être contredite.

Les six paires du choix retenu, pire cas des trois visions :

    bon ↔ mauvais    20,1        mauvais ↔ attention  18,2   ← la pire
    bon ↔ attention  26,2        mauvais ↔ neutre     27,9
    bon ↔ neutre     39,3        attention ↔ neutre   53,5

⚠️ **Ce module ne migre rien.** `code-critic` a rendu BUILD-MODIFIED sur R133 avec cette
condition explicite : ne pas migrer les figures existantes en une passe. Les 19 figures
sous le plancher sont un plafond enregistré dans
`.claude/dev-docs/figure-contrast-baseline.json`, et la porte dure ne porte que sur ce
qui est neuf — `tests/test_a_new_figure_can_be_attributed.py`.

⚠️ **`ATTENTION` a d'abord été écrit hors de sa propre contrainte.** Le premier jet le
posait à `#e9bc0c`, L* 78,1 — au-dessus de la bande 43–77 que ce module déclare pourtant
appliquer trois paragraphes plus haut. Trouvé en RELISANT la valeur contre la règle
écrite juste à côté, pas par un garde. `test_semantic_colours_are_attributable.py`
vérifie désormais la bande AUSSI, pour que la prochaine fois ce ne soit pas une relecture
qui l'attrape. Le meilleur ambre dans la bande est `#f8b10d` (L* 76,9) et coûte 0,4 de
pire paire — 18,2 au lieu de 18,6.

⚠️ **Ces couleurs n'ont PAS été mesurées pour le mode sombre.** La bande de clarté y est
plus étroite (0,48–0,67) et le maximum atteignable pour quatre teintes chaudes y est
**13,9**, sous le plancher de 15 — une borne mesurée le 2026-09-12, pas un oubli. Un
usage en mode sombre demande sa propre mesure.
"""
from __future__ import annotations

# ── Le couple central, séparé par la CLARTÉ et non par la teinte ──────────────
BON = "#27751a"        # vert profond   — L* 43,1
MAUVAIS = "#ec7979"    # rouge clair    — L* 64,1   (ΔE 20,1 contre BON)

# ── Les deux autres termes ────────────────────────────────────────────────────
ATTENTION = "#f8b10d"  # ambre          — L* 76,9
NEUTRE = "#496983"     # ardoise        — L* 43,0

#: Toutes les couleurs sémantiques — c'est ce que le garde mesure, paire par paire.
SEMANTIQUES = {"bon": BON, "mauvais": MAUVAIS, "attention": ATTENTION, "neutre": NEUTRE}

#: Le plancher d'attribution du dépôt, en CIEDE2000, mode clair.
PLANCHER = 15.0

#: La bande de clarté du mode clair, reprise de la palette de plateformes.
BANDE_CLARTE = (0.43, 0.77)
