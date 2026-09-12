"""Comment la figure dit qu'elle n'a PAS mesuré — le vocabulaire de l'absence.

Type: Sub
Uses: plotly.graph_objects, i18n.t
Depends on: rien du dépôt (aucune base, aucun Streamlit)
Persists in: nothing

Pourquoi ce module existe
-------------------------
`platform_chart.py` a franchi 1 200 lignes en gagnant deux surfaces d'absence de
plus le 2026-09-12, et le cliquet `tests/test_a_file_only_gets_shorter.py` a refusé
— « les ajouter à FROZEN fige la dette ; les découper la retire ». Il a eu raison
deux fois dans la même séance : c'est déjà lui qui avait fait sortir `_NAV_SECTIONS`
d'`app.py`.

Le découpage n'est pas arbitraire. Ces sept fonctions répondent toutes à UNE
question — *que sait-on, et que ne sait-on pas ?* — et elles sont l'obsession de ce
dépôt :

* `known` distingue les trois absences (avant la 1ʳᵉ mesure, entre deux, après la
  dernière) ; elle décide où la bande se coupe, et c'est la fonction la plus
  coûteuse à mal écrire de tout le module ;
* `unmeasured_spans` en dérive les intervalles à hachurer ;
* `_hatch_traces` les dessine, `_unmeasured_hover` les fait parler ;
* `_late_starts` et `_not_yet_collected_hover` portent le fait INDIVIDUEL — telle
  plateforme n'était pas encore collectée — que la hachure, pleine hauteur, ne peut
  pas porter sans mentir sur les autres.

Aucune ne touche à la base, à Streamlit ni au thème : elles prennent des listes et
rendent des listes ou des traces. C'est ce qui les rend testables seules, et c'est
pourquoi elles partent ensemble.

⚠️ `platform_chart` les RÉ-EXPORTE : `pdf_charts` appelle `pc.unmeasured_spans`, et
`tests/test_the_legend_says_what_the_figure_shows.py` vérifie que `pc` porte encore
`unmeasured_spans` et `_hatch_traces`. Un découpage qui casse ses appelants n'est
pas un découpage, c'est un déménagement à la charge des autres.
"""
from __future__ import annotations


def _measured_range(values: list) -> tuple:
    """(premier, dernier) index mesuré d'une série, ou `(None, None)`."""
    seen = [i for i, v in enumerate(values) if v is not None]
    return (seen[0], seen[-1]) if seen else (None, None)


def known(values: list, index: int) -> bool:
    """Sait-on ce que cette plateforme a fait ce jour-là ?

    Deux absences très différentes se ressemblent dans une liste de `None`, et les
    confondre coûtait tout l'historique :

    * **avant sa première mesure** — la plateforme n'était pas encore collectée. Elle
      n'a rien apporté à ce qu'on peut montrer, et 0 est la bonne valeur. Sans cette
      distinction, SoundCloud — collectée depuis le 2026-03-31 — coupait la bande sur
      les 1 142 jours de Spotify qui la précèdent, et « Depuis le début » n'affichait
      plus qu'une seule plateforme ;
    * **entre les deux** — un jour où la collecte n'a pas tourné. Là on ne sait pas, et
      la bande se coupe ;
    * **après la dernière mesure** — on ne sait pas non plus, et c'est le cas que cette
      fonction traitait comme le premier.

    Les deux extrémités ne sont PAS symétriques, et la version précédente les traitait
    du même argument. Avant la première mesure, zéro est vrai : la plateforme n'existait
    pas dans nos données. Après la dernière, la plateforme existe toujours — c'est NOUS
    qui avons cessé de la mesurer. Prouvé par exécution le 2026-09-10 : YouTube mesurée
    les 5 premiers jours d'une fenêtre de 20 donnait, en mode Cumulé (le défaut),

        cumulé  [10, 20, 30, 40, 50, None × 15]
        TRACÉ   [10, 20, 30, 40, 50,   0 × 15]   ← une seule tranche continue

    c'est-à-dire une bande qui monte puis **retombe à zéro** — « YouTube a perdu toutes
    ses écoutes ». En mode Par période, les mêmes jours étaient tracés `0` avec
    l'infobulle « compteur inchangé », qui affirme une mesure qu'on n'a pas faite.
    """
    first, last = _measured_range(values)
    if first is None:
        return False
    if index < first:
        return True
    if index > last:
        return False
    return values[index] is not None


def unmeasured_spans(aligned: dict, order: list) -> list:
    """Les intervalles d'indices où une plateforme DÉJÀ APPARUE n'a pas de mesure.

    C'est la réponse en PIXELS à « on ne voit pas la différence entre zéro et pas de
    donnée ». Jusqu'ici la bande se coupait — bien — mais `stackgroup` infère zéro
    pour la plateforme manquante, donc **le total empilé redescend** et se lit comme
    une chute. Le seul rattrapage était une phrase sous la figure.

    `known()` fait déjà la distinction qui compte : avant la première mesure d'une
    plateforme, zéro est vrai (elle n'existait pas dans nos données) ; entre deux
    mesures et après la dernière, on ne sait pas.

    ET LA PRÉHISTOIRE ? Elle n'est PAS ici, et deux mesures successives l'ont
    sortie de cette fonction — les deux valent d'être écrites, la seconde surtout.

    1. On a d'abord hachuré les pas antérieurs à la première mesure de CHAQUE
       plateforme, en union avec les trous. Mesuré sur l'artiste 1 avant livraison :
       SoundCloud démarrant le 2026-03-31, **1 185 jours sur 1 350** — 35 seaux sur
       42 au pas mois — passaient sous la hachure, dont les trois années où Spotify
       est mesurée chaque jour. Une hachure est pleine hauteur : elle affirme quelque
       chose de TOUTES les plateformes. L'unionner ainsi laissait une plateforme
       arrivée tard effacer l'historique d'une ancienne — exactement ce que `known()`
       avait été écrite pour empêcher.

    2. On a donc voulu l'intersection : ne hachurer que les pas où PERSONNE n'avait
       commencé. Elle ne peut jamais se produire. `_window` fait partir le `span` du
       premier jour mesuré **toutes plateformes confondues** (`all_days[0]`), donc au
       moins une plateforme a sa première mesure à l'indice 0, donc l'intersection
       est toujours vide. Le paramètre aurait été du code correct que rien n'atteint,
       la forme que ce dépôt paie le plus souvent — retiré au lieu d'être gardé.

    Ce que la hachure ne peut pas porter, deux surfaces le portent à sa place, et
    toutes deux PAR PLATEFORME : `_not_yet_collected_hover` au survol, et
    `render_collection_start_note` en toutes lettres sous la figure.

    Rend des intervalles FERMÉS `(début, fin)` sur les indices de `span`, fusionnés :
    trois jours manquants d'affilée font une bande, pas trois.
    """
    holes: set = set()
    for pkey in order:
        values = aligned.get(pkey) or []
        for i in range(len(values)):
            if not known(values, i):
                holes.add(i)
    holes = sorted(holes)
    if not holes:
        return []
    spans, start, prev = [], holes[0], holes[0]
    for i in holes[1:]:
        if i == prev + 1:
            prev = i
            continue
        spans.append((start, prev))
        start = prev = i
    spans.append((start, prev))
    return spans


def _hatch_traces(spans: list, span: list, ceiling: float, ink: str,
                  legend: bool = True) -> list:
    """Une trace hachurée par intervalle non mesuré, posée SOUS les aires.

    ⚠️ Pourquoi une trace et pas un `add_vrect` : une SHAPE Plotly ne supporte pas
    `fillpattern` — vérifié le 2026-09-12 sur la version de production (5.24.1) et en
    local (6.5.2). `Scatter.fillpattern`, lui, est supporté des deux côtés. Le
    rectangle est donc une trace fermée, hors `stackgroup` pour ne pas entrer dans la
    pile, et `hoverinfo="skip"` pour ne rien affirmer au survol.
    """
    import plotly.graph_objects as go      # paresseux, comme dans la figure

    from src.dashboard.utils.i18n import t
    label = t("platform_chart.unmeasured", "▨ Aucune mesure")
    out = []
    for n, (a, b) in enumerate(spans):
        # Le seau est élargi d'un demi-pas de chaque côté quand c'est possible : un
        # trou d'un seul jour doit rester visible, et un rectangle de largeur nulle
        # ne se voit pas.
        x0 = span[max(a - 1, 0)] if a > 0 else span[a]
        x1 = span[min(b + 1, len(span) - 1)] if b < len(span) - 1 else span[b]
        out.append(go.Scatter(
            x=[x0, x1, x1, x0, x0],
            y=[0, 0, ceiling, ceiling, 0],
            mode="lines",
            line=dict(width=0),
            fill="toself",
            fillcolor="rgba(0,0,0,0)",
            fillpattern=dict(shape="/", size=7, solidity=0.12,
                             fgcolor=ink, bgcolor="rgba(0,0,0,0)"),
            hoverinfo="skip",
            # UNE SEULE entrée, et elle n'est pas cliquable en mode « part » : la
            # légende y est désactivée en entier, parce qu'un clic masquerait une
            # trace sans recalculer les parts.
            showlegend=legend and n == 0,
            name=label,
            legendgroup="__unmeasured__",
        ))
    return out


def _unmeasured_hover(spans: list, span: list) -> object:
    """Une trace invisible qui DIT, au survol, que le pas n'a pas été mesuré.

    La hachure se voit, elle ne se survole pas : un rectangle n'a que quatre coins,
    donc en `hovermode="x unified"` il ne contribue à aucune des colonnes entre les
    deux. L'artiste survolait un trou et lisait « 0 » — le chiffre qu'on avait
    justement cessé de dessiner. « Clarifier le 0 » (2026-09-12).

    Cette trace porte un point à CHAQUE pas non mesuré, à hauteur zéro, invisible
    (`marker` transparent, taille nulle) et hors `stackgroup` pour ne rien ajouter à
    la pile. Son seul travail est d'exister sous le curseur.
    """
    import plotly.graph_objects as go

    from src.dashboard.utils.i18n import t
    holes = sorted({i for a, b in spans for i in range(a, b + 1)})
    return go.Scatter(
        x=[span[i] for i in holes], y=[0] * len(holes),
        mode="markers", marker=dict(size=0.1, color="rgba(0,0,0,0)"),
        showlegend=False, legendgroup="__unmeasured__",
        hovertemplate="<b>" + t("platform_chart.no_data_hover",
                                "Pas de donnée récoltée sur cette période")
                      + "</b><extra></extra>",
    )


def _late_starts(aligned: dict, order: list, span: list,
                 labels: dict) -> list:
    """`(libellé, date)` pour chaque plateforme dont la 1ʳᵉ mesure suit la fenêtre.

    Index 0 exclu : une plateforme mesurée dès le premier pas n'a pas de préhistoire
    à expliquer, et le dire serait du bruit sur la ligne la plus utile.
    """
    out = []
    for pkey in order:
        first, _ = _measured_range(aligned.get(pkey) or [])
        if first:
            out.append((labels.get(pkey, pkey), span[first]))
    return out


def _not_yet_collected_hover(aligned: dict, order: list, span: list,
                             labels: dict) -> list:
    """Une trace invisible PAR PLATEFORME, sur ses pas antérieurs à sa 1ʳᵉ mesure.

    C'est la réponse littérale à la remarque du 2026-09-12 : « quand je sélectionne
    avec la souris, j'ai pas de data pour youtube et soundcloud depuis le début ».
    Exact — il n'y avait rien à survoler. Les points de la préhistoire valent `None`,
    donc `hovermode="x unified"` n'affiche aucune ligne pour eux, et le lecteur en
    conclut ce qu'il veut : une panne, un zéro, un bug.

    La hachure ne peut pas le dire à sa place : elle est pleine hauteur, donc elle
    parle de TOUTES les plateformes à la fois, et la préhistoire est un fait
    individuel — Spotify mesure depuis 2023 pendant que SoundCloud n'existe pas
    encore. Voir `unmeasured_spans` pour ce que cette confusion coûtait.

    Chaque trace porte le nom de sa plateforme, donc la ligne apparaît au bon
    endroit dans l'infobulle groupée, avec sa date de départ.
    """
    import plotly.graph_objects as go

    from src.dashboard.utils.i18n import t

    out = []
    for pkey in order:
        values = aligned.get(pkey) or []
        first, _ = _measured_range(values)
        if not first:                      # 0 ou None : aucune préhistoire à dire
            continue
        since = span[first]
        out.append(go.Scatter(
            x=span[:first], y=[0] * first,
            mode="markers", marker=dict(size=0.1, color="rgba(0,0,0,0)"),
            showlegend=False, legendgroup=pkey,
            name=labels.get(pkey, pkey),
            hovertemplate=t("platform_chart.not_yet_collected",
                            "pas encore collectée — depuis le {since}").format(
                                since=since.isoformat())
                          + "<extra>" + labels.get(pkey, pkey) + "</extra>",
        ))
    return out
