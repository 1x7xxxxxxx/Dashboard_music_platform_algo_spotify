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
from datetime import date
from src.dashboard.utils import get_db_connection
from src.dashboard.utils.cache_invalidation import purge_after_write
from src.dashboard.utils.i18n import t
from src.dashboard.utils.s4a_entry_insight import load_release_dates
from src.dashboard.auth import get_artist_id, is_admin
from src.dashboard.utils.date_format import format_serie

# Hypeddit a sa couleur MESURÉE depuis le 2026-09-21 : un cyan, famille de teinte
# libre, pire paire 18,1 contre le magenta d'Apple. Les trois séries de cette page
# sont de la MÊME source : elles se distinguent par l'opacité, pas par la teinte.

def entry_defaults(release_dates: dict, campaigns: list) -> tuple[bool, str | None]:
    """(is_new, name) the entry form opens on — the LATEST release (R482, W5). Pure.

    A campaign serves one release : the latest release is « new » until a campaign
    carries its title. Without any release date, fall back to the newest campaign.
    """
    if not release_dates:
        return (not campaigns, campaigns[0] if campaigns else None)
    song = max(release_dates, key=release_dates.get)
    match = next((c for c in campaigns if str(song).casefold() in str(c).casefold()), None)
    return (False, match) if match else (True, song)


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
        purge_after_write(artist_id=artist_id)
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



_MAX_RINGS = 12  # two rows of six rings (R245); the caption names what is left out
_RINGS_PER_ROW = 6


def _render_history(db):
    """Section Historique (50 dernières lignes) — REPLIÉE par défaut (R377, V25)."""
    with st.expander(t("hypeddit.history_header", "📋 Historique"), expanded=False):
        _render_history_table(db)


def _render_history_table(db):
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
        df_hist['date'] = format_serie(pd.to_datetime(df_hist['date']))
        st.dataframe(df_hist, width="stretch")
    else:
        st.info(t("hypeddit.empty_history", "Historique vide."))


def _render_entry_form(db):
    """Section Saisie manuelle — EN TÊTE de page depuis le 2026-09-21."""
    st.header(t("hypeddit.entry_header", "📝 Saisir les données"))
    # R377 (V23) : les gestes seulement — pas d'explication de ce qu'est un smart link.
    with st.expander(t("hypeddit.fetch_header", "📥 Récupérer tes chiffres sur Hypeddit")):
        st.markdown(t(
            "hypeddit.fetch_steps",
            "1. Ouvre **hypeddit.com** et connecte-toi.\n"
            "2. Dans ton tableau de bord, ouvre la campagne de ta sortie.\n"
            "3. Ouvre ses statistiques et règle-les sur la journée à saisir.\n"
            "4. Reporte ici la campagne, la date, les **visites** et les **clics**, "
            "puis **Enregistrer**."))

    # R482 (W5 II, owner 2026-10-09) : type, campaign and date on ONE line, visits and
    # clicks next, then ONE centred call to action — « Réinitialiser » is gone. No
    # `st.form` : inside a form the type radio could not swap the campaign field until
    # the submit, so « Nouvelle » kept showing the list of existing campaigns.
    existing = get_campaigns_list(db)
    is_new, default_name = entry_defaults(load_release_dates(db, _resolve_artist_id()),
                                          existing)
    _existing_lbl = t("hypeddit.type_existing", "Existante")
    _new_lbl = t("hypeddit.type_new", "Nouvelle")
    c_type, c_name, c_date = st.columns([1, 2, 1])
    with c_type:
        campaign_type = st.radio(t("hypeddit.type_label", "Type"), [_existing_lbl, _new_lbl],
                                 index=1 if is_new or not existing else 0,
                                 horizontal=True, key="h_type")
    with c_name:
        if campaign_type == _existing_lbl and existing:
            campaign_name = st.selectbox(
                t("hypeddit.campaign", "🎯 Campagne"), options=existing,
                index=existing.index(default_name) if default_name in existing else 0,
                key="h_campaign")
        else:
            campaign_name = st.text_input(t("hypeddit.campaign_name", "🎯 Nom de la campagne"),
                                          value=default_name if is_new and default_name else "",
                                          key="h_new_camp_name")
    with c_date:
        entry_date = st.date_input(t("hypeddit.date", "📅 Date"), value=date.today(),
                                   key="h_date")
    c_visits, c_clicks = st.columns(2)
    with c_visits:
        visits = st.number_input(t("hypeddit.visits_input", "👁️ Visites"), min_value=0, step=1, key="h_visits")
    with c_clicks:
        clicks = st.number_input(t("hypeddit.clicks_input", "🖱️ Clics"), min_value=0, step=1, key="h_clicks")
    _, c_save, _ = st.columns([1, 2, 1])
    with c_save:
        submit = st.button(t("hypeddit.save_btn", "💾 Enregistrer"), type="primary",
                           width="stretch", key="h_save")

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
        # R476 (W5) : the campaign comparison moved to the cross view, section « Sorties ».
        _render_history(db)
    finally:
        db.close()

if __name__ == "__main__":
    show()
