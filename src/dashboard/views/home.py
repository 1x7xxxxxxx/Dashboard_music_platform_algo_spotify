"""Page d'accueil — KPI globaux, fraîcheur des sources, statut des pipelines."""
import datetime as _dt
import html as _html
import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from src.dashboard.utils import project_db
from src.dashboard.utils.i18n import t
from src.dashboard.auth import tenant_scope
from src.dashboard.utils.navigation import goto
from src.dashboard.utils.status_matrix import render_status_matrix
from src.dashboard.utils.airflow_monitor import AirflowMonitor, cached_last_run_per_dag
from src.dashboard.utils.kpi_helpers import (
    get_source_freshness, freshness_status,
    SOURCES_CONFIG,
)


# Au-delà de cette fenêtre, le pas JOUR n'est plus le défaut : « Depuis le début »
# couvre ~4 ans, soit ~1 400 points par plateforme — la figure devient illisible et
# le rendu coûte plus que ce qu'il montre. 120 jours ≈ un trimestre glissant, la
# plus longue fenêtre où un point par jour reste lisible sur la largeur d'un écran.
# L'artiste peut toujours forcer le jour : c'est un défaut, pas une contrainte.
# Au-delà de cette fenêtre, le pas du jour cède au mois. 360 et non 365 : le
# filtre « 12 mois » vaut 365 jours et doit basculer, une année bissextile ou un
# arrondi de bornes ne doit pas décider du grain affiché.
_DAY_UNTIL_YEAR = 360
# Au-delà de ce nombre de points, une courbe devient une bande. ~5 ans au pas mois.
_MAX_BUCKETS = 60


def _freshness_badge(label, icon, last_dt):
    """Génère une carte de fraîcheur HTML."""
    emoji, color, age_label = freshness_status(last_dt)
    date_str = last_dt.strftime("%d/%m %H:%M") if last_dt else "—"
    return f"""
    <div style="border:1px solid {color}; border-radius:8px; padding:8px 12px;
                background:{color}18; text-align:center; min-width:110px;">
        <div style="font-size:1.3em;">{icon}</div>
        <div style="font-weight:600; font-size:0.85em;">{label}</div>
        <div style="font-size:0.75em; color:{color};">{emoji} {age_label}</div>
        <div style="font-size:0.65em; color:#888;">{date_str}</div>
    </div>
    """


def _section_freshness(db, artist_id):
    """Deux groupes, parce que ce sont deux CONTRATS différents.

    Les huit sources étaient sur une seule ligne, sous un paragraphe qui expliquait
    en prose laquelle était automatique et laquelle attendait un fichier. Le lecteur
    devait donc retenir une liste pour interpréter une grille — et l'information qui
    compte vraiment, « à quelle heure ça arrive », n'était nulle part.

    Chaque source porte désormais son contrat (`kind`) et son heure (`at`) dans
    `SOURCES_CONFIG`, et la grille les montre là où on les lit : sous la source.
    """
    st.subheader(t("home.freshness_header", "📡 Fraîcheur des données"))
    freshness = get_source_freshness(db, artist_id)
    meta = {src["label"]: src for src in SOURCES_CONFIG}

    # Deux titres, aucune glose. « 🔄 Collecte automatique » et « 📂 À déposer
    # toi-même » disent déjà tout ce que les deux phrases retirées le 2026-09-12
    # répétaient ; et chaque tuile d'API porte son heure, ce que la phrase ne
    # faisait pas.
    groups = (
        ("api", t("home.freshness_api", "🔄 Collecte automatique")),
        ("csv", t("home.freshness_csv", "📂 À déposer toi-même")),
    )
    for kind, title in groups:
        labels = [lbl for lbl in freshness if meta.get(lbl, {}).get("kind") == kind]
        if not labels:
            continue
        st.markdown(f"**{title}**")
        cols = st.columns(len(labels))
        for col, label in zip(cols, labels):
            info = freshness[label]
            # Le BARÈME suit le contrat de la source : un CSV non redéposé
            # depuis trois jours n'est pas une panne, une API muette si.
            emoji, color, age_label = freshness_status(info["last_dt"], kind)
            date_str = info["last_dt"].strftime("%d/%m %H:%M") if info["last_dt"] else "—"
            at = meta.get(label, {}).get("at")
            when = (t("home.freshness_every_day", "chaque jour à {h}").format(h=at)
                    if at else t("home.freshness_on_upload", "à chaque import"))
            with col:
                # HIGH-07: html.escape() on all interpolated values — defence-in-depth
                # against stored XSS if a DB-sourced value ever reaches these variables.
                st.markdown(
                    f"""<div style="border:1px solid {_html.escape(color)}; border-radius:8px;
                        padding:8px 6px; background:{_html.escape(color)}18; text-align:center;">
                        <div style="font-size:1.2em;">{_html.escape(str(info['icon']))}</div>
                        <div style="font-weight:600; font-size:0.8em; white-space:nowrap;">{_html.escape(label)}</div>
                        <div style="font-size:0.75em; color:{_html.escape(color)};">{_html.escape(emoji)} {_html.escape(age_label)}</div>
                        <div style="font-size:0.65em; color:#888;">{_html.escape(date_str)}</div>
                        <div style="font-size:0.62em; color:#999; margin-top:2px;">{_html.escape(when)}</div>
                    </div>""",
                    unsafe_allow_html=True
                )

def _section_streams(db, artist_id):
    """Le filtre en haut au centre, la courbe à gauche, les chiffres à droite.

    Disposition demandée le 2026-09-08. Elle n'est pas qu'esthétique : la courbe est ce
    qu'on regarde, les tuiles ce qu'on vérifie. Côte à côte, elles répondent à la même
    période sans qu'on ait à faire défiler entre les deux — c'était le vrai défaut de
    la version empilée, où le filtre était à un écran de la figure qu'il commande.
    """
    from src.dashboard.utils import date_range
    from src.dashboard.utils.platform_timeseries import daily_streams_by_platform

    st.subheader(t("home.streams_header", "🎧 Tes chiffres"))

    # LES TROIS BARRES SUR LA MÊME GRILLE, alignées au bord gauche.
    #
    # Ce filtre vivait dans un `st.columns([1, 3, 1])`, donc il commençait à 20 % de
    # la largeur pendant que la barre mode/pas commençait à 0 % et la figure à 0 %.
    # Trois réglages du même écran sur trois grilles : c'est la cause mesurée du
    # désalignement signalé le 2026-09-12, et le centrage ne rendait rien en échange.
    #
    # Empilées et pleine largeur, les trois se lisent de haut en bas — période, puis
    # affichage, puis pas — et aucune ne bouge quand un libellé change de longueur.
    # Un seul propriétaire du réglage : tout ce qui suit le LIT.
    range_key = date_range.render_selector()
    since, until = date_range.bounds(range_key)

    series = daily_streams_by_platform(db, artist_id)
    # Apple n'a pas de série quotidienne : ses relevés annuels sont ajoutés tels quels
    # et ne deviennent traçables qu'au pas annuel (`STEP_ONLY`).
    from src.dashboard.utils.platform_timeseries import apple_yearly_series
    _apple = apple_yearly_series(db, artist_id)
    if _apple:
        series['apple'] = _apple
    # INSTAGRAM ET META PASSENT PAR LA MÊME REQUÊTE, et ce n'est pas une élégance :
    # l'accueil est à 13 allers-retours pour un plafond de 13, et ce plafond ne monte
    # pas (`test_a_page_asks_the_same_question_once`). `period_side_metrics` REMPLACE
    # `get_instagram_followers` — son `ig_followers` porte le même effectif courant —
    # donc la page gagne la dépense Meta et l'écart d'abonnés sans gagner une requête.
    from src.dashboard.utils.platform_timeseries import period_side_metrics
    _side = period_side_metrics(db, artist_id, since, until)
    ig_count = _side.get("ig_followers") or 0

    # UN SEUL CALCUL, pour toutes les surfaces. `platform_totals` porte les deux
    # régimes — compteurs des plateformes « depuis le début », somme des écarts mesurés
    # sur une période bornée — et refuse d'additionner deux formes. Le grand total vert
    # additionnait ici le compteur de CHAÎNE YouTube, celui qu'on a prouvé ~10× faux le
    # 2026-09-08 : trois pages du même produit donnaient trois totaux différents.
    from src.dashboard.utils.platform_timeseries import combined_total, platform_totals
    totals = platform_totals(db, artist_id, since, until)
    grand_total = combined_total(totals)

    if not grand_total and not ig_count:
        st.info(t(
            "home.no_data_yet",
            "🕐 **Tes premiers chiffres ne sont pas encore là — c'est normal.**\n\n"
            "La collecte automatique tourne **chaque matin entre 5 h et 11 h** (heure "
            "de Paris) et remplit cette page toute seule. Tu n'as rien à faire.\n\n"
            "Elle démarre aussi d'elle-même dès que tu enregistres des identifiants."))
        st.caption(t("home.no_data_hint",
                     "Si rien n'arrive après une collecte, la page **🚦 Santé "
                     "onboarding** dit quelle source ne répond pas, et pourquoi."))
        return

    # ── LA PÉRIODE PRÉCÉDENTE, DE MÊME LONGUEUR, COLLÉE DEVANT CELLE-CI ──────
    #
    # Elle alimente l'écart de CHAQUE boîte. Elle ne coûte aucun aller-retour :
    # `platform_totals` relit `daily_streams_by_platform` et
    # `cumulative_by_platform`, dont les requêtes ne portent que `artist_id` et sont
    # donc déjà dans le cache `(sql, params)`. Seul le découpage change.
    #
    # « Depuis le début » n'a PAS de période précédente : inventer une borne
    # produirait une comparaison contre du vide, et `None` ne dessine pas de flèche.
    _prev, _prev_grand = None, None
    if since is not None:
        _u = until or _dt.date.today()
        _len = (_u - since).days
        if _len > 0:
            _prev = platform_totals(db, artist_id,
                                    since - _dt.timedelta(days=_len + 1),
                                    since - _dt.timedelta(days=1))
            _prev_grand = combined_total(_prev or {}) or None

    # LA DERNIÈRE MESURE PAR PLATEFORME, dérivée de `series` — déjà en mémoire.
    # C'est ce qui permet à une boîte vide de dire « dernier relevé : 05/09/26 »
    # plutôt que de laisser croire à zéro écoute. Mesuré en prod le 2026-09-12 :
    # Spotify s'arrêtait sept jours en arrière, et rien ne le nommait.
    _side = dict(_side)
    _side["last_measured"] = {
        k: max(d for d, _v in rows) for k, rows in (series or {}).items() if rows}

    _render_tiles(totals, grand_total, ig_count,
                  prev=_prev, side=_side, prev_grand=_prev_grand)

    # `totals` et `_side` sont DÉJÀ calculés au-dessus : les repasser évite de
    # les redemander, et le plafond de requêtes est atteint.
    _render_trend(db, series, since, until, range_key, artist_id,
                  totals=totals, side=_side)


def _render_tiles(totals: dict, grand_total: int, ig_count: int,
                  prev: dict | None = None, side: dict | None = None,
                  prev_grand: int | None = None) -> None:
    """Une BOÎTE par plateforme, chacune avec son écart contre la période d'avant.

    Elles avaient quitté l'écran le 2026-09-10, et le motif était juste : elles
    portaient les compteurs « DEPUIS LE DÉBUT » pendant que la figure, à côté, ne
    traçait que la période choisie. Deux nombres pour la même ligne, aucun faux, et
    une note dont le seul travail était d'excuser l'écart en prose. Ce n'était pas la
    TUILE le défaut, c'était le CHIFFRE — et `platform_totals()` est borné à la
    fenêtre depuis le 2026-09-11.

    ── L'ÉCART, ET POURQUOI C'EST LA PÉRIODE PRÉCÉDENTE DE MÊME LONGUEUR ─────────

    « l'écart relatif en delta vs une autre période qui restera à définir selon le
    filtre temporel (si 30 jours sélectionnés, on fait le delta vs les 30 jours
    d'avant si c'est pertinent pour toi ?) » (2026-09-12). Oui, et c'est le seul
    choix qui ne demande rien à personne : la fenêtre de même longueur collée devant
    est définie pour TOUT filtre, elle ne dépend pas du calendrier, et elle compare
    des durées égales. « Le même mois l'an dernier » serait plus parlant sur douze
    mois et absurde sur trente jours ; « depuis le début » ne serait pas un écart.

    Elle ne coûte AUCUNE requête : `platform_totals` relit
    `daily_streams_by_platform` et `cumulative_by_platform`, dont les requêtes ne
    portent que `artist_id` — déjà dans le cache `(sql, params)` de la page. Changer
    la fenêtre change un découpage Python, pas un aller-retour.

    ⚠️ **AUCUN ÉCART N'EST AFFICHÉ CONTRE UNE PÉRIODE NON MESURÉE.** Un « +100 % »
    contre une fenêtre où l'on n'avait pas encore collecté transforme le début de
    NOTRE observation en croissance de l'artiste. C'est le mensonge le plus facile
    de cet écran, et il est rendu impossible par construction : `prev` vaut `None`
    pour une plateforme sans mesure, et `None` ne produit pas de flèche.

    ── CE QUE LA BOÎTE DIT QUAND LA FENÊTRE EST VIDE MAIS L'HISTORIQUE NON ───────

    Mesuré en production le 2026-09-12 : la série Spotify s'arrête au **5 septembre**,
    sept jours avant le jour où l'artiste regarde. Sur « 3 derniers jours » il n'y a
    donc réellement rien — et c'était signalé comme une incohérence, parce que
    YouTube et SoundCloud, eux, avaient des points : la figure se dessinait, Spotify
    disparaissait, et RIEN ne nommait la différence entre « zéro écoute » et « aucun
    export déposé ».

    La boîte le dit maintenant, à l'endroit où l'artiste lit le chiffre. C'est le
    bon endroit précisément parce que ce n'est PAS une note sous la figure : les
    notes de ce genre viennent d'être retirées à sa demande, et elles l'étaient à
    raison — une prose qui s'excuse ne remplace pas un chiffre qui se lit.

    Apple reste « — » sur une période bornée : ses relevés sont des totaux de dépôt,
    pas des quantités du jour, donc aucune fenêtre ne les découpe.
    """
    _t = totals or {}
    _p = prev or {}
    _s = side or {}

    def _n(v) -> str:
        # `—` ET JAMAIS `0`. Un zéro affirme « personne n'a écouté » ; l'absence dit
        # « nous n'avons rien mesuré ». C'est la distinction que toute cette page
        # défend, et une tuile est le pire endroit pour la perdre : elle est lue en
        # premier et sans contexte.
        return f"{int(v):,}".replace(",", "\u202f") if v else "—"

    def _delta(now, before):
        """L'écart relatif, ou `None` — jamais un pourcentage contre du vide."""
        if not now or not before:
            return None
        return f"{(now - before) / before * 100:+.1f}".replace(".", ",") + " %"

    st.markdown(
        f"""<div style="text-align:center; padding:14px; background:#f0f2f6;
            border-radius:10px; margin-bottom:12px;">
            <div style="color:#555; font-size:0.95em; font-weight:600;">{
                t("home.total_all_platforms",
                  "🎧 Total streams toutes plateformes")}</div>
            <div style="font-size:2.6em; color:#1DB954; font-weight:800;">{
                grand_total:,}</div>
            <div style="color:#666; font-size:0.9em;">{
                _delta(grand_total, prev_grand) or ""}</div>
        </div>""".replace(",", "\u202f"),
        unsafe_allow_html=True)

    # ⚠️ `platform_totals` EST LU SUR LE SITE D'APPEL, PAS DANS UN HELPER — et ce
    # n'est pas un goût d'écriture. Sous sa première forme (`_v("spotify")`), la
    # tuile n'était attribuable à AUCUNE source : `make gold-coverage` marquait les
    # quatre « indéterminée · appelants-multiples », le lecteur abandonnant sur un
    # helper à plus d'appelants que son plafond. Quatre tuiles de l'écran le plus lu
    # du produit sortaient de la carte de la couche or le jour même où on les
    # remettait. En lisant `_t.get(...)` ici, la tranche repart de `totals`,
    # paramètre à UN seul appelant, jusqu'à `platform_totals()` — la porte d'ADR-019.
    #
    # LA DERNIÈRE MESURE, pour distinguer « zéro » de « pas encore collecté ». Elle
    # se dérive de `side`, déjà en mémoire : aucune requête de plus.
    _last = _s.get("last_measured") or {}

    def _box(col, key: str, label: str, help_text: str | None = None) -> None:
        value, before = _t.get(key), _p.get(key)
        with col.container(border=True):
            st.metric(label, _n(value), delta=_delta(value, before),
                      help=help_text)
            # L'ABSENCE SE NOMME, ET SEULEMENT QUAND ELLE EST UNE ABSENCE. Une
            # plateforme qui n'a jamais rien livré n'a pas de « dernier relevé » à
            # montrer ; celle qui en a un, hors fenêtre, en a un à montrer.
            if not value and _last.get(key):
                st.caption(t("home.tile_last_seen",
                             "Dernier relevé : {d}").format(
                                 d=_last[key].strftime("%d/%m/%y")))

    c1, c2, c3 = st.columns(3)
    _box(c1, "spotify", "🎵 Spotify")
    _box(c2, "youtube", "🎬 YouTube")
    _box(c3, "soundcloud", "☁️ SoundCloud")

    c4, c5, c6 = st.columns(3)
    _box(c4, "apple", "🎎 Apple Music",
         t("home.apple_no_window",
           "Apple Music ne fournit qu'un relevé par dépôt de CSV : impossible de le "
           "découper par période. Choisis « Depuis le début » pour son total."))

    # INSTAGRAM PORTE UN EFFECTIF, ET SON ÉCART EST DÉJÀ UN ÉCART. `ig_delta` est le
    # gain d'abonnés SUR LA FENÊTRE (`dernier − premier`), pas un cumul : le passer
    # en `delta` d'une tuile dont la valeur est l'effectif courant dit exactement la
    # bonne chose, et sans la requête qu'un second appel aurait coûtée.
    _ig_d = _s.get("ig_delta")
    with c5.container(border=True):
        st.metric("📸 Instagram", _n(ig_count),
                  delta=(f"{_ig_d:+d}".replace("+", "+") if _ig_d else None),
                  help=t("home.ig_is_a_headcount",
                         "Un EFFECTIF d'abonnés, pas un cumul d'écoutes : il ne se "
                         "découpe pas par période et n'entre pas dans le total "
                         "ci-dessus. L'écart est celui de la période affichée."))

    # META ADS DANS LA MÊME RANGÉE — « ajoute meta ads avec l'argent dépensé et le
    # meilleur CPR obtenu avec le budget associé dans la même box » (2026-09-12).
    #
    # LE BUDGET EST COLLÉ AU CPR, jamais seul. « 0,0112 € » sans « sur 18,41 € »
    # laisse croire à une performance reproductible alors que c'est peut-être un
    # coup de chance sur une petite dépense — c'est la raison pour laquelle cette
    # métrique avait été demandée AVEC son budget dès le premier jour.
    _spend, _cpr, _cpr_spend, _cpr_name = (_s.get("meta_spend"), _s.get("best_cpr"),
                                           _s.get("best_cpr_spend"),
                                           _s.get("best_cpr_name"))
    with c6.container(border=True):
        st.metric(t("home.tile_meta", "📊 Meta Ads"),
                  (f"{_spend:,.2f}".replace(",", "\u202f").replace(".", ",")
                   + "\u00a0€") if _spend else "—",
                  delta=_delta(_spend, _s.get("prev_meta_spend")),
                  help=t("home.tile_meta_help",
                         "Dépense publicitaire de la période affichée, et la "
                         "campagne au coût par résultat le plus BAS avec le budget "
                         "qu'elle a consommé."))
        if _cpr:
            st.caption(t("home.tile_best_cpr", "🎯 Meilleur CPR {cpr}{budget}{name}")
                       .format(
                           cpr=f"{_cpr:,.4f}".replace(",", "\u202f")
                               .replace(".", ",") + "\u00a0€",
                           budget=(" · " + f"{_cpr_spend:,.2f}"
                                   .replace(",", "\u202f").replace(".", ",")
                                   + "\u00a0€") if _cpr_spend else "",
                           name=f" — {_cpr_name}" if _cpr_name else ""))


# `_recap_extra` A ÉTÉ SUPPRIMÉE LE 2026-09-12, pas mise de côté. Elle fabriquait
# les lignes « Apple Music / Instagram / Meta Ads » de la table de droite, avec leur
# unité entre parenthèses. Les trois ont désormais leur BOÎTE dans la rangée du haut,
# où elles portent en plus l'écart contre la période précédente. Garder la fonction
# « au cas où » aurait produit ce que ce dépôt paie le plus souvent : du code correct
# que rien n'atteint, et qui pourrit jusqu'à ce qu'on le rebranche sur un écran qui a
# changé sous lui.


def _recap_metrics(side: dict, totals: dict, aligned: dict, span: list,
                   step: str, mode: str, prev_total=None) -> list:
    """Les lignes qui ne sont pas des plateformes — `(libellé, valeur, aide)`.

    « Quelles autres métriques intéressantes on peut rajouter ? » (2026-09-12). Le
    critère retenu n'est pas « laquelle est jolie » mais **laquelle ne coûte rien** :
    aucune ne pose de requête.

    ⚠️ Chaque métrique lit la source qui répond à SA question, pas la plus proche.
    Le meilleur pas vient des listes DESSINÉES (il doit s'accorder à la figure) ; le
    coût par écoute vient de `platform_totals` (il ne doit PAS changer quand on
    bascule le mode d'affichage). Les confondre a produit deux coûts par écoute pour
    la même période, mesurés à l'écran avant livraison.

    l'accueil est à 13 allers-retours pour un plafond de 13 qui ne monte pas. Trois
    des quatre se DÉRIVENT de ce qui est déjà en mémoire — les listes remises à
    Plotly et les totaux déjà calculés — et les deux dernières voyagent dans la
    requête que `period_side_metrics` posait déjà.

    Ce qui est livré, et pourquoi chacune :

    * **Meilleur jour** — la question qu'un artiste pose en premier devant une
      courbe (« c'était quand, le pic ? »), et la figure y répond mal : au pas mois,
      le sommet visible est un seau, pas un jour.
    * **Coût par écoute** — le seul chiffre qui relie les deux moitiés de la page,
      la dépense Meta et les écoutes. Il n'existait nulle part.
    * **Meilleur CPR** — demandé explicitement, avec le budget qui l'a produit :
      « 0,011 € » sans « sur 18 € » laisse croire à une performance reproductible
      alors que c'est peut-être un coup de chance sur une petite dépense.
    * **Probabilité de déclenchement** — ⚠️ une PRÉDICTION, jamais un taux observé.
      Le taux observé demanderait `s4a_song_algo_outcomes`, à **0 ligne** tous
      locataires confondus (mesuré le 2026-09-12). Le libellé porte le mot
      « prédite » ; l'écrire « taux de déclenchement » serait inventer une mesure.

    Une métrique dont l'ingrédient manque ne rend PAS zéro : elle ne rend rien, et
    la ligne n'apparaît pas. Un « 0,00 € » de coût par écoute sur une période sans
    campagne se lirait comme de la publicité gratuite.
    """
    def _eur(v, digits: int = 2) -> str:
        return (f"{v:,.{digits}f}".replace(",", "\u202f").replace(".", ",")
                + "\u00a0€")

    out: list = []
    # LE MEILLEUR PAS, pris sur les listes DESSINÉES — donc au grain affiché, et
    # jamais en contradiction avec la figure.
    #
    # ⚠️ JAMAIS EN CUMULÉ, et ce garde manquait : un commentaire disait « la ligne
    # saute » et rien ne la faisait sauter. Rendu à l'écran le 2026-09-12, il
    # affichait « 📈 Meilleure semaine 286 346 · 01/06/26 » — une série cumulée ne
    # fait que monter, donc son maximum est TOUJOURS son dernier point. Le chiffre
    # était le niveau final, la date la fin de la fenêtre : deux façons de ne rien
    # dire, présentées comme un pic. Même famille que le reste de la séance — une
    # règle juste pour une quantité, fausse pour un niveau de compteur.
    best_i, best_v = None, 0
    if mode != "cumulative":
        for i in range(len(span)):
            tot = sum((aligned.get(k) or [None] * len(span))[i] or 0
                      for k in aligned)
            if tot > best_v:
                best_i, best_v = i, tot
    if best_i is not None and best_v:
        label = {"day": t("home.metric_best_day", "📈 Meilleur jour"),
                 "week": t("home.metric_best_week", "📈 Meilleure semaine"),
                 "month": t("home.metric_best_month", "📈 Meilleur mois"),
                 }.get(step, t("home.metric_best_step", "📈 Meilleur point"))
        out.append((label,
                    f"{int(best_v):,}".replace(",", "\u202f")
                    + f" · {span[best_i].strftime('%d/%m/%y')}", None))

    # LE DÉNOMINATEUR EST `combined_total`, PAS CE QUE LA FIGURE DESSINE — et c'est
    # une correction, pas un détail. Mesuré à l'écran le 2026-09-12 : le coût par
    # écoute valait 0,0170 € en « Par période » et 0,0101 € en « Cumulé », pour la
    # MÊME période et la même dépense. Basculer un mode d'affichage ne change pas ce
    # qu'une écoute a coûté ; c'est le dénominateur qui était faux.
    #
    # La cause est connue et déjà payée : la somme des écarts quotidiens d'un
    # COMPTEUR sous-compte, parce qu'un écart n'existe qu'entre deux jours
    # consécutifs et que les journées non collectées sont perdues (facteur 887
    # mesuré le 2026-09-11). `platform_totals` évite ce piège en lisant la
    # DIFFÉRENCE DE NIVEAU, et c'est le nombre que porte déjà la bannière.
    from src.dashboard.utils.platform_timeseries import combined_total
    streams = combined_total(totals or {})
    sp = (side or {}).get("meta_spend")
    if sp and streams:
        out.append((t("home.metric_cost_per_stream", "💸 Coût par écoute"),
                    f"{sp / streams:,.4f}".replace(",", "\u202f").replace(".", ",")
                    + "\u00a0€",
                    t("home.metric_cost_per_stream_help",
                      "💸 coût par écoute = dépense Meta de la période ÷ écoutes "
                      "de la période (toutes plateformes, pas seulement celles que "
                      "la pub visait)")))

    # LE MEILLEUR CPR N'EST PLUS ICI — il est dans la boîte Meta Ads, au-dessus,
    # « avec l'argent dépensé […] dans la même box » (2026-09-12). Le laisser aussi
    # dans les indicateurs mettrait le même nombre deux fois sur un écran, ce qui est
    # exactement le motif pour lequel la table de droite a été retirée.

    algo_p, algo_name = ((side or {}).get("best_algo_p"),
                         (side or {}).get("best_algo_name"))
    if algo_p:
        out.append((t("home.metric_best_algo", "🔮 Proba. déclenchement prédite"),
                    f"{algo_p * 100:.1f}".replace(".", ",") + " %"
                    + (f" · {algo_name}" if algo_name else ""),
                    t("home.metric_best_algo_help",
                      "🔮 probabilité PRÉDITE par le modèle que le titre le mieux "
                      "placé entre en playlist algorithmique — ce n'est pas un taux "
                      "observé : aucune issue n'a encore été saisie")))

    # ── LES TROIS DE PLUS (2026-09-12), ET AUCUNE NE POSE DE REQUÊTE ──────────
    #
    # Le critère n'a pas changé : une métrique entre si elle se DÉRIVE de ce qui
    # est déjà en mémoire. L'accueil est à 13 allers-retours pour un plafond de 13
    # qui ne monte pas (`test_a_page_asks_the_same_question_once`).

    # LA PART DE LA MEILLEURE PLATEFORME — lue sur les séries DESSINÉES, comme le
    # meilleur pas, pour la même raison : le tableau juste au-dessus affiche ces
    # totaux-là, et deux pourcentages qui ne se recoupent pas sur le même écran
    # valent moins que pas de pourcentage.
    #
    # ⚠️ PAS EN MODE « PART ». `aligned` y porte déjà des pourcentages : en tirer
    # une part donnerait la part d'une part. C'est la faute exacte que le meilleur
    # pas a commise en cumulé, et elle se garde de la même façon — en nommant le
    # régime, pas en espérant que personne n'y aille.
    if mode not in ("share", "cumulative"):
        sums = {k: sum(v for v in (aligned.get(k) or []) if v) for k in aligned}
        tot = sum(sums.values())
        if tot and sums:
            top = max(sums, key=lambda k: sums[k])
            if sums[top]:
                from src.dashboard.utils.platform_timeseries import PLATFORM_LABELS
                out.append((t("home.metric_top_share", "🥇 Plateforme dominante"),
                            f"{PLATFORM_LABELS.get(top, top)} · "
                            + f"{sums[top] / tot * 100:.0f}".replace(".", ",") + " %",
                            t("home.metric_top_share_help",
                              "🥇 la plateforme qui pèse le plus dans la période, et "
                              "sa part des écoutes TRACÉES — Apple n'y entre pas, sa "
                              "série n'existe qu'au pas annuel")))

    # LES PAS RÉELLEMENT MESURÉS — l'information que portait la colonne « mesurés »,
    # retirée le 2026-09-12 (« à quoi correspond la colonne mesurés ? Enlève-la »).
    #
    # Elle avait un défaut de FORME, pas de fond : une colonne oblige chaque ligne à
    # répondre, y compris celles pour qui la question n'a pas de sens, et elle
    # doublait la largeur de la table pour un chiffre qu'on lit une fois. En UNE
    # ligne, à la fin, elle dit ce que la figure montre déjà par ses hachures : sur
    # quelle part de la fenêtre on a vraiment regardé. Un « 165 065 » sur 12 mois
    # mesurés 40 jours n'est pas le même fait qu'un « 165 065 » sur 365.
    if span:
        seen = sum(1 for i in range(len(span))
                   if any((aligned.get(k) or [None] * len(span))[i] is not None
                          for k in aligned))
        if seen and seen < len(span):
            unit = {"day": t("home.step_days", "jours"),
                    "week": t("home.step_weeks", "semaines"),
                    "month": t("home.step_months", "mois"),
                    "year": t("home.step_years", "années")}.get(step, "pas")
            out.append((t("home.metric_measured", "📅 Périodes mesurées"),
                        f"{seen} / {len(span)} {unit}",
                        t("home.metric_measured_help",
                          "📅 le nombre de {unit} où au moins une plateforme a été "
                          "collectée, sur le total de la fenêtre — les autres sont "
                          "les bandes hachurées de la figure").format(unit=unit)))

    # LA VARIATION CONTRE LA PÉRIODE PRÉCÉDENTE N'EST PLUS UNE LIGNE : c'est la
    # FLÈCHE de chaque boîte du haut, une par plateforme au lieu d'un seul chiffre
    # agrégé. L'aide qui l'accompagnait — « ↔️ écart avec la fenêtre de MÊME
    # LONGUEUR qui précède immédiatement celle-ci… » — a été nommée inutile le
    # 2026-09-12, et elle l'était : une flèche verte à côté d'un nombre se lit sans
    # qu'on explique ce qu'elle compare. La règle qu'elle énonçait, elle, n'a pas
    # bougé d'un cran — `_delta()` rend `None` contre une période non mesurée.

    return out


def _render_trend(db, series, since, until, range_key, artist_id,
                  totals=None, side=None) -> None:
    """La figure de l'accueil — pleine largeur depuis que les tuiles sont parties.

    Chaque valeur est une quantité du JOUR : `platform_timeseries` ramène les compteurs
    cumulatifs (SoundCloud, YouTube) à leur écart quotidien, sans quoi la courbe
    additionnerait des totaux-depuis-toujours à des streams quotidiens.
    """
    from src.dashboard.utils.platform_chart import (
        render_missing_history_note, render_platform_chart,
    )

    # QUELLES SOURCES TRACER. Toutes par défaut : le filtre sert à ISOLER une
    # plateforme, pas à en cacher. Les cases ne proposent que ce que la période
    # contient — cocher une source qui n'a rien à dire ne montrerait rien et se
    # lirait comme une panne.
    from src.dashboard.utils.platform_timeseries import (
        PLATFORM_LABELS, STEP_ONLY, measured_days,
    )

    from src.dashboard.utils.platform_chart import MODES

    # ── LE PAS N'EST PLUS UN CHOIX : IL SE DÉRIVE DE LA FENÊTRE ──────────────
    #
    # « on ne devrait pas supprimer le filtre jour semaine mois année et
    # automatiquement trier depuis le début via année ou mois selon la date si
    # >360j et automatiquement mettre par jour si on est à 90jours 30jours ou sur
    # mesure <359j ? » (2026-09-12). Oui — et c'est plus juste que ce que je venais
    # d'écrire.
    #
    # La barre avait d'abord proposé les quatre pas à toutes les fenêtres, ce qui
    # offrait « Année » sur 30 jours : un seau, une figure qui se replie, une note
    # sous elle pour s'en excuser. J'avais corrigé en FILTRANT la barre selon la
    # fenêtre. C'était encore une demi-mesure : le pas pertinent est entièrement
    # déterminé par la fenêtre, donc le demander est demander à l'artiste de
    # trancher une question dont la réponse est calculable. Un contrôle dont toutes
    # les options sauf une sont mauvaises n'est pas un contrôle, c'est un piège.
    #
    # LA RÈGLE, telle qu'énoncée, avec une seule addition MESURÉE :
    #   * fenêtre < `_DAY_UNTIL_YEAR` jours  → **jour** (30 j, 90 j, sur mesure)
    #   * fenêtre ≥ `_DAY_UNTIL_YEAR`        → **mois**, sauf si le mois rendrait
    #     plus de `_MAX_BUCKETS` points, auquel cas **année**
    #   * « Depuis le début » (fenêtre inconnue) → même règle, sur l'étendue réelle
    #     des données
    #
    # Le garde-fou du haut n'est pas un seuil de confort : au-delà, les points se
    # chevauchent et la courbe devient une bande. Il ne se déclenche qu'au-delà de
    # cinq ans d'historique — aucun locataire n'y est (le plus ancien porte
    # 1 344 jours, mesuré le 2026-09-12), donc il est écrit pour le jour où ça
    # arrivera, pas pour aujourd'hui.
    #
    # ⚠️ CE QUE ÇA COÛTE, ET IL FAUT LE DIRE : **Apple Music ne sera plus jamais
    # tracée.** Sa série n'existe qu'au pas ANNUEL (`STEP_ONLY`) — ses exports sont
    # des totaux de dépôt, pas des quantités du jour — et le pas annuel n'est plus
    # atteignable que sur plus de cinq ans de données. Son total n'est pas perdu
    # pour autant : il est dans sa BOÎTE, en haut, où il est même plus lisible qu'un
    # point isolé sur une courbe. C'est un arbitrage assumé, pas un oubli.
    _window_days = (until - since).days if since and until else None
    if _window_days is None:
        # « Depuis le début » : la fenêtre est celle des données, pas du filtre.
        _dates = [d for rows in (series or {}).values() for d, _v in rows]
        _window_days = (max(_dates) - min(_dates)).days if _dates else 0

    if _window_days < _DAY_UNTIL_YEAR:
        step = 'day'
    elif _window_days / 30 <= _MAX_BUCKETS:
        step = 'month'
    else:
        step = 'year'

    # LE MODE, en barre lui aussi : « je pense que c'est mieux de mettre des cases à
    # cocher plutôt qu'un onglet déroulant pour voir toutes les possibilités direct ».
    # Un seul mode à la fois — deux figures empilées doubleraient la hauteur de page
    # et le plafond de figures du premier écran est à cinq.
    # DEUX BARRES EMPILÉES, pleine largeur, dans l'ordre où on les lit.
    #
    # Elles partageaient une rangée en 3/2/1 avec une TROISIÈME colonne — le filtre
    # de sources — qui n'existe qu'en mode « part », donc vide trois fois sur
    # quatre tout en occupant 1/6 de la largeur en permanence. Le partage forçait
    # aussi la barre de mode à 3/5, juste assez pour que ses libellés tiennent.
    #
    # Pleine largeur, plus rien n'est contraint : les quatre modes tiennent sur une
    # ligne, et le filtre de sources est rendu plus bas, uniquement quand il existe.
    mode = st.segmented_control(
        t("home.trend_mode", "Affichage"), list(MODES),
        format_func=lambda k: t(f"home.mode_{k}", MODES[k]),
        default="cumulative",
        key=f"home_trend_mode_{artist_id}", label_visibility="collapsed",
    ) or "cumulative"

    # LE GRAIN EST AFFICHÉ, MÊME S'IL N'EST PLUS CHOISI — et c'est la contrepartie
    # de l'avoir automatisé. Un axe dont le pas change sous le curseur sans un mot
    # est exactement le défaut que ce module garde depuis le 2026-09-08 : un réglage
    # appliqué en silence se lit comme une panne. Ici il n'y a pas de réglage repris,
    # mais il y a un fait que le lecteur ne peut pas deviner en regardant l'axe —
    # « chaque point est un mois » n'est pas lisible sur une courbe de 44 points.
    st.caption({
        'day': t("home.grain_day", "Chaque point est un **jour**."),
        'month': t("home.grain_month", "Chaque point est un **mois** — la fenêtre "
                                       "dépasse un an, le pas du jour la rendrait "
                                       "illisible."),
        'year': t("home.grain_year", "Chaque point est une **année**."),
    }.get(step, ""))

    available = [k for k in PLATFORM_LABELS
                 # Une source qui n'existe qu'à un pas donné n'est proposée qu'à ce
                 # pas-là : la cocher ailleurs ne montrerait rien et se lirait comme
                 # une panne.
                 if (STEP_ONLY.get(k) is None or STEP_ONLY[k] == step)
                 and measured_days(series, k, since, until)]
    # LE FILTRE DE SOURCES EST LA LÉGENDE DE LA FIGURE, sauf en mode « part ».
    #
    # « Peut-on intégrer le clickage des plateformes directement sur le graphique
    # plutôt qu'avec le filtre qui doit sélectionner ? ça enlèverait de la
    # complexité » (2026-09-11). Un clic de légende est côté navigateur : il ne
    # relance pas le script. Le `multiselect`, lui, coûtait un rendu complet — 287 ms
    # mesurés en production — pour masquer une bande.
    #
    # « Part de chaque plateforme » est l'exception, et pour une raison de calcul et
    # non de goût : ses pourcentages sont établis sur l'ensemble AFFICHÉ, et un clic
    # de légende masque une trace sans recalculer les autres. La pile ne ferait plus
    # 100 %, ce qui est un chiffre faux et pas seulement une figure incomplète.
    chosen = available
    if mode == "share" and len(available) > 1:
        chosen = st.multiselect(
            t("home.trend_sources", "Sources affichées"), available,
            default=available, format_func=lambda k: PLATFORM_LABELS[k],
            key=f"home_trend_sources_{artist_id}",
            label_visibility="collapsed",
            placeholder=t("home.trend_sources_ph", "Toutes les sources")) or available

    if step != 'year' and any(k in series and series[k] for k in STEP_ONLY):
        st.caption(t(
            "home.trend_apple_hint",
            "🎎 **Apple Music** n'apparaît qu'au pas **Par année** : ses exports sont "
            "des totaux de période, pas des chiffres du jour. L'étaler sur 365 jours "
            "inventerait une valeur que personne n'a mesurée."))

    # Le mode « Cumulé » ne reconstruit pas le cumul des plateformes à COMPTEUR : il
    # lit celui de la couche or, dont le dernier point est le total que les tuiles
    # affichent juste au-dessus. Sans lui, la somme courante d'une série de
    # DIFFÉRENCES n'additionne que les journées consécutives — mesuré le 2026-09-11
    # sur l'artiste 1 : 21 pour YouTube au lieu de 118 219, 8 pour SoundCloud au lieu
    # de 23 486.
    from src.dashboard.utils.platform_timeseries import (cumulative_by_platform,
                                                          discarded_deltas)
    cumulative = cumulative_by_platform(db, artist_id)
    # Ce que la conversion cumul → quotidien jette. La figure décide si la phrase
    # s'applique : elle seule connaît le pas retenu quand l'utilisateur a dit
    # « Automatique ».
    _discarded = discarded_deltas(db, artist_id)

    # LE RÉCAPITULATIF EST À DROITE DE LA FIGURE, et il est CONSTRUIT PAR ELLE.
    #
    # « Où est passé le tableau juste à côté du graphique qui montre les métriques »
    # (2026-09-12). Il avait été retiré le 2026-09-10 parce qu'il montrait le total
    # DEPUIS LE DÉBUT à côté d'une courbe bornée à la période : deux chiffres qui ne
    # se répondaient pas. Le conteneur est passé à la figure, qui le remplit avec les
    # listes qu'elle vient de remettre à Plotly — aucune requête neuve, et aucune
    # possibilité de divergence.
    # ── LE RÉCAPITULATIF À DROITE DE LA FIGURE A ÉTÉ RETIRÉ LE 2026-09-12 ─────
    #
    # « supprime-le et remplace-le par celui qu'on a validé qui est actuellement
    # placé en haut du graphique ». Il y avait DEUX récapitulatifs sur le même
    # écran — les boîtes au-dessus et cette table markdown à droite — et ils
    # répondaient à la même question avec deux mises en page. Le dépôt connaît le
    # prix de deux surfaces pour un même nombre : c'est la raison même pour
    # laquelle les tuiles avaient été retirées le 2026-09-10.
    #
    # Ce qui a été CONSERVÉ, et où : les totaux par plateforme, Instagram, Apple et
    # Meta Ads vivent dans les boîtes du haut, avec en plus l'écart contre la
    # période précédente que la table ne portait pas. Le meilleur CPR et son budget
    # sont dans la boîte Meta. Rien de ce que la table affichait n'a disparu de
    # l'écran — c'est la CONDITION pour retirer une surface, et pas seulement la
    # politesse : une suppression qui perd une information est une régression
    # déguisée en simplification.
    #
    # Sont parties avec elle les aides que l'artiste a nommées comme inutiles — la
    # ligne « 🔮 probabilité PRÉDITE … · ↔️ écart avec la fenêtre de MÊME LONGUEUR
    # … » était le `st.caption` de cette table. L'écart, lui, est devenu une flèche
    # dans chaque boîte : il se lit, il ne se raconte plus.
    #
    # La figure prend donc toute la largeur, comme entre le 2026-09-10 et le
    # 2026-09-12.
    drawn = render_platform_chart(
        series, since=since, until=until, only=chosen, step=step, mode=mode,
        cumulative=cumulative, discarded=_discarded,
        # `recap=True` ET NON UNE COLONNE : sans conteneur, les indicateurs
        # tombent là où la figure les rend — juste sous elle, dans l'ordre de
        # lecture. C'est le seul endroit d'où l'on connaît le grain RÉELLEMENT
        # retenu quand l'artiste a laissé « Automatique ».
        recap=True,
        # UN RAPPEL, pas une liste toute faite : les métriques dérivées doivent
        # être calculées sur les séries que la figure a RÉELLEMENT dessinées.
        recap_metrics=lambda al, sp, _gr, st_, md: _recap_metrics(
            side, totals, al, sp, st_, md),
        key=f"home_trend_{artist_id}")
    if not drawn:
        # DEUX SILENCES TRÈS DIFFÉRENTS, ET UN SEUL MESSAGE LES DISAIT.
        #
        # Vu au navigateur le 2026-09-12, sur « 90 jours · Jour · Par période » :
        # l'écran affichait « pas encore assez d'historique » à un locataire qui a
        # **quatre ans** de mesures. La vérité était « rien n'a été mesuré dans
        # cette fenêtre » — le CSV Spotify n'avait pas été déposé depuis 92 jours,
        # c'est-à-dire exactement le cas que cette séance traite.
        #
        # Un message qui se trompe de cause envoie l'artiste chercher le mauvais
        # geste : le premier fait attendre, le second demande un import. C'est la
        # même famille que la note qui décrivait une autre figure, et elle se règle
        # de la même façon — dériver le texte de l'état, pas l'écrire à côté.
        _last = max((d for rows in (series or {}).values() for d, _ in rows),
                    default=None)
        if _last is not None and since is not None and _last < since:
            st.warning(t(
                "home.trend_nothing_in_window",
                "Aucune mesure sur cette période. La dernière remonte au **{last}** "
                "— dépose un export récent, ou élargis la fenêtre pour revoir "
                "l'historique."
            ).format(last=_last.strftime("%d/%m/%Y")))
        else:
            st.info(t(
                "home.trend_no_series",
                "Pas encore assez d'historique pour tracer une évolution : il faut "
                "au moins deux journées de collecte consécutives sur une "
                "plateforme."))
        return
    # LA LÉGENDE EST PARTIE DANS LE MODULE DE LA FIGURE, le 2026-09-10.
    #
    # Elle était fixe ici et disait « Écoutes **du jour** […] un blanc dans la bande
    # […] pas de mesure ce jour-là » sous TOUS les modes et TOUS les pas. En
    # « Chacune à son échelle · Par année », les trois affirmations étaient fausses en
    # même temps : les points portaient des totaux ANNUELS, il n'y avait pas de bande
    # mais des facettes, et un blanc ne parlait pas d'un jour.
    #
    # Elle ne pouvait pas être juste depuis ici : cette vue connaît le pas DEMANDÉ, et
    # « Automatique » n'en est pas un — seul le module sait lequel a été retenu. Le
    # texte vit désormais à côté du comportement dont il parle (`t_trend_caption`),
    # rendu par `_render_notes` avec les autres explications.

    # CE QUE LA FIGURE NE TRACE PAS, DIT PLUTÔT QUE TU.
    #
    # Pour un compteur cumulé, l'écart n'est calculé qu'entre deux jours CONSÉCUTIFS :
    # entre deux relevés distants de neuf jours on sait ce qui s'est passé EN TOUT,
    # jamais quel jour, et l'attribuer au dernier inventerait un pic. Ces écoutes-là
    # sont donc écartées — et elles l'étaient EN SILENCE.
    #
    # Mesuré le 2026-09-10 sur l'artiste 1 : la figure trace 21 écoutes YouTube et en
    # écarte 167. Une figure qui montre un neuvième du volume sans le dire se lit comme
    # une plateforme morte.
    render_missing_history_note()


_DAG_LABELS = {
    "spotify_api_daily":        ("🎵", "Spotify API"),
    "youtube_daily":            ("🎬", "YouTube"),
    "soundcloud_daily":         ("☁️", "SoundCloud"),
    "instagram_daily":          ("📸", "Instagram"),
    "meta_ads_api_daily":       ("📊", "Meta Ads"),
    "ml_scoring_daily":         ("🤖", "ML Scoring"),
    "data_quality_check":       ("🔍", "Qualité données"),
}

_STATE_COLOR = {
    "success": ("#00CC96", "🟢"),
    "failed":  ("#EF553B", "🔴"),
    "running": ("#636EFA", "🔵"),
    "queued":  ("#FFA500", "🟡"),
}


def _section_onboarding(db, artist_id: int) -> None:
    """Brick 29 — Onboarding progress tracker for new artists."""
    # La définition des quatre étapes vit dans `utils.setup_completion`, pas ici.
    # Elle était écrite ICI et l'aiguillage d'accueil en posait une AUTRE (« l'artiste
    # n'a-t-il rien branché du tout ? ») : deux surfaces, même question, réponses
    # opposées dès la deuxième connexion. Une seule règle, deux lecteurs.
    from src.dashboard.utils.setup_completion import (
        STEP_LABELS, read_setup_state)

    # LE PLAN FILTRE LES ÉTAPES : une étape qui mène à une page verrouillée
    # enverrait l'artiste sur le paywall depuis son parcours de mise en route.
    from src.dashboard.auth import get_artist_plan
    state = read_setup_state(db, artist_id, st.session_state.get('user_id'),
                             plan=get_artist_plan())
    if not state.steps:
        return

    steps = [(s.done, STEP_LABELS[s.key](), s.page, s.detail, s.key)
             for s in state.steps]
    completed = state.done_count
    all_done = state.complete

    # LE BANDEAU EST REPLIÉ QUAND LA CONFIGURATION EST FINIE, et déplié tant qu'elle
    # ne l'est pas. Demandé le 2026-09-08.
    #
    # C'est la même information dans les deux cas ; ce qui change est ce qu'elle
    # DEMANDE. Tant qu'il reste une étape, le bandeau est la première chose à faire et
    # il occupe la place ; une fois terminé, il ne réclame rien et n'a plus à pousser
    # les chiffres vers le bas à chaque visite. Le repli n'est pas un masquage : le
    # titre porte le verdict, et on l'ouvre pour revoir le détail.
    header = (t("home.onboarding_done_header",
                "✅ Mise en route — configuration terminée") if all_done
              else t("home.onboarding_progress",
                     "🚀 Mise en route — {done}/{total} étapes complétées").format(
                         done=completed, total=len(steps)))
    with st.expander(header, expanded=not all_done):
        _render_onboarding_body(db, artist_id, steps, completed, all_done)


def _render_step_detail(detail) -> None:
    """Le listing OK / NOK sous une étape, quand elle en a un.

    « Rajoute sur la ligne configurer api la liste de toutes les plateformes avec
    mention OK, NOK », et de même pour les imports (2026-09-12). L'étape disait
    « fait / pas fait » et l'artiste devait ouvrir la page pour savoir CE QUI
    manquait — la même plainte que la matrice d'état avait déjà réglée pour les
    plateformes : un verdict global n'indique aucun geste.

    ⚠️ LE DÉTAIL N'EST PAS LA CONDITION. Une étape est cochée dès qu'UNE ligne est
    OK ; les NOK disent ce qu'il reste à gagner, ils ne bloquent pas. Exiger les
    huit types d'import laisserait la ligne rouge à vie pour un artiste sans SACEM
    ni DistroKid — l'erreur exacte de l'ancienne étape Apple obligatoire, qui
    tenait l'autostart à l'arrêt.
    """
    if not detail:
        return
    # LA COULEUR PORTE LE VERDICT, PLUS LE MOT. « Vu qu'on a mis les cases vertes,
    # retire les OK » (2026-09-12) : « ✅ spotify OK » disait deux fois la même
    # chose, et la répétition allongeait la ligne au point de la faire passer sur
    # deux rangées avec huit types de fichiers.
    #
    # ⬜ était le mauvais signe pour le manque : un carré blanc se lit « pas encore
    # regardé », pas « il manque quelque chose ». ❌ le dit, et il se distingue de ✅
    # par la FORME autant que par la couleur — un lecteur daltonien voit une croix
    # contre une coche, pas deux gris.
    st.caption(" · ".join(f"{'✅' if ok else '❌'} {name}" for name, ok in detail))


def _render_step_hint(key: str) -> None:
    """Ce que l'étape RAPPORTE, quand son nom ne le dit pas.

    Seule la saisie S4A en porte un : c'est la seule étape dont le bénéfice n'est
    pas devinable depuis le geste — saisir des ajouts en playlist ne rend rien tout
    de suite, ça nourrit les modèles. Une étape dont on ne voit pas le gain est une
    étape qu'on saute, et c'est celle dont dépend la précision des prédictions.
    """
    from src.dashboard.utils.setup_completion import STEP_HINTS
    hint = STEP_HINTS.get(key)
    if hint is not None:
        st.caption(hint())


def _render_onboarding_body(db, artist_id: int, steps, completed: int,
                            all_done: bool) -> None:
    """Le CONTENU du bandeau, extrait pour qu'il puisse être replié.

    Extrait tel quel le 2026-09-08 : le corps n'a pas changé, seul son contenant. Le
    titre, lui, a quitté le corps — il est devenu l'étiquette du repli, sans quoi il
    aurait été écrit deux fois.
    """
    if all_done:
        st.success(t("home.onboarding_done", "Toutes les étapes de mise en route sont complètes. 🎉"))
    else:
        st.progress(completed / len(steps))
        # Ce que la coche MESURE. Un artiste en test a cliqué « Connecter ma
        # sélection », est arrivé sur la page, et s'est étonné que la case reste
        # vide : « ça ne coche pas le rond de données credentials API, c'est
        # confus ». La case suit l'ACTION, pas la visite — la cocher à l'arrivée
        # dirait que c'est fait alors que rien n'est enregistré.
        st.caption(t("home.onboarding_ticks_on_action",
                     "Une étape se coche quand l'action est **faite**, pas quand la "
                     "page est ouverte."))

    # Les quatre étapes NOMMAIENT leur destination sans y mener : la clé de page était
    # liée à `_page` puis jetée, et les lignes étaient du `st.markdown`. Un artiste en
    # test l'a dit ainsi — « lien cliquable mise en route dans la page d'accueil ».
    # Few (*Information Dashboard Design*) : un tableau de bord sert de rampe de
    # lancement, on clique la donnée elle-même. Une étape faite reste du texte : il n'y
    # a rien à y faire, et un bouton inutile est du bruit.
    for idx, (done, label, page_key, detail, key) in enumerate(steps):
        if done:
            st.markdown(f"✅ {label}")
            _render_step_hint(key)
            _render_step_detail(detail)
            continue
        # L'étape « lancer ta première collecte » NOMMAIT le geste et envoyait vers une
        # autre page pour le faire ; le bouton, lui, est dans la barre latérale. Deux
        # endroits pour une action, c'est une consigne — et une consigne est ce qu'on
        # écrit quand le bouton est ailleurs. Elle le fait maintenant elle-même.
        if page_key == "onboarding" and idx == len(steps) - 1:
            if st.button(f"⬜ {label}", key=f"home_step_{idx}",
                         width="stretch", type="primary"):
                _launch_collections()
            continue
        if st.button(f"⬜ {label}", key=f"home_step_{idx}",
                     width="stretch"):
            goto(page_key)
        _render_step_hint(key)
        _render_step_detail(detail)

    # One compact line of per-platform boxes, only while something is still amber or
    # red. The steps above are STAGES ("import a CSV"); this is per PLATFORM, which
    # is the axis an artist actually asks about — "is my SoundCloud working?".
    if not all_done:
        st.caption(t("home.matrix_caption",
                     "Par plateforme — survole une case pour le détail :"))
        render_status_matrix(db, artist_id, compact=True, allow_probe=False,
                             key_suffix="home")


def _launch_collections() -> None:
    """Déclenche les collectes de CE locataire, depuis l'étape qui les nomme."""
    from src.dashboard.utils.collection_trigger import trigger_all_collections
    from src.dashboard.utils.collection_progress import (
        remember_not_launched, remember_runs)

    try:
        from src.utils.airflow_trigger import AirflowTrigger
        from src.dashboard.app import COLLECTION_DAGS      # noqa: PLC0415
    except Exception:      # noqa: BLE001 — hors app : le bouton ne doit pas casser la page
        st.warning(t("home.launch_unavailable",
                     "⚠️ Le déclenchement n'est pas disponible ici. Utilise le bouton "
                     "Elle démarre aussi d'elle-même dès que tu enregistres des identifiants."))
        return

    artist_id = tenant_scope()
    with st.status(t("home.launching", "Lancement des collectes…"), expanded=False):
        launched, not_launched = trigger_all_collections(
            artist_id, AirflowTrigger(), COLLECTION_DAGS)
    remember_runs(launched)
    remember_not_launched(not_launched)
    if launched:
        st.success(t("home.launched",
                     "🚀 Collecte lancée — tes premiers chiffres arrivent dans "
                     "~2 minutes. Recharge la page pour les voir.").format())
    if not_launched:
        st.error(t("home.launch_refused",
                   "❌ {n} collecte(s) refusée(s) : {why}").format(
                       n=len(not_launched),
                       why=" · ".join(f"{k} — {v}" for k, v in not_launched.items())))


def _section_dag_status():
    """Résumé du dernier run de chaque DAG. **Admin seulement.**

    Cette section montre l'état Airflow de TOUTE LA FLOTTE : `get_dag_list()` ne
    prend pas d'`artist_id`, et il n'en existe pas de version par locataire — un run
    de DAG appartient à l'infrastructure, pas à un artiste.

    Rapporté par un artiste en test le 2026-08-30, sur un compte créé la minute
    d'avant, sans une seule credential : « DAG spotify_api_daily — 🟢 success —
    dernier run 15:27 ». Il a demandé si c'était le bug des données d'un autre.
    Ce n'en est pas un — aucune donnée d'artiste ne fuit — mais l'effet est pire
    qu'inutile : un vert affiché à quelqu'un qui n'a rien connecté lui dit que sa
    collecte a fonctionné.

    Sa remarque suivante tranche le sort de la section : « cette ligne n'a rien à
    faire là, on s'en fout ici vu qu'on a déjà l'état des plateformes ». La matrice
    Configuré / Répond / Données répond à SA question, par locataire. Celle-ci
    répond à la mienne.
    """
    from src.dashboard.auth import is_admin
    if not is_admin():
        return

    st.subheader(t("home.dag_header", "🚦 Statut des pipelines"))

    monitor = AirflowMonitor()
    try:
        dag_list = monitor.get_dag_list()
    except Exception:
        st.warning(t("home.airflow_unreachable", "API Airflow inaccessible — démarrer Docker."))
        return

    if not dag_list:
        st.warning(t("home.no_dags", "Aucun DAG trouvé. Vérifier que Airflow est lancé."))
        return

    # Single batch call for every DAG's latest run (was N+1: one call per DAG).
    # Cached 60 s: 16 HTTP round-trips, re-paid on every widget interaction.
    last_states = cached_last_run_per_dag()
    rows = []
    for dag_id in dag_list:
        r = last_states.get(dag_id)
        if not r:
            rows.append((dag_id, None, None, None))
        else:
            rows.append((dag_id, r['state'], r['start_date'], r['end_date']))

    # Grille responsive : 5 colonnes
    n_cols = 5
    cols = st.columns(n_cols)
    for i, (dag_id, state, start, end) in enumerate(rows):
        icon_dag, label = _DAG_LABELS.get(dag_id, ("⚙️", dag_id))
        label = t(f"home.dag.{dag_id}", label)
        color, state_icon = _STATE_COLOR.get(state, ("#888888", "⚫"))
        state_label = state or t("home.never_run", "jamais lancé")
        date_str = start[:16].replace("T", " ") if start else "—"

        with cols[i % n_cols]:
            st.markdown(
                f"""<div style="border:1px solid {color};border-radius:8px;
                    padding:8px 10px;background:{color}18;text-align:center;margin-bottom:8px;">
                    <div style="font-size:1.4em">{icon_dag}</div>
                    <div style="font-weight:600;font-size:0.8em;white-space:nowrap">{label}</div>
                    <div style="font-size:0.85em">{state_icon} {state_label}</div>
                    <div style="font-size:0.65em;color:#888">{date_str}</div>
                </div>""",
                unsafe_allow_html=True,
            )


def show():
    # Pas de filet sous le titre ni sous le bandeau de mise en route. Demandé le
    # 2026-09-08 : « enlève les 2 traits blancs qui entourent mise en route ». Un
    # séparateur sépare deux choses ; celui-ci encadrait un bloc qui porte déjà sa
    # propre bordure d'accordéon, donc il doublait un trait déjà là.
    # PAS DE TITRE DE PAGE — retiré le 2026-09-12 sur demande. Il redisait ce que
    # la barre latérale et l'onglet du navigateur portent déjà, en occupant la
    # première hauteur d'écran : l'artiste connaît le nom du produit sur lequel il
    # vient de se connecter. Ce que cet espace doit porter, ce sont ses chiffres.
    #
    # ⚠️ LA CLÉ `home.title` PART AVEC LUI. J'ai d'abord écrit ici qu'elle servait
    # au titre de l'onglet et à la navigation, donc qu'il fallait la garder. C'était
    # FAUX — `grep -rn "home.title" src/` ne rend que le catalogue lui-même. Un
    # commentaire qui justifie de garder quelque chose, et que le code dément, est
    # exactement la classe `a-prose-claim-that-cannot-be-verified` : il aurait
    # protégé une entrée morte pour toujours, parce que personne ne revérifie une
    # raison écrite. Vérifié, puis retirée — et `test_no_orphan_en_keys` l'aurait
    # attrapée de toute façon, ce qui est le bon ordre : le garde ne remplace pas
    # la vérification, il la rattrape.
    artist_id = tenant_scope()  # None = admin only, never a stray artist

    with project_db() as db:
        try:
            # Onboarding tracker — only shown to artists with incomplete setup
            if artist_id is not None:
                _section_onboarding(db, artist_id)

            _section_streams(db, artist_id)
            # PDF shortcut removed here — redundant with the dedicated "📄 Export PDF" page.
            # Pas de filet avant la fraîcheur : demandé le 2026-09-08, « retire les
            # 2 traits au-dessus de fraîcheur des données ». Les sous-titres suffisent
            # à séparer trois blocs qui ne se ressemblent pas.
            _section_dag_status()
            _section_freshness(db, artist_id)
        except Exception as e:
            st.error(t("home.display_error", "Erreur d'affichage : {err}").format(err=e))
