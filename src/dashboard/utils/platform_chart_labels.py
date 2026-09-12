"""Les étiquettes de valeur posées sur les aires de la figure des plateformes.

Type: Utility
Uses: plotly
Depends on: src/dashboard/utils/platform_chart.py (appelant)
Persists in: nothing

Extrait de `platform_chart.py` le 2026-09-13, quand ce dernier a franchi 1 200 lignes
et que `test_a_file_only_gets_shorter` l'a signalé. Le découpage suit une couture
réelle : poser un texte sur une aire ne demande rien de ce que sait le reste du module
— ni les seaux, ni les trous, ni les modes d'agrégation — seulement les séries déjà
alignées et la palette.
"""
from __future__ import annotations


def annotate_series(fig, span: list, aligned: dict, order: list, palette: dict,
                    surface: str, mode: str) -> None:
    """UNE étiquette par plateforme, dans sa couleur, sur la hauteur de sa bande.

    « peux-tu ajouter des valeurs étiquettes pertinentes vers le max ou la dernière
    valeur obtenue dans la couleur adéquate » (2026-09-12).

    LAQUELLE DES DEUX, ET LE MODE TRANCHE :

    * en CUMULÉ, la courbe ne fait que monter — son maximum EST son dernier point.
      Étiqueter « le max » y répéterait la fin de la courbe ; on étiquette donc la
      dernière valeur, qui est le total de la période ;
    * en PAR PÉRIODE, la dernière valeur est le dernier seau, souvent partiel et
      rarement intéressant. C'est le PIC qui répond à la question qu'on se pose
      devant la courbe — « c'était quand, le meilleur moment ? ».

    UNE SEULE PAR PLATEFORME. Étiqueter chaque point ferait un mur de chiffres sur
    une courbe de 44 points, et l'infobulle les donne déjà tous.

    ⚠️ LA COULEUR EST CELLE DE LA PALETTE, jamais une couleur choisie ici. Les
    couleurs de cette figure ont été mesurées en deutéranopie le 2026-09-12 : en
    réécrire une à l'œil défait ce travail en silence.

    LES AIRES SONT EMPILÉES, donc l'étiquette se pose sur le CUMUL des plateformes
    sous elle — la hauteur réelle de la bande à l'écran. La poser sur la valeur brute
    la mettrait à l'intérieur de la pile, sur une autre couleur.
    """
    stack = [0.0] * len(span)
    for pkey in order:
        vals = aligned.get(pkey) or []
        best_i, best_v = None, None
        for i in range(min(len(vals), len(span))):
            v = vals[i]
            if v is None:
                continue
            if mode == "cumulative":
                best_i, best_v = i, v          # la dernière mesure connue
            elif best_v is None or v > best_v:
                best_i, best_v = i, v          # le pic de la période
        for i in range(min(len(vals), len(span))):
            stack[i] += (vals[i] or 0)
        if best_i is None or not best_v:
            continue
        fig.add_annotation(
            x=span[best_i], y=stack[best_i],
            text=f"<b>{int(round(best_v)):,}</b>".replace(",", " "),
            showarrow=False, yshift=9,
            font=dict(size=11, color=palette[pkey]),
            # Un fond opaque : sur une aire pleine de la même teinte, un chiffre
            # sans fond devient illisible dès que la bande est haute.
            bgcolor=surface, borderpad=2, opacity=0.92)
