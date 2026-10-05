"""La grille « ce qui alimente tes chiffres » — chaque source, sa date, son heure.

Type: Sub
Uses: kpi_helpers (get_source_freshness, freshness_state, freshness_status, SOURCES_CONFIG),
      absence_cta, date_format
Triggers: views/onboarding_health.py (vue artiste)
Persists in: nothing

R373 (2026-10-05) : partie de l'accueil (V6, « on s'en fout ici »). Elle n'avait pas
d'autre maison côté artiste — Alertes, qui lit la même fraîcheur, est réservée à
l'admin. Santé onboarding est la page où l'on vient demander « qu'est-ce qui manque,
qu'est-ce qui arrive et quand » : elle l'héberge désormais. Les clés `home.freshness_*`
gardent leur nom — les renommer n'achèterait rien et rouvrirait 2 catalogues.
"""
import html as _html

import streamlit as st

from src.dashboard.utils.date_format import format_date
from src.dashboard.utils.i18n import t
from src.dashboard.utils.kpi_helpers import (
    SOURCES_CONFIG, freshness_state, freshness_status, get_source_freshness,
)


def render_source_freshness(db, artist_id, etat=None) -> None:
    """Deux groupes, parce que ce sont deux CONTRATS différents.

    Les huit sources étaient sur une seule ligne, sous un paragraphe qui expliquait
    en prose laquelle était automatique et laquelle attendait un fichier. Le lecteur
    devait donc retenir une liste pour interpréter une grille — et l'information qui
    compte vraiment, « à quelle heure ça arrive », n'était nulle part.

    Chaque source porte désormais son contrat (`kind`) et son heure (`at`) dans
    `SOURCES_CONFIG`, et la grille les montre là où on les lit : sous la source.
    """
    st.subheader(t("home.freshness_header", "📡 Ce qui alimente tes chiffres"))
    freshness = get_source_freshness(db, artist_id)
    meta = {src["label"]: src for src in SOURCES_CONFIG}

    # ── CE QUI MANQUE, ET CE QU'IL Y A À FAIRE ────────────────────────────────
    #
    # Ajouté le 2026-09-22. Avant, une source sans donnée affichait « — » et
    # s'arrêtait : sur les six locataires bêta de production, QUATRE n'avaient rien
    # nulle part, donc leur accueil était un écran de tirets sans une seule
    # indication de quoi faire.
    #
    # Yifrah, *Microcopy* p.129 : « au lieu de dire qu'il n'y a rien ici, écris ce
    # qui est censé s'y trouver ou ce qu'on peut y faire […] fournis un lien. »
    #
    # ⚠️ Zéro requête : `freshness` est déjà en main, et `plan` est résolu une fois
    # ici plutôt qu'une fois par carte. L'accueil est à son plafond d'allers-retours.
    absentes = [meta[lbl] for lbl, info in freshness.items()
                if info["last_dt"] is None and lbl in meta]
    if absentes:
        from src.dashboard.auth import get_artist_plan
        from src.dashboard.utils.absence_cta import render_absence_list

        # ⚠️ TANT QUE LA MISE EN ROUTE N'EST PAS FINIE, CES CARTES SE REPLIENT —
        # et c'est un défaut trouvé en REGARDANT le rendu, qu'aucun test ne voyait.
        #
        # Un locataire vide se retrouvait devant TROIS surfaces qui répondent à la
        # même question : le bandeau de mise en route (quatre étapes), sa matrice par
        # plateforme, et ces dix cartes. Trois fois « voilà ce qu'il te reste à
        # faire », dans trois vocabulaires différents.
        #
        # Les deux ne sont pas redondantes, elles sont à deux GRAINS : le bandeau est
        # par ÉTAPE (« importe tes fichiers »), les cartes sont par PLATEFORME (« ton
        # SoundCloud n'est pas branché »). Tant qu'il reste une étape, le bandeau est
        # la bonne réponse et il occupe la place ; une fois la mise en route terminée,
        # c'est l'axe plateforme que l'artiste vient chercher.
        en_route = etat is not None and not etat.complete
        st.caption(t("home.absence_intro",
                     "Ces sources ne sont pas encore branchées — chacune ajoute une "
                     "pièce à tes chiffres :"))
        if en_route:
            titre = t("home.absence_repli",
                      "Voir les {n} sources à brancher, une par une").format(
                          n=len(absentes))
            with st.expander(titre, expanded=False):
                render_absence_list(absentes, plan=get_artist_plan(),
                                    limite=len(absentes), prefixe="home_")
        else:
            render_absence_list(absentes, plan=get_artist_plan(), prefixe="home_")
        st.markdown("")

    # Deux titres, aucune glose. « 🔄 Collecte automatique » et « 📂 À déposer
    # toi-même » disent déjà tout ce que les deux phrases retirées le 2026-09-12
    # répétaient ; et chaque tuile d'API porte son heure, ce que la phrase ne
    # faisait pas.
    groups = (
        ("api", t("home.freshness_api", "🔄 Collecte automatique")),
        ("csv", t("home.freshness_csv", "📂 À déposer toi-même")),
    )
    for kind, title in groups:
        # Seules les sources qui ONT une mesure : les autres sont traitées au-dessus,
        # avec leur geste. Une tuile à « — » répétait l'absence sans rien en dire.
        # ⚠️ `mesure_dt` ET NON `last_dt` : la présence se juge sur la date que la
        # donnée PORTE, pas sur celle où on l'a écrite. Une table que le DAG réécrit
        # chaque matin a toujours une date d'écriture.
        labels = [lbl for lbl in freshness
                  if meta.get(lbl, {}).get("kind") == kind
                  and freshness[lbl].get("mesure_dt") is not None]
        if not labels:
            continue
        st.markdown(f"**{title}**")
        cols = st.columns(len(labels))
        for col, label in zip(cols, labels):
            info = freshness[label]
            # Le BARÈME suit le contrat de la source : un CSV non redéposé
            # depuis trois jours n'est pas une panne, une API muette si.
            # ── LE VERDICT SE CALCULE SUR LA DATE DE MESURE ────────────────────
            #
            # ⚠️ Il se calculait sur `last_dt`, la date d'ÉCRITURE. Mesuré en
            # production le 2026-09-22 : `meta_insights_performance_day` porte un
            # `MAX(collected_at)` du jour même et un `MAX(day_date)` au **2024-09-30**
            # — **722 jours**. La tuile affichait « 🟢 il y a 0h » ET la date
            # d'aujourd'hui : la couleur et la date mentaient ENSEMBLE, ce qui est pire
            # qu'une seule des deux. La supervision admin lit la bonne colonne depuis
            # R154 : deux surfaces répondaient différemment à la même question.
            _mesure = info.get("mesure_dt")
            emoji, color, age_label = freshness_status(_mesure, kind)
            date_str = format_date(_mesure)
            at = meta.get(label, {}).get("at")
            when = (t("home.freshness_every_day", "chaque jour à {h}").format(h=at)
                    if at else t("home.freshness_on_upload", "à chaque import"))

            # ── QUAND DIRE QUE LES DEUX DATES DIVERGENT ────────────────────────
            #
            # ⚠️ AUCUN SEUIL NEUF, et c'est le point. On le dit quand les deux dates
            # ne rendent pas le MÊME VERDICT sur le barème qui existe déjà. Un écart
            # d'un jour est normal — un export quotidien décrit la veille — et il ne
            # change aucun verdict, donc il reste muet. Mesuré le 2026-09-22 sur les
            # dix sources : cette règle parle pour Meta (720 j, `attention` →
            # `perime`) et Hypeddit (1 j, `frais` → `attention`), et se taît sur SACEM
            # (65 j, `perime` des deux côtés — l'écart ne change pas le geste).
            #
            # Un seuil en jours aurait demandé une distribution ; il n'y en a pas
            # (dix sources, six valeurs). Le barème, lui, est déjà calibré.
            _ecrit = info.get("last_dt")
            _written = ""
            if _ecrit is not None and _mesure is not None and (
                    freshness_state(_ecrit, kind) != freshness_state(_mesure, kind)):
                _written = t("home.freshness_written", "collecte du {d}").format(
                    d=format_date(_ecrit))
            col.markdown(freshness_tile_html(color, str(info['icon']), label, emoji,
                                             age_label, date_str, when, _written),
                         unsafe_allow_html=True)


def freshness_tile_html(color: str, icon: str, label: str, emoji: str, age_label: str,
                        date_str: str, when: str, written: str = "") -> str:
    """One freshness tile as HTML on a SINGLE line. Pure.

    R346 (2026-10-04): the divergence line, "" in the usual case, sat alone on its line
    in a multi-line f-string. An empty value left a blank line, CommonMark closed the
    HTML block there, and the indented `</div>` after it rendered as literal text under
    every tile of « Collecte automatique » / « À déposer toi-même ». The parts are now
    joined with no separator, so no value — empty or not — can open a blank line.

    HIGH-07: every interpolated value is escaped — defence-in-depth against stored XSS
    if a DB-sourced value ever reaches these arguments — and its whitespace is collapsed,
    so a value carrying "\\n\\n" cannot reopen the blank line either.
    """
    def e(s: str) -> str:
        return _html.escape(" ".join(str(s).split()))

    parts = [
        f'<div style="border:1px solid {e(color)}; border-radius:8px; padding:8px 6px; '
        f'background:{e(color)}18; text-align:center;">',
        f'<div style="font-size:1.2em;">{e(icon)}</div>',
        f'<div style="font-weight:600; font-size:0.8em; white-space:nowrap;">{e(label)}</div>',
        f'<div style="font-size:0.75em; color:{e(color)};">{e(emoji)} {e(age_label)}</div>',
        f'<div style="font-size:0.65em; color:#888;">{e(date_str)}</div>',
        f'<div style="font-size:0.62em; color:#999; margin-top:2px;">{e(when)}</div>',
    ]
    if written:
        parts.append('<div style="font-size:0.6em; color:#c77; margin-top:2px;">'
                     f'{e(written)}</div>')
    parts.append("</div>")
    return "".join(parts)
