"""Hypeddit — la saisie d'abord, puis ce qu'elle dit.

Type: Feature
Uses: get_db_connection, smart_period_filter, platform_colors, i18n
Depends on: hypeddit_campaigns, hypeddit_daily_stats, v_hypeddit_daily (106)
Persists in: hypeddit_campaigns, hypeddit_daily_stats

L'ORDRE DE LA PAGE A CHANGÉ, ET C'EST LA DEMANDE DU 2026-09-21
----------------------------------------------------------------
« Remonte le panneau "saisir les données" tout en haut. » Le formulaire était en
BAS, après les statistiques et l'historique. Or cette page n'est pas une page de
lecture : **rien ici n'est collecté automatiquement.** Les visites et les clics
d'un smart link se recopient à la main depuis le tableau de bord Hypeddit. Le
geste de la page EST la saisie ; les figures sont ce qu'on regarde après.

C'est aussi pourquoi l'entrée de menu a quitté « Analytics plateformes » pour
rejoindre la configuration, juste après « Saisie S4A » — même geste, même moment.

CE QUE LA FORME DES DONNÉES IMPOSE
------------------------------------
Mesuré le 2026-09-21 sur le locataire 1 : **six campagnes, et cinq d'entre elles
ne portent qu'UN SEUL relevé.** Une seule (« Kimono à semelle de fer remix ») en
a dix-huit, étalés sur trois ans.

Cela condamne deux choses que la page faisait :

  · les MOYENNES JOURNALIÈRES (« Visites Moy. », « Clicks Moy. ») — une moyenne
    sur des relevés qui sont des totaux de campagne, pris à des dates sans
    rapport, ne décrit rien ;
  · l'agrégation PAR DATE — cinq campagnes sur six sont seules sur leur journée,
    donc chaque barre est en réalité UNE campagne, sans que rien ne le dise.

La page nomme donc la campagne sur chaque valeur, et le tableau « Voir le détail
des données » disparaît : il n'existait que pour retrouver le nom que la figure
taisait.

CE QU'ELLE GAGNE, ET QUI N'EXISTAIT NULLE PART
------------------------------------------------
Le **taux de conversion** — clics ÷ visites. C'est le seul chiffre qui juge un
smart link : sa raison d'être est de transformer une visite en clic vers une
plateforme. Mesuré ici, il va de **16 %** à **48 %** selon la campagne. Trois
fois d'écart, et aucune surface ne le montrait.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from src.dashboard.utils import get_db_connection
from src.dashboard.utils.cache_invalidation import purge_after_write
from src.dashboard.utils.i18n import t
from src.dashboard.utils.period_filter import (
    latest_release_date,
    smart_period_filter,
)
from src.dashboard.auth import get_artist_id, is_admin
from src.dashboard.utils.platform_colors import PALETTE_LIGHT

# Hypeddit a sa couleur MESURÉE depuis le 2026-09-21 : un cyan, famille de teinte
# libre, pire paire 18,1 contre le magenta d'Apple. Les trois séries de cette page
# sont de la MÊME source : elles se distinguent par l'opacité, pas par la teinte.
_HYP = PALETTE_LIGHT["hypeddit"]

# --- FONCTION DE CALLBACK POUR LE RESET ---
def clear_form_data():
    """Réinitialise les valeurs du formulaire dans le session state."""
    st.session_state["h_visits"] = 0
    st.session_state["h_clicks"] = 0
    if "h_new_camp_name" in st.session_state:
        st.session_state["h_new_camp_name"] = ""


def add_campaign_stats(db, campaign_name: str, date, visits: int, clicks: int):
    """Ajoute ou met à jour les statistiques d'une campagne.

    Le budget n'est plus saisi côté Hypeddit : la dépense publicitaire réelle est
    celle de Meta Ads (ROI Breakeven). La colonne DB `budget` reste à sa valeur par
    défaut (0). Seules les visites/clics (vraies métriques smart-link) sont saisies.
    """
    artist_id = _resolve_artist_id_or_none()
    if artist_id is None:
        return False, t("hypeddit.invalid_session", "❌ Session invalide.")

    try:
        # 1. Assurer que la campagne existe
        campaign_data = [{
            'artist_id': artist_id,
            'campaign_name': campaign_name,
            'is_active': True
        }]

        db.upsert_many(
            table='hypeddit_campaigns',
            data=campaign_data,
            conflict_columns=['artist_id', 'campaign_name'],
            update_columns=['is_active', 'updated_at']
        )

        # 2. Stats
        stats_data = [{
            'artist_id': artist_id,
            'campaign_name': campaign_name,
            'date': date,
            'visits': visits,
            'clicks': clicks
        }]

        db.upsert_many(
            table='hypeddit_daily_stats',
            data=stats_data,
            conflict_columns=['artist_id', 'campaign_name', 'date'],
            update_columns=['visits', 'clicks', 'updated_at']
        )

        # ⚠️ LA PURGE, ajoutée le 2026-09-22 avec l'entrée de Hypeddit au registre
        # des sources. Tant que cette table n'était lue par aucun cache, ne pas
        # purger ne coûtait rien. Depuis qu'elle sert la fraîcheur de l'accueil —
        # derrière un TTL de 600 s — un artiste qui saisit sa campagne verrait
        # « ✅ enregistré » et une tuile inchangée pendant dix minutes, sans rien à
        # l'écran pour l'expliquer.
        #
        # « On ne fait pas confiance à l'horloge, on écoute l'évènement. »
        purge_after_write()
        return True, t("hypeddit.save_success", "✅ Données enregistrées avec succès")

    except Exception as e:
        return False, t("hypeddit.save_error", "❌ Erreur: {err}").format(err=e)


def _resolve_artist_id_or_none() -> int | None:
    """LA décision du locataire, en un seul endroit — sans décider quoi en faire.

    Règle #7 : `get_artist_id() or 1` est interdit. Rend l'identifiant, ou `None`
    quand la session ne permet pas de le résoudre.

    Cette forme existe parce que les appelants ne peuvent pas tous réagir de la même
    façon : une fonction de RENDU arrête la page (`st.stop()`), une fonction
    d'ÉCRITURE doit rendre un couple `(False, message)` à son appelant. Le garde
    lui-même — « personne d'autre qu'un administrateur ne retombe sur le locataire
    1 » — est identique dans les deux cas, et c'est LUI qu'on ne veut pas voir
    réécrit à la main : il l'était encore sur deux sites, chacun avec sa propre
    version du message.
    """
    artist_id = get_artist_id()
    if artist_id is not None:
        return artist_id
    if not is_admin():
        return None
    return 1  # admin fallback — documented, admins only


def _resolve_artist_id() -> int:
    """Le même garde, pour un appelant qui rend une page : arrête au lieu de mentir."""
    artist_id = _resolve_artist_id_or_none()
    if artist_id is None:
        st.error(t("hypeddit.session_invalid", "Session invalide."))
        st.stop()
    return artist_id


def get_campaigns_list(db):
    artist_id = _resolve_artist_id()
    query = "SELECT campaign_name FROM hypeddit_campaigns WHERE is_active = true AND artist_id = %s ORDER BY created_at DESC"
    df = db.fetch_df(query, (artist_id,))
    return df['campaign_name'].tolist() if not df.empty else []


def get_global_stats(start_date, end_date, db):
    """Récupère les statistiques de TOUTES les campagnes sur la période.

    `db` may be passed in to reuse the caller's connection (rule #9 — one
    connection per view); when None, opens and closes its own.
    """
    artist_id = _resolve_artist_id()
    # `v_hypeddit_daily` (migration 106) porte le grain (locataire, campagne, jour).
    # La table brute peut porter deux lignes pour le même jour — un ré-import — et
    # la vue les additionne une fois pour toutes. Le PDF la lisait déjà ; cette page,
    # non : deux surfaces répondaient au même « combien de visites » par deux chemins.
    query = """
        SELECT campaign_name, day AS date, visits, clicks
        FROM v_hypeddit_daily
        WHERE day >= %s AND day <= %s AND artist_id = %s
        ORDER BY day
    """
    return db.fetch_df(query, (start_date, end_date, artist_id))


def _render_global_stats(db):
    """Section Statistiques Globales (graphique multi-axes + KPIs)."""
    st.header(t("hypeddit.global_stats", "📊 Statistiques globales"))

    # Smart period filter (presets + auto-default on data span) instead of two
    # manual date inputs. The connection is show()'s — this used to open a second
    # one here and close it below, while show()'s stayed open.
    artist_id = _resolve_artist_id()
    # DÉFAUT « DEPUIS LA DERNIÈRE SORTIE » — 2026-09-21, appliqué à toute l'app.
    # Une campagne Hypeddit sert une SORTIE ; l'année civile n'est pas son cadre.
    window = smart_period_filter(
        db,
        table="hypeddit_daily_stats",
        date_column="date",
        artist_id=artist_id,
        key="hyp_stats",
        latest_release_resolver=lambda: latest_release_date(db, artist_id),
        default_override="last_release",
    )

    df = get_global_stats(window.start, window.end, db=db)

    if df.empty:
        st.info(t("hypeddit.no_data_period", "📭 Aucune donnée trouvée pour la période sélectionnée."))
        return

    # Nettoyage et conversion. PAS de `fillna(0)` : une valeur absente sur une ligne
    # présente est une mesure qu'on n'a pas, et la compter pour zéro tire la moyenne
    # vers le bas tout en dessinant une journée creuse qui n'a pas eu lieu. `NaN`
    # traverse : la moyenne l'ignore, la figure y coupe sa ligne.
    df['visits'] = pd.to_numeric(df['visits'], errors='coerce')
    df['clicks'] = pd.to_numeric(df['clicks'], errors='coerce')
    df['date'] = pd.to_datetime(df['date'])

    _render_campaign_series(df, window)


def _render_campaign_series(df, window) -> None:
    """Visites, clics et taux de conversion — par CAMPAGNE, sur l'axe du temps.

    REMPLACE LES DEUX TUILES DE MOYENNE, et la raison est dans la donnée.
    « Visites Moy. » et « Clicks Moy. » divisaient la somme par le nombre de
    LIGNES. Or cinq campagnes sur six ne portent qu'un seul relevé, qui est le
    TOTAL de la campagne : la moyenne mélangeait donc des totaux de campagnes
    différentes, prises à des dates sans rapport, et rendait un nombre qui ne
    décrit ni une journée ni une campagne.

    ⚠️ ET CHAQUE VALEUR PORTE LE NOM DE SA CAMPAGNE. Demandé le 2026-09-21 :
    « intégrer le nom des tracks pour chaque valeur, au lieu du tableau ". Le
    tableau « Voir le détail des données » n'existait que pour retrouver le nom
    que la figure taisait — il disparaît avec la cause.

    ⚠️ PAS D'AGRÉGATION PAR DATE. La version d'avant sommait toutes les campagnes
    d'un même jour. Sur ces données, cinq campagnes sur six sont SEULES sur leur
    journée : chaque barre était donc déjà une campagne, sans le dire. Les
    empiler par campagne ne change aucun total et rend le fait lisible.
    """
    # ⚠️ `min_count=1` — UNE SOMME DE RIEN VAUT `NaN`, PAS 0.
    #
    # `groupby().sum()` rend **0** quand toutes les valeurs d'un groupe sont
    # `NaN` : une campagne dont aucune visite n'a jamais été relevée sortait donc
    # avec une barre à zéro, indiscernable d'une campagne mesurée à zéro. C'est
    # exactement la classe que `test_a_figure_never_draws_a_zero_it_did_not_measure`
    # garde, et elle m'a repris ici : la lecture ne met plus de zéro
    # (`errors='coerce'` laisse passer `NaN`), et l'AGRÉGATION le remettait.
    #
    # Avec `min_count=1`, une campagne jamais mesurée rend `NaN` et Plotly ne
    # dessine pas de barre du tout — l'absence reste une absence.
    par_camp = (df.groupby('campaign_name')
                  .agg(visits=('visits', lambda x: x.sum(min_count=1)),
                       clicks=('clicks', lambda x: x.sum(min_count=1)),
                       jour=('date', 'max'), releves=('date', 'count'))
                  .reset_index().sort_values('jour'))

    from plotly.subplots import make_subplots
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.18,
        row_heights=[0.58, 0.42],
        subplot_titles=[
            t("hypeddit.panel_volume", "Visites et clics, par campagne"),
            t("hypeddit.panel_conv", "Taux de conversion — clics ÷ visites")])

    # Le VOLUME, en barres nommées. L'axe des x porte les campagnes : cinq d'entre
    # elles n'ont qu'un relevé, une date ne les distingue donc pas.
    fig.add_trace(go.Bar(
        x=par_camp['campaign_name'], y=par_camp['visits'],
        name=t("hypeddit.visits", "Visites"), marker_color=_HYP, opacity=0.45,
        hovertemplate="%{x}<br>%{y:,.0f} visite(s)<extra></extra>"), row=1, col=1)
    fig.add_trace(go.Bar(
        x=par_camp['campaign_name'], y=par_camp['clicks'],
        name=t("hypeddit.clicks", "Clics"), marker_color=_HYP,
        hovertemplate="%{x}<br>%{y:,.0f} clic(s)<extra></extra>"), row=1, col=1)

    # LE TAUX DE CONVERSION — la raison d'être d'un smart link, et il n'était
    # calculé nulle part. `where(visits != 0)` : un dénominateur nul rend NaN, pas
    # l'infini ni zéro — « aucune visite » n'est pas « aucune conversion ».
    _v = pd.to_numeric(par_camp['visits'], errors='coerce')
    taux = (pd.to_numeric(par_camp['clicks'], errors='coerce')
            / _v.where(_v != 0) * 100)
    fig.add_trace(go.Bar(
        x=par_camp['campaign_name'], y=taux,
        name=t("hypeddit.conversion", "Conversion"), marker_color=_HYP, opacity=0.8,
        text=[("—" if pd.isna(x) else f"{x:.0f} %") for x in taux],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>%{y:.1f} %<extra></extra>"), row=2, col=1)

    fig.update_layout(
        height=680, barmode='group', margin=dict(t=90, b=140),
        legend=dict(orientation="h", y=1.10),
        title_text=t("hypeddit.chart_title", "Mes campagnes Hypeddit ({label})")
        .format(label=window.label))
    fig.update_xaxes(tickangle=-30, row=1, col=1)
    fig.update_xaxes(tickangle=-30, row=2, col=1)
    fig.update_yaxes(title_text=t("hypeddit.volume_axis", "Volume"), row=1, col=1)
    fig.update_yaxes(title_text=t("hypeddit.conv_axis", "%"), range=[0, 100], row=2, col=1)
    st.plotly_chart(fig, width="stretch")

    # CE QUE LE TAUX DIT, et le nombre de relevés derrière chaque barre.
    _mesure = par_camp[taux.notna()]
    if not _mesure.empty:
        _t = taux.dropna()
        meilleure = par_camp.loc[_t.idxmax(), 'campaign_name']
        zeros = int((par_camp['visits'].fillna(0) == 0).sum())
        st.caption(t(
            "hypeddit.conv_caption",
            "**{n} campagne(s)** sur la période. Le **taux de conversion** est ce "
            "qui juge un smart link : sa raison d'être est de transformer une "
            "visite en clic vers une plateforme. Il va ici de **{mini:.0f} %** à "
            "**{maxi:.0f} %** — **{best}** convertit le mieux. Une visite qui ne "
            "clique pas est un budget dépensé pour rien.\n\n"
            "⚠️ {solo} campagne(s) ne portent qu'**un seul relevé** : leur barre "
            "est un TOTAL de campagne, pas une journée. {zero}"
        ).format(n=len(par_camp), mini=_t.min(), maxi=_t.max(), best=meilleure,
                 solo=int((par_camp['releves'] == 1).sum()),
                 zero=(t("hypeddit.zero_campaigns",
                         "{k} campagne(s) n'ont que des relevés à zéro sur cette "
                         "période : leur conversion est incalculable, pas nulle.")
                       .format(k=zeros) if zeros else "")))


def _render_history(db):
    """Section Historique (50 dernières lignes)."""
    st.header(t("hypeddit.history_header", "📋 Historique"))
    artist_id = _resolve_artist_id()
    df_hist = db.fetch_df("""
        SELECT campaign_name, day AS date, visits, clicks
        FROM v_hypeddit_daily
        WHERE artist_id = %s
        ORDER BY day DESC LIMIT 50
    """, (artist_id,))
    # No `db.close()` here: this helper did not open the connection, `show()` did and
    # closes it in its own `finally`. Closing it mid-page left `_render_entry_form`
    # querying a closed handle, which `PostgresHandler._ensure_connection()` silently
    # repaired by reconnecting — so the page worked, opened TWO connections per
    # render against rule #9, and nothing said so. A leftover from before 2026-08-21,
    # when each helper owned its own connection.

    if not df_hist.empty:
        df_hist['date'] = pd.to_datetime(df_hist['date']).dt.strftime('%d/%m/%Y')
        st.dataframe(df_hist, width="stretch")
    else:
        st.info(t("hypeddit.empty_history", "Historique vide."))


def _render_entry_form(db):
    """Section Saisie manuelle — EN TÊTE de page depuis le 2026-09-21."""
    st.header(t("hypeddit.entry_header", "📝 Saisir les données"))

    with st.form("hypeddit_entry_form"):
        col1, col2 = st.columns(2)

        with col1:
            existing_campaigns = get_campaigns_list(db)
            _existing_lbl = t("hypeddit.type_existing", "Existante")
            _new_lbl = t("hypeddit.type_new", "Nouvelle")
            campaign_type = st.radio(t("hypeddit.type_label", "Type"), [_existing_lbl, _new_lbl], horizontal=True)

            if campaign_type == _existing_lbl and existing_campaigns:
                campaign_name = st.selectbox(t("hypeddit.campaign", "🎯 Campagne"), options=existing_campaigns)
            else:
                campaign_name = st.text_input(t("hypeddit.campaign_name", "🎯 Nom de la campagne"), key="h_new_camp_name")

            entry_date = st.date_input(t("hypeddit.date", "📅 Date"), value=datetime.now().date() - timedelta(days=1))

        with col2:
            visits = st.number_input(t("hypeddit.visits_input", "👁️ Visites"), min_value=0, step=1, key="h_visits")
            clicks = st.number_input(t("hypeddit.clicks_input", "🖱️ Clicks"), min_value=0, step=1, key="h_clicks")

        st.markdown("---")

        c1, c2, c3 = st.columns([2, 1, 1])
        with c2:
            submit = st.form_submit_button(t("hypeddit.save_btn", "💾 Enregistrer"), type="primary")
        with c3:
            # Reset button — side effect via on_click callback; return value unused
            st.form_submit_button(t("hypeddit.reset_btn", "🔄 Réinitialiser"), on_click=clear_form_data)

    if submit:
        if not campaign_name:
            st.error(t("hypeddit.campaign_name_required", "Nom de campagne requis"))
        elif not visits and not clicks:
            # ⚠️ UN JOUR À ZÉRO N'EST PAS UNE MESURE — trouvé le 2026-09-21 en
            # lisant la base, pas en relisant le code.
            #
            # Les deux champs valent 0 par défaut (`min_value=0`), et le bouton
            # « Enregistrer » écrivait la ligne telle quelle. Mesuré sur le
            # locataire 1 : la campagne « Kimono à semelle de fer remix » porte
            # **17 jours consécutifs à 0 visite et 0 clic** (22/08 → 20/09/2026),
            # contre un seul vrai relevé. Son taux de conversion en devient
            # incalculable, et sa moyenne journalière était tirée à zéro.
            #
            # Un zéro SAISI et un zéro NON MESURÉ sont indiscernables une fois en
            # base. On refuse donc d'écrire le premier plutôt que d'essayer de les
            # distinguer plus tard — c'est la seule fois où l'on peut encore le
            # faire.
            st.warning(t(
                "hypeddit.both_zero",
                "Rien à enregistrer : visites et clics sont tous les deux à **0**. "
                "Un jour à zéro s'écrit en base comme une mesure et tire les "
                "moyennes vers le bas — alors qu'il veut dire « je n'ai pas "
                "relevé ». Saisis au moins une valeur, ou laisse la journée vide."))
        else:
            success, msg = add_campaign_stats(db, campaign_name, entry_date, visits, clicks)
            if success:
                st.success(msg)
            else:
                st.error(msg)


def show():
    # ⚠️ NI TITRE NI SOUS-TITRE — retirés le 2026-09-21, même geste que sur Apple,
    # YouTube, SoundCloud et Instagram : « 📱 Hypeddit - Gestion & Analyse »
    # répétait l'entrée de menu qu'on vient de cliquer.

    # One connection for the whole page, closed once (rule #9). The five helpers
    # below opened and closed their own until 2026-08-21 — including the write
    # path, which ran on every form submit.
    db = get_db_connection()
    if db is None:
        st.error(t("hypeddit.db_unreachable", "❌ Base de données injoignable."))
        return

    try:
        # LA SAISIE D'ABORD — 2026-09-21. Rien n'est collecté automatiquement sur
        # cette page : le geste EST le formulaire, les figures sont ce qu'on
        # regarde après l'avoir rempli. L'ordre d'avant (stats, historique,
        # saisie) demandait de faire défiler toute la page pour atteindre la
        # seule chose qu'on y vient faire.
        _render_entry_form(db)
        st.markdown("---")
        _render_global_stats(db)
        st.markdown("---")
        _render_history(db)
    finally:
        db.close()

if __name__ == "__main__":
    show()
