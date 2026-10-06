"""Les KPI de l'accueil — total + donut à côté de la figure, puis quatre tuiles et trois portes.

Type: Sub
Uses: streamlit, i18n.t, html
Depends on: rien du dépôt — ni base, ni requête, ni figure
Persists in: nothing

Pourquoi ce module existe
-------------------------
`views/home.py` a franchi 1 200 lignes le 2026-09-13 en gagnant les tuiles Shazam puis
Hypeddit, et le cliquet `tests/test_a_file_only_gets_shorter.py` a refusé — « les
ajouter à FROZEN fige la dette ; les découper la retire ».

**La couture est réelle, pas un déménagement.** Cette fonction ne prend que des
dictionnaires déjà calculés et rend du Streamlit : elle n'ouvre aucune connexion, ne
lit aucune série, ne connaît ni le pas ni le mode de la figure. C'est la même couture
que `platform_chart_labels.py` a suivie le 2026-09-13 — poser un nombre dans une case
ne demande rien de ce qui l'a calculé.

Ce que cela rend possible, et qui comptait
------------------------------------------
La colonne devient testable SEULE : on lui passe un `totals` et un `side`, et on lit
ce qu'elle affiche, sans base et sans rendu de page complète. Les deux défauts que ce
dépôt a payés le plus cher sur ces tuiles — un zéro affiché à la place d'une absence,
un écart calculé contre une fenêtre non mesurée — se vérifient à ce niveau-là.

⚠️ ELLE S'APPELLE `render_tiles`, SANS TIRET BAS. Le nom privé n'avait de sens que
tant qu'elle vivait dans le fichier qui l'appelle ; exportée, un `_` en tête dirait
« n'importez pas ceci » à son seul appelant légitime.
"""
from __future__ import annotations

import contextlib
import html as _html

import streamlit as st

from src.dashboard.utils.formats import num
from src.dashboard.utils.i18n import t
from src.dashboard.utils.proxy_disclosure import cpr_help
from src.dashboard.utils.stat_boxes import stat_box


def _format_gate(val) -> str:
    """One gate tile's value: the maximum predicted probability, ON the floor too. Pure.

    R421 — the owner's decision (2026-10-06): « pas d'estimation fiable » is replaced by
    the number. The floor caveat moved to the tooltip; this is the one surface exempted
    from `proba_affichable` (tests/test_a_floor_probability_is_never_shown_as_a_measure.py).
    """
    try:
        p = float(val)
    except (TypeError, ValueError):
        return "—"
    if p != p:                                            # NaN
        return "—"
    return f"{p * 100:.1f}".replace(".", ",") + " %"


#: R424 — each gate's 28-day target and the measure it starts from. DW and Radio: the
#: model's own non-algo threshold (`ALGO_FEATURE_ZONES`). RR has only a release-week
#: threshold (2 000 / 7 d); the owner chose to bring it to 28 days, ×4 (2026-10-06).
_GATE_28D = (("release_dw", "DW", "NonAlgoStreams28Days", 1),
             ("release_radio", "RADIO", "NonAlgoStreams28Days", 1),
             ("release_rr", "RR", "StreamsLast7Days", 4))


def gate_gaps_28d(nonalgo28_log, streams28) -> dict:
    """{gate key: streams still missing over the next 28 days}. Pure.

    A gate whose measure is unknown (no prediction → no non-algo figure) is left out
    rather than shown as the whole target: « nothing measured » is not « zero ». RR's
    measure is the release's streams over the last 28 days, where no row means none.
    """
    import math

    from src.dashboard.utils.algo_knowledge import ALGO_FEATURE_ZONES

    nonalgo = math.expm1(nonalgo28_log) if nonalgo28_log is not None else None
    out = {}
    for key, algo, fid, mult in _GATE_28D:
        target = (ALGO_FEATURE_ZONES.get(algo, {}).get(fid) or {}).get("target")
        current = nonalgo if fid == "NonAlgoStreams28Days" else (streams28 or 0)
        if target is None or current is None:
            continue
        out[key] = max(0, round(target * mult - current))
    return out


def _gate_sub(gap, cpr) -> str:
    """The small line under a gate: what is left over 28 days, and its price. Pure."""
    if gap is None:
        return ""
    if gap == 0:
        return t("home.gate_28d_met", "✅ objectif 28 j atteint")
    line = t("home.gate_28d_gap", "📈 {n} streams / 28 j").format(
        n=f"{gap:,}".replace(",", "\u202f"))
    if cpr:
        line += " · 💶 " + f"{gap * cpr:,.0f}".replace(",", "\u202f") + "\u00a0€"
    return line


def agencer(unites: list, par_rangee: int = 2) -> list[list]:
    """Range les unités en rangées SANS jamais en couper une.

    Une « unité » est une liste de boîtes qui doivent rester côte à côte. Deux
    existent, et leur voisinage est une décision écrite, pas un hasard de place :

      Meta + Hypeddit     la chaîne que le produit raconte : on dépense, les gens
                          cliquent, le titre est écouté, l'algorithme le reprend
      Shazam + Instagram  les signaux relevés hors des plateformes d'écoute (V3)

    Un simple découpage en tranches de deux les casserait dès qu'une unité de deux
    tombe en position impaire. Cette fonction regarde donc PLUS LOIN dans la liste :
    quand il ne reste qu'une place et que l'unité suivante en demande deux, elle
    avance une unité d'une seule boîte pour combler, et l'unité de deux garde sa
    rangée entière.

    Pure : ni Streamlit, ni base. Elle se teste sur des entiers.
    """
    restantes = list(unites)
    rangees: list[list] = []
    while restantes:
        rangee: list = []
        place = par_rangee
        while place and restantes:
            # La première unité qui TIENT dans ce qui reste de la rangée.
            i = next((j for j, u in enumerate(restantes) if len(u) <= place), None)
            if i is None:
                break          # rien ne tient : la rangée se ferme incomplète
            unite = restantes.pop(i)
            rangee.extend(unite)
            place -= len(unite)
        rangees.append(rangee)
    return rangees


def _render_total_and_share(_t: dict, _grand_fmt: str, _banner_title: str,
                            delta: str | None, total_slot=None, share_slot=None) -> None:
    """The total banner, then each platform's share of it (the donut).

    R424 — « le total au milieu entre le graphique et le diagramme circulaire, où ça
    fait référence aux deux » (2026-10-06): the banner goes in its own middle column,
    so the donut column holds the plot alone and lines up with the figure.
    """
    # LE BANDEAU EST COMPACT : il partage la largeur avec la figure désormais.
    # « diminues la taille des box pour que tout rentre ». 2,6em débordait de sa
    # colonne dès six chiffres ; 1,8 était trop discret (V1, 2026-10-05) → 2,3.
    # The row is bottom-aligned on the plots (340 px): the bottom margin lifts the
    # banner to their vertical middle.
    (total_slot or st).markdown(
        f"""<div title="{_banner_title}" style="text-align:center; padding:8px 6px;
            background:#f0f2f6; border-radius:8px; margin-bottom:{
                "120px" if total_slot is not None else "8px"};">
            <div style="color:#555; font-size:0.78em; font-weight:600;">{
                t("home.total_all_platforms", "🎧 Total streams")}</div>
            <div style="font-size:1.9em; line-height:1.1; color:#1DB954;
                 font-weight:800;">{_grand_fmt}</div>
            <div style="color:#666; font-size:0.78em;">{
                delta or ""}</div>
        </div>""",
        unsafe_allow_html=True)

    # R371 (V2) — each platform's share of THAT total, read from the same `totals`
    # dict: the slices sum to the number above by construction, never a second total.
    from src.dashboard.utils import charts
    from src.dashboard.utils.platform_share import platform_share_figure
    _pie = platform_share_figure(_t)
    if _pie is not None:
        # R423 — no decision line under the donut: « Voir quelle plateforme porte tes
        # écoutes… » was « inutile » (the owner, 2026-10-06).
        with share_slot if share_slot is not None else contextlib.nullcontext():
            charts.plotly_chart(_pie, width="stretch", key="home_platform_share",
                                decision=False)


def render_tiles(totals: dict, grand_total: int, ig_count: int,
                  side: dict | None = None, prev_grand: int | None = None,
                  share_slot=None, total_slot=None) -> None:
    """Les KPI de l'accueil — trois blocs.

    R423 (2026-10-06) — « sur la même ligne horizontale le graphique cumulé et le
    diagramme circulaire », puis Meta Ads, Hypeddit, Shazam, Insta « sur la même ligne
    les quatre », et en dessous les trois portes. `share_slot` is the column beside the
    figure: the total banner and the donut go there, everything else below the row.

    ── L'ORDRE, ET POURQUOI CELUI-LÀ ────────────────────────────────────────────

    1. le total toutes plateformes, avec son écart ;
    2. **les trois portes algorithmiques de la DERNIÈRE SORTIE** — Discover Weekly,
       Radio, Release Radar. « rajoute dans les kpi juste en dessous de streams
       totaux, la meilleure probabilité pour la dernière release de trigger : DW
       Radio et RR : 3 kpi » (2026-09-12). Trois portes distinctes, trois chiffres :
       leur maximum répondait à une autre question, « quel titre du catalogue est le
       mieux placé », qui n'est pas celle qu'on se pose devant une sortie ;
    3. une boîte par plateforme, plus Meta Ads.

    ⚠️ **CE SONT DES PROBABILITÉS PRÉDITES, jamais des taux observés.** Le taux
    observé demanderait `s4a_song_algo_outcomes`, à **0 ligne** tous locataires
    confondus (mesuré le 2026-09-12) : personne n'a jamais saisi l'issue d'une
    prédiction. Le libellé porte le mot, et il doit le porter.

    ── L'ÉCART, ET POURQUOI LA PÉRIODE PRÉCÉDENTE DE MÊME LONGUEUR ──────────────

    C'est le seul repère défini pour TOUT filtre, indépendant du calendrier, à
    durées égales. Il ne coûte aucune requête : `platform_totals` relit des séries
    dont les requêtes ne portent qu'`artist_id`, donc déjà en cache.

    **AUCUN ÉCART CONTRE UNE PÉRIODE NON MESURÉE.** Un « +100 % » contre une fenêtre
    où l'on n'avait pas encore collecté transforme le début de NOTRE observation en
    croissance de l'artiste — rendu impossible par construction : `None` ne produit
    pas de flèche.

    ── CE QUE DIT UNE BOÎTE VIDE ────────────────────────────────────────────────

    Mesuré en production le 2026-09-12 : la série Spotify s'arrête au 5 septembre,
    sept jours en arrière. Sur une fenêtre courte il n'y a donc réellement rien — et
    c'était lu comme une incohérence, parce que les autres plateformes avaient des
    points. La boîte nomme sa dernière date plutôt que de laisser « — » se lire comme
    un zéro.
    """
    _t, _s = totals or {}, side or {}

    def _n(v) -> str:
        # `—` ET JAMAIS `0`. Un zéro affirme « personne n'a écouté » ; l'absence dit
        # « nous n'avons rien mesuré ».
        return f"{int(v):,}".replace(",", "\u202f") if v else "—"

    def _delta(now, before):
        """L'écart relatif, ou `None` — jamais un pourcentage contre du vide."""
        if not now or not before:
            return None
        return f"{(now - before) / before * 100:+.1f}".replace(".", ",") + " %"

    # ── CE QUE LE CHIFFRE-TITRE ADDITIONNE, NOMMÉ PLUTÔT QUE SUPPOSÉ ────────
    #
    # Mesuré le 2026-09-13, artiste 1, « Depuis le début » : le bandeau additionne
    # les 165 065 de Spotify — mesurées jour par jour — aux COMPTEURS À VIE de
    # YouTube (118 336) et SoundCloud (23 486). **41 % du plus gros chiffre de
    # l'accueil** n'a donc aucune date derrière lui, et rien ne le disait.
    #
    # Le nombre est CONSERVÉ tel quel : c'est bien le total de ce que l'artiste a
    # fait, et le rogner de 41 % lui retirerait une vérité pour en servir une autre.
    # Ce qui manquait était la composition, pas le total.
    #
    # ⚠️ LA PHRASE EST CONDITIONNELLE, et elle se dérive de la MÊME condition que
    # l'infobulle des tuiles à compteur — `_obs[1] < value`, la croissance observée
    # est inférieure au total affiché. Sur une fenêtre bornée, `platform_totals`
    # rend une différence de niveaux : il n'y a alors aucun compteur à vie dans la
    # somme, la condition est fausse, et la phrase ne s'affiche pas. L'écrire sans
    # condition serait vrai un filtre sur cinq.
    #
    # `title=` ET NON `help=` : le bandeau est du HTML brut — `st.markdown` n'a pas
    # d'infobulle. L'attribut natif ne coûte pas une ligne de hauteur, et c'est ce
    # qui a été exigé pour la boîte Meta : aucune case plus haute que ses voisines.
    _lifetime_parts = []
    for _k, _lab in (("youtube", "🎬 YouTube"), ("soundcloud", "☁️ SoundCloud")):
        _v, _o = _t.get(_k), (_s.get("observed_growth") or {}).get(_k)
        if _v and _o and _o[1] < _v:
            _lifetime_parts.append(
                f"{_lab} {int(_v):,}".replace(",", "\u202f"))
    _banner_title = ""
    if _lifetime_parts and grand_total:
        _banner_title = _html.escape(t(
            "home.total_composition",
            "Somme de toutes les plateformes mesurées. {parts} sont des COMPTEURS À "
            "VIE : ils portent tout ce qui précède notre première collecte, et cette "
            "part-là n'a aucune date. Les écoutes Spotify, elles, sont comptées jour "
            "par jour."
        ).format(parts=" et ".join(_lifetime_parts)))

    # LE SÉPARATEUR DE MILLIERS SE POSE SUR LE NOMBRE, PAS SUR LE GABARIT.
    # Un `.replace(",", "…")` sur toute la chaîne rendue mangeait AUSSI les virgules
    # de l'infobulle qu'on vient d'y mettre — les siennes sont du texte, pas des
    # milliers. Le défaut n'existait pas tant que le gabarit n'était que du HTML.
    _grand_fmt = f"{grand_total:,}".replace(",", "\u202f")
    if total_slot is not None:
        _render_total_and_share(_t, _grand_fmt, _banner_title,
                                _delta(grand_total, prev_grand),
                                total_slot=total_slot, share_slot=share_slot)
    else:
        with share_slot if share_slot is not None else contextlib.nullcontext():
            _render_total_and_share(_t, _grand_fmt, _banner_title,
                                    _delta(grand_total, prev_grand))

    # ── L'ORDRE SUIT LA DONNÉE — 2026-09-22 ────────────────────────────────
    #
    # « l'accueil montre en prio les plateformes qui ont des données ». Les six
    # rangées étaient écrites à la main, dans un ordre fixe, et un artiste qui n'a
    # que SoundCloud le trouvait en cinquième position derrière quatre tirets.
    #
    # Une UNITÉ est une liste de boîtes qui ne se séparent jamais. Deux existent,
    # et leur voisinage est une décision écrite :
    #
    #   Meta + Hypeddit     la chaîne que le produit raconte : on dépense (Meta), les
    #                       gens cliquent (Hypeddit), le titre est écouté
    #   Shazam + Instagram  les deux signaux relevés HORS des plateformes d'écoute —
    #                       demandé le 2026-10-05 (V3), il remplace Apple + Shazam
    #
    # `agencer()` les range sans jamais en couper une.
    #
    # ⚠️ DEUX PAR RANGÉE, pas trois : la colonne fait 2/5 de la page et un libellé
    # comme « ☁️ SoundCloud » se coupe en deux à trois colonnes.
    #
    # ⚠️ Le tri ne touche QUE ce bloc. Le total toutes plateformes reste en tête et
    # les trois portes algorithmiques restent en dernier — « place les 3 box en
    # dessous de insta & meta ads » (2026-09-13), pour ne pas mélanger du mesuré et
    # du prédit dans le même coup d'œil.

    # ── SHAZAM — LE CATALOGUE, ET LA DERNIÈRE SORTIE ────────────────────────
    #
    # ADR-025 met Shazam dans le cœur du produit ; il n'apparaissait sur AUCUN écran
    # (0 occurrence dans ce fichier, mesuré le 2026-09-13, quand `youtube` en avait
    # 12). C'est l'incohérence que l'arbitrage a rendue visible.
    #
    # LE TITRE EST DANS L'INFOBULLE, PAS DANS LA LIGNE SECONDAIRE — même arbitrage
    # que la campagne de la boîte Meta juste en dessous. « Ô Chiotte l'arbitre
    # Tucome Back - Original » dans une colonne à 2/5 de la page passerait à la
    # ligne et casserait l'alignement de la rangée, celui-là même qui vient d'être
    # corrigé sur Meta.
    #
    # `delta_color="off"` : ce n'est pas une variation, c'est un second chiffre
    # d'une autre nature. Le teinter lui ferait dire « ça monte ».
    _shz, _shz_rel = _s.get("shazam_total"), _s.get("shazam_release")
    _shz_song = _s.get("release_song")
    _shz_help = t(
        "home.tile_shazam_help",
        "Shazams **depuis le début**, lus dans l'export Apple Music. C'est un "
        "relevé de dépôt et non une quantité du jour : il ne se découpe pas par "
        "période, et ce chiffre ne bouge donc pas avec le filtre.")
    if _shz_song:
        _shz_help += (
            " " + t("home.tile_shazam_release_help",
                    "La seconde ligne est la dernière sortie, « {song} ».")
            .format(song=_shz_song)
            if _shz_rel is not None else
            # DIRE POURQUOI C'EST VIDE. Le titre d'une sortie et celui d'un export
            # Apple sont deux textes LIBRES qui ne coïncident pas — mesuré le
            # 2026-09-13 : « … Tucome Back - Original » contre « … Tucome Back »,
            # zéro ligne en égalité exacte. Sans rapprochement confirmé on n'affiche
            # rien plutôt qu'un chiffre pris sur un homonyme.
            " " + t("home.tile_shazam_unlinked",
                    "« {song} » n'est pas encore rapprochée d'un titre Apple : son "
                    "compte de Shazams ne peut pas être isolé. La page **🔗 "
                    "Correspondance des titres** permet de faire le lien.")
            .format(song=_shz_song))

    # META ADS — LE CPR DE LA DERNIÈRE CAMPAGNE, PAS LE RECORD HISTORIQUE.
    # « met en automatique la dernière release et pas forcément les meilleurs
    # résultats qu'on a obtenu toute campagne confondue » (2026-09-12). Un record
    # est irréfutable : on ne peut pas faire mieux, donc il ne bouge jamais et ne
    # dit rien de ce qui marche aujourd'hui. Le nom de la campagne retenue est
    # affiché AVEC le chiffre — c'est ce qui rend la règle vérifiable d'un coup
    # d'œil, là où un rapprochement flou sur le titre se tromperait en silence.
    _spend, _cpr = _s.get("meta_spend"), _s.get("best_cpr")
    _cpr_spend, _cpr_name = _s.get("best_cpr_spend"), _s.get("best_cpr_name")
    # LE CPR EST DANS LA LIGNE `delta`, PAS DANS UN `st.caption` SOUS LA BOÎTE.
    #
    # « il faut ramener la taille de la box meta de la même dimension que les
    # autres » (2026-09-13). La légende sous la métrique ajoutait une ligne à cette
    # boîte seule : dans une grille de six, une case plus haute que ses voisines
    # casse l'alignement de toute la rangée, et l'œil lit ce décalage comme une
    # hiérarchie qui n'existe pas.
    #
    # `delta_color="off"` parce que ce n'est PAS une variation : c'est un second
    # chiffre de nature différente. Le teinter en vert ou en rouge lui ferait dire
    # « ça monte » ou « ça baisse », ce qui n'a aucun sens pour un coût par résultat
    # affiché seul. L'écart de dépense cède sa place — entre « la dépense a varié de
    # x % » et « voici le CPR de la dernière campagne », c'est le second qui a été
    # demandé, et une boîte ne porte qu'un chiffre secondaire.
    _cpr_line = None
    if _cpr:
        _cpr_line = t("home.tile_best_cpr", "🎯 CPR {cpr}{budget}").format(
            cpr=f"{_cpr:,.4f}".replace(",", "\u202f").replace(".", ",") + "\u00a0€",
            budget=(" · " + f"{_cpr_spend:,.2f}".replace(",", "\u202f")
                    .replace(".", ",") + "\u00a0€") if _cpr_spend else "")

    _hd_ctr, _hd_camp = _s.get("hypeddit_ctr"), _s.get("hypeddit_campaign")
    _hd_v, _hd_c = _s.get("hypeddit_visits"), _s.get("hypeddit_clicks")
    _hd_help = t(
        "home.tile_hypeddit_help",
        "Meilleur taux de clic obtenu par un lien Hypeddit de la dernière sortie : "
        "clics divisés par visites. Il porte toute l'histoire de la campagne, pas la "
        "période affichée — ce chiffre ne bouge donc pas avec le filtre.")
    if _hd_camp:
        _hd_help += " " + t("home.tile_hypeddit_campaign",
                            "Campagne : « {name} ».").format(name=_hd_camp)
    elif _s.get("release_song"):
        # DIRE POURQUOI C'EST VIDE, comme la tuile Shazam. Le rapprochement passe par
        # un lien CONFIRMÉ : la sortie est « … Tucome Back - Original » et la
        # campagne « … tucome back », la casse et le suffixe diffèrent.
        _hd_help += " " + t(
            "home.tile_hypeddit_unlinked",
            "« {song} » n'est rattachée à aucune campagne Hypeddit confirmée. La "
            "page **🔗 Correspondance des titres** permet de faire le lien."
        ).format(song=_s["release_song"])

    # Chaque boîte : (la valeur qui dit si elle a des données, son rendu).
    # Spotify, YouTube, Apple Music and SoundCloud have no box since R421: the pie
    # above carries them, value and share (« vu qu'on les affiche dans le rond »).
    def _u_shazam(col):
        with col.container(border=True):
            st.metric(
                t("home.tile_shazam", "🎧 Shazam"), _n(_shz),
                delta=(t("home.tile_shazam_release", "🆕 Dernière sortie · {n}")
                       .format(n=num(_shz_rel, 0))
                       if _shz_rel is not None else None),
                delta_color="off", help=_shz_help)

    def _u_instagram(col):
        # INSTAGRAM PORTE UN EFFECTIF, ET SON ÉCART EST DÉJÀ UN ÉCART — `ig_delta`
        # est le gain d'abonnés SUR LA FENÊTRE, pas un cumul.
        with col.container(border=True):
            st.metric("📸 Instagram", _n(ig_count),
                      delta=(f"{_ig_d:+d}" if _ig_d else None),
                      help=t("home.ig_is_a_headcount",
                             "Un EFFECTIF d'abonnés, pas un cumul d'écoutes : il ne "
                             "se découpe pas par période et n'entre pas dans le "
                             "total ci-dessus. L'écart est celui de la période "
                             "affichée."))

    def _u_meta(col):
        with col.container(border=True):
            st.metric(t("home.tile_meta", "📊 Meta Ads"),
                      (f"{_spend:,.2f}".replace(",", "\u202f").replace(".", ",")
                       + "\u00a0€") if _spend else "—",
                      delta=_cpr_line, delta_color="off",
                      help=t("home.tile_meta_help",
                             "Dépense publicitaire de la période affichée, et le "
                             "coût par résultat de la campagne la plus RÉCENTE — "
                             "celle de la dernière sortie, pas le record de toutes "
                             "les campagnes.")
                      + (f" Campagne : {_cpr_name}." if _cpr_name else "")
                      # R146 — ce chiffre est un coût par CLIC SORTANT. C'est la
                      # tuile du premier écran : elle ne peut pas être la seule à
                      # laisser croire qu'un « résultat » est une écoute.
                      + "\n\n" + cpr_help())

    def _u_hypeddit(col):
        with col.container(border=True):
            st.metric(
                t("home.tile_hypeddit", "📱 Hypeddit"),
                (f"{_hd_ctr:.1f}".replace(".", ",") + "\u00a0%")
                if _hd_ctr is not None else "—",
                delta=(t("home.tile_hypeddit_volume", "👁️ {v} · 🖱️ {c}").format(
                           v=f"{_hd_v:,}".replace(",", "\u202f"),
                           c=f"{_hd_c:,}".replace(",", "\u202f"))
                       if _hd_v else None),
                delta_color="off", help=_hd_help)

    _ig_d = _s.get("ig_delta")
    _unites = [
        # R371 (V3) — Meta Ads + Hypeddit on one row (the spend → click chain), then
        # Shazam + Instagram on the next: the two signals measured off the stores.
        [(_spend, _u_meta), (_hd_ctr, _u_hypeddit)],
        [(_shz, _u_shazam), (ig_count, _u_instagram)],
    ]
    # `sorted` est STABLE : à présence égale, l'ordre de déclaration ci-dessus
    # départage. Une unité a des données dès qu'UNE de ses boîtes en a — sans quoi
    # Shazam vide ferait descendre Apple qui livre.
    _unites.sort(key=lambda u: not any(v for v, _f in u))

    # R423 — the four boxes on ONE row, under the figure and the donut.
    for _rangee in agencer(_unites, par_rangee=4):
        _cols = st.columns(4)
        for _col, (_valeur, _rendu) in zip(_cols, _rangee):
            _rendu(_col)


    # `_recap_extra` A ÉTÉ SUPPRIMÉE LE 2026-09-12, pas mise de côté. Elle fabriquait
    # les lignes « Apple Music / Instagram / Meta Ads » de la table de droite, avec leur
    # unité entre parenthèses. Les trois ont désormais leur BOÎTE dans la rangée du haut,
    # où elles portent en plus l'écart contre la période précédente. Garder la fonction
    # « au cas où » aurait produit ce que ce dépôt paie le plus souvent : du code correct
    # que rien n'atteint, et qui pourrit jusqu'à ce qu'on le rebranche sur un écran qui a
    # changé sous lui.


    # ── LES TROIS PORTES DE LA DERNIÈRE SORTIE, SOUS LES PLATEFORMES ────────
    #
    # « place les 3 box en dessous de insta & meta ads » (2026-09-13). Elles étaient
    # juste sous le total, en tête de colonne. Elles y coupaient la lecture : les six
    # boîtes de plateformes racontent ce qui S'EST PASSÉ, ces trois-là ce qui POURRAIT
    # se passer. Mélanger du mesuré et du prédit dans le même coup d'œil est le
    # meilleur moyen de faire lire une prédiction comme un relevé.
    #
    # Le libellé le dit désormais en toutes lettres — « Probabilités prédites
    # maximales pour » : ce sont les maximums que le modèle a attribués à ce titre,
    # pas des taux constatés. Le taux constaté demanderait `s4a_song_algo_outcomes`,
    # à **0 ligne** tous locataires confondus (mesuré le 2026-09-12).
    _gates = (("release_dw", t("home.gate_dw", "🎯 Discover Weekly")),
              ("release_radio", t("home.gate_radio", "📻 Radio")),
              ("release_rr", t("home.gate_rr", "🆕 Release Radar")))
    if any(_s.get(k) for k, _lab in _gates):
        # R421 — no sentence above or below (« Ta dernière sortie… », « Budget Meta
        # pour déclencher… » : « enlève les phrases inutiles », 2026-10-06). The title
        # and the nature of the number live in each box's tooltip.
        st.caption(t(
            "home.gates_caption",
            "Le pourcentage maximal prédit pour ta dernière sortie d'entrer dans "
            "chaque playlist algorithmique de Spotify."))
        g1, g2, g3 = st.columns(3)
        # R424 — under each percentage, « en tout petit […] comme Meta, Hypeddit,
        # Shazam et Instagram »: the streams left over 28 days and their price at the
        # best CPR, read as 1 click = 1 stream (the owner's choice, 2026-10-06).
        _gaps = gate_gaps_28d(_s.get("release_nonalgo28_log"),
                              _s.get("release_streams28"))
        for col, (key, label) in zip((g1, g2, g3), _gates):
            val = _s.get(key)
            # R346 — compact HTML, not `st.metric`: its label/value fonts are fixed and
            # « 🆕 Release Radar » was cut to « 🆕 Release Ra… » in a third of the column.
            # The help survives as the tooltip; the HTML is ONE line (see
            # tests/test_an_html_placeholder_never_stands_alone_on_its_line.py).
            col.markdown(stat_box(label, _format_gate(val),
                                   t("home.gate_help_max",
                                     "Probabilité PRÉDITE maximale que « {song} », ta "
                                     "dernière sortie, entre dans cette playlist "
                                     "algorithmique. Ce n'est pas un taux observé. Au "
                                     "plancher du modèle, ce chiffre est le même pour "
                                     "tous les titres.").format(
                                         song=_s.get("release_song") or "—")
                                   + " " + t("home.gate_28d_help",
                                             "En dessous : les streams qui manquent sur "
                                             "28 jours pour atteindre le seuil du modèle, "
                                             "et leur coût au meilleur CPR, en comptant "
                                             "un clic pour une écoute."),
                                   sub=_gate_sub(_gaps.get(key), _cpr)),
                         unsafe_allow_html=True)
