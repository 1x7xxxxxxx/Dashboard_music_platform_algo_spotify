"""La couleur d'une plateforme — UNE définition, pour toute l'application.

Type: Utility
Uses: rien à l'exécution (src/dashboard/utils/colorimetry pour le garde)
Depends on: rien
Persists in: nothing

Pourquoi ce module existe
-------------------------
La palette mesurée vivait dans `platform_chart.py`, à l'intérieur du module qui
dessine UNE figure. Toute autre surface écrivait donc ses couleurs à la main, et
le dépôt en portait la trace : `#1DB954` — le vert de marque Spotify, celui que la
mesure du 2026-09-08 a précisément REFUSÉ — est écrit en dur dans **14 fichiers**,
dont `meta_x_spotify.py`, `revenue_forecast.py` et `data_wrapped.py`.

Une couleur recopiée n'est pas un défaut de style : c'est une définition qui
diverge. Le vert « Spotify » de l'accueil et celui d'une autre page ne sont pas le
même vert, et un artiste qui passe de l'une à l'autre n'a aucune raison de
comprendre que les deux parlent de la même plateforme.

Ce module est ce qu'on importe à la place :

    from src.dashboard.utils.platform_colors import platform_color
    fig.add_trace(go.Scatter(..., line=dict(color=platform_color("spotify"))))

⚠️ **Ce module ne migre rien.** C'est la même condition que `semantic_colors` a
reçue de `code-critic` : migrer d'un coup les figures existantes est un changement
que personne ne peut relire. Les quatorze sites en dur restent en dur ; ce qui est
NEUF passe par ici.

La mesure — reprise telle quelle, et ce que META y ajoute
----------------------------------------------------------
Les quatre premières couleurs viennent du balayage du 2026-09-08/12 sur ~1,7 M de
combinaisons, sous les contraintes du validateur (CIEDE2000 + simulation
deutan/protan de Viénot/Brettel, bande de clarté par thème). Elles sont déplacées
ici SANS une valeur modifiée, pour que `tests/test_the_palette_can_be_attributed.py`
reste exactement le même garde.

**META a été mesurée le 2026-09-21, et le résultat est contre-intuitif : sa couleur
de MARQUE passe.** `#0866ff` tient le plancher de 15 en clair (pire paire **15,3**,
`apple ↔ meta` en deutéranopie). C'est l'inverse de ce qui était arrivé aux quatre
premières, dont les teintes de marque exactes étaient à ΔE 4,6 — et la raison est
simple : les quatre occupent l'arc chaud (vert, rouge, orange, magenta), le bleu
était LIBRE. Une famille de teinte inoccupée ne coûte rien à personne.

⚠️ **L'optimum brut a été refusé ici aussi, et le refus est chiffré.** Le balayage
rend `#a6c1dd` (pire paire 16,9) — un bleu pâle délavé qui ne lit pas comme Meta,
exactement le piège que `semantic_colors` documente pour `MAUVAIS` (`#f4d7da`,
refusé). **On paie 1,6 de marge pour que META lise comme META.**

⚠️ **En mode sombre, META ne coûte RIEN.** La pire paire de la palette sombre était
**13,9** (`soundcloud ↔ youtube`, la borne mesurée le 2026-09-12) ; avec META à
`#0171fe` elle reste **13,9** — la même paire, le même nombre. Ajouter une teinte
n'a pas dégradé la palette parce que la contrainte vivante est ailleurs. HYPEDDIT,
ajoutée le même jour, ne coûte rien non plus : les pires paires restent 15,3 en
clair et 13,9 en sombre, inchangées.

INSTAGRAM N'A PAS DE COULEUR, ET C'EST UNE BORNE MESURÉE
---------------------------------------------------------
⚠️ **Sept teintes attribuables sont IMPOSSIBLES dans cette palette.** Recherche
CONJOINTE du 2026-09-21 sur le couple (cyan Hypeddit, violet Instagram), les cinq
autres fixées — le meilleur couple atteignable rend :

    clair   ΔE  9,6   contre un plancher de 15,0
    sombre  ΔE 12,8   contre un plancher de 13,5

La paire qui bloque est `hypeddit ↔ instagram` en **deutéranopie**, et la raison
est structurelle, pas un manque de recherche : la deutéranopie efface l'axe
rouge-vert, donc un cyan et un violet y convergent tous deux vers le même bleu.
Aucune position de l'une ou l'autre famille n'y échappe.

⚠️ **Et cette borne a failli m'échapper.** J'ai d'abord mesuré chaque encre neuve
contre les cinq existantes, jamais les deux neuves **entre elles** : le couple
`#3fb8cc` / `#bb8ffa` sortait à 8,9 en deutan avec les deux « validées »
séparément. Une palette se mesure par PAIRES, toutes les paires, et une mesure
séquentielle n'est pas une mesure conjointe.

Conséquence assumée : Instagram n'entre pas dans ce module. Là où sa donnée est
utile — les abonnés du compte — elle s'affiche en CHIFFRE et non en courbe, ce qui
est de toute façon plus honnête : un compteur d'abonnés du compte entier ne
s'attribue pas à une campagne.
"""
from __future__ import annotations

# ── Mode clair — plancher 15,0 · bande de clarté 0,43–0,77 ────────────────────
PALETTE_LIGHT: dict[str, str] = {
    "spotify": "#3acf84",
    "youtube": "#bd354b",
    "soundcloud": "#e0631b",
    "apple": "#bd00a4",
    # META, mesurée le 2026-09-21. Sa teinte de marque (#0866FF), L* 0,48.
    "meta": "#0866ff",
    # HYPEDDIT, mesurée le 2026-09-21. Famille CYAN — une teinte libre, comme le
    # bleu de Meta l'était. Pire paire 18,1 (contre le magenta d'Apple).
    # L'optimum brut est `#9bc5cf` (26,4), et il est refusé pour la raison
    # habituelle de ce dépôt : L* 0,77, le haut de la bande, un cyan délavé qui
    # lit comme un fond. **On paie 8,3 de marge pour que ce soit un cyan.**
    "hypeddit": "#3fb8cc",
}

# ── Mode sombre — plancher 13,5 · bande de clarté 0,48–0,67 ───────────────────
PALETTE_DARK: dict[str, str] = {
    "spotify": "#268756",
    "youtube": "#e01b2b",
    "soundcloud": "#f28100",
    "apple": "#cf19b6",
    "meta": "#0171fe",
    "hypeddit": "#5db1a5",
}

#: Les planchers et les bandes, lus par le garde. Leur écart est expliqué dans
#: `tests/test_the_palette_can_be_attributed.py` : 15 en sombre serait un plancher
#: que rien ne peut franchir, donc un garde rouge à vie, donc ignoré.
FLOOR_LIGHT, FLOOR_DARK = 15.0, 13.5
BAND_LIGHT, BAND_DARK = (0.43, 0.77), (0.48, 0.67)


def platform_color(platform: str, *, dark: bool = False, default: str | None = None) -> str:
    """La couleur de `platform`, dans le thème demandé.

    `default` est rendu pour une plateforme SANS couleur mesurée — Instagram et
    Hypeddit aujourd'hui. Il vaut mieux une couleur neutre assumée qu'une teinte
    choisie au jugé : le balayage du 2026-09-21 a montré qu'aucune position de la
    famille violet/rose ne tient le plancher à côté du magenta d'Apple, et
    inventer une couleur pour le cacher est ce que ce module existe pour empêcher.
    """
    pal = PALETTE_DARK if dark else PALETTE_LIGHT
    if platform in pal:
        return pal[platform]
    if default is not None:
        return default
    raise KeyError(
        f"'{platform}' n'a pas de couleur mesurée. Les plateformes mesurées sont "
        f"{sorted(pal)}. Ajouter une teinte demande un balayage sous le plancher "
        f"(voir le docstring), pas un choix — passe `default=` en attendant.")
