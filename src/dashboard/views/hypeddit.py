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
from datetime import date
from src.dashboard.utils import get_db_connection, charts
from src.dashboard.utils.formats import num
from src.dashboard.utils.cache_invalidation import purge_after_write
from src.dashboard.utils.i18n import t
from src.dashboard.utils.release_picker import default_releases, release_picker
from src.dashboard.utils.s4a_entry_insight import load_release_dates
from src.dashboard.auth import get_artist_id, is_admin
from src.dashboard.utils.platform_colors import PALETTE_LIGHT
from src.dashboard.utils.date_format import format_serie

# Hypeddit a sa couleur MESURÉE depuis le 2026-09-21 : un cyan, famille de teinte
# libre, pire paire 18,1 contre le magenta d'Apple. Les trois séries de cette page
# sont de la MÊME source : elles se distinguent par l'opacité, pas par la teinte.
_HYP = PALETTE_LIGHT["hypeddit"]

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


def get_campaign_stats(db, artist_id: int):
    """Every reading of every campaign of the tenant — the campaign filter bounds it (R377)."""
    return db.fetch_df(
        "SELECT campaign_name, day AS date, visits, clicks FROM v_hypeddit_daily "
        "WHERE artist_id = %s ORDER BY day", (artist_id,))


def default_campaigns(last_day: pd.Series, n: int = 2) -> list:
    """The `n` campaigns read most recently — the two latest releases by default. Pure.

    `last_day` maps a campaign name to its last day with a reading. A campaign serves
    one release, so its last reading dates the release it served.
    """
    return default_releases(list(last_day.sort_values(ascending=False).index), n)


def render_campaign_stats(db, artist_id: int) -> None:
    """Statistiques par CAMPAGNE : visites, clics et pub Meta, comparées (R377).

    R476 (owner W5, 2026-10-09 : « on n'arrive pas à voir qui a le mieux performé ni les
    data Meta → vue croisée ») : rendered by the cross view's « Sorties » section only,
    with the tenant passed in (rule 7) — the Hypeddit page keeps entry + history.

    ⚠️ UN FILTRE CAMPAGNE, PLUS UN FILTRE DE PÉRIODE — 2026-10-05, revue d'écran du
    propriétaire (V22-V25). Une campagne Hypeddit sert UNE sortie : c'est elle l'unité
    qu'on compare, pas une fenêtre de dates. La période par défaut (« depuis la dernière
    sortie ») cachait justement la campagne de l'avant-dernière, celle à laquelle on veut
    comparer la dernière. Défaut : les deux campagnes relevées le plus récemment.
    """
    st.subheader(t("hypeddit.global_stats_cross", "🔗 Mes campagnes Hypeddit comparées"))
    df = get_campaign_stats(db, artist_id)
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

    last = df.groupby('campaign_name')['date'].max()
    chosen = release_picker(
        t("hypeddit.campaign_filter", "🎯 Campagnes comparées"),
        list(last.sort_values(ascending=False).index), key="hyp_campaigns",
        help=t("hypeddit.campaign_filter_help",
               "Par défaut, les deux campagnes les plus récentes — tes deux dernières "
               "sorties."))
    if not chosen:
        st.info(t("hypeddit.no_campaign", "Choisis au moins une campagne à comparer."))
        return
    df = df[df['campaign_name'].isin(chosen)]

    # R301 (R282 proposal D, 2026-09-28) — the Meta spend around each campaign's release: the
    # rings already carry visits, clicks and conversion per campaign, so the proposal's ONE
    # new fact goes under each ring instead of a second chart repeating the first (R299).
    spend = db.fetch_df("SELECT day, SUM(spend) AS spend FROM v_meta_daily "
                        "WHERE artist_id = %s GROUP BY day", (artist_id,))
    _render_campaign_series(
        df, t("hypeddit.label_campaigns", "{n} campagne(s)").format(n=len(chosen)), spend)


_MAX_RINGS = 12  # two rows of six rings (R245); the caption names what is left out
_RINGS_PER_ROW = 6


def _short(name, lines: int = 2, width: int = 16) -> str:
    """A campaign name cut to `lines` lines of `width` characters, with « … » if cut."""
    words, out, cur = str(name).split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    out.append(cur)
    return "<br>".join(out[:lines]) + ("…" if len(out) > lines else "")


def _render_campaign_series(df, label: str, spend=None) -> None:
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

    # LE TAUX DE CONVERSION — la raison d'être d'un smart link. `where(visits != 0)` :
    # un dénominateur nul rend NaN, pas l'infini ni zéro — « aucune visite » n'est pas
    # « aucune conversion ».
    _v = pd.to_numeric(par_camp['visits'], errors='coerce')
    taux = (pd.to_numeric(par_camp['clicks'], errors='coerce')
            / _v.where(_v != 0) * 100)

    # R211 (2026-09-27) — le propriétaire : « des ronds au lieu de barres ». UN ANNEAU
    # PAR CAMPAGNE : la part qui clique contre la part qui repart, le taux au centre. Une
    # barre de taux se lisait contre un axe à 100 ; un anneau se lit seul. Les campagnes
    # sans visite mesurée n'ont pas d'anneau (incalculable, pas nul) — la légende le dit.
    # R245 (fiche 17, 2026-09-27 : « sous forme de ronds, les graphes c'est pas très
    # pertinent ; la valeur totale de chaque en étiquette ») — les barres de volume
    # disparaissent : chaque campagne est UN anneau, son taux au centre, ses totaux dessous.
    ringed = par_camp[taux.notna()].tail(_MAX_RINGS)
    if spend is not None and not spend.empty:
        from src.dashboard.utils.meta_impact import spend_around
        ringed = ringed.assign(meta=[spend_around(spend, pd.Timestamp(d).date())
                                     for d in ringed['jour']])
    charts.plotly_chart(rings_figure(ringed, taux, label), width="stretch")
    # R443 (propriétaire, 2026-10-07) : « intégrer des graphiques sur le nombre de
    # visites, le nombre de clics et les pubs Meta dépensées pour la comparaison ». Les
    # anneaux disent le TAUX ; trois barres côte à côte disent les VOLUMES, campagne
    # contre campagne, chacune sur sa propre échelle — jamais un second axe.
    compared = par_camp.tail(_MAX_RINGS)
    if spend is not None and not spend.empty:
        from src.dashboard.utils.meta_impact import spend_around
        compared = compared.assign(meta=[spend_around(spend, pd.Timestamp(d).date())
                                         for d in compared['jour']])
    charts.plotly_chart(comparison_figure(compared), width="stretch")
    hidden = int(taux.notna().sum()) - len(ringed)
    if hidden > 0:
        st.caption(t("hypeddit.rings_capped",
                     "Anneaux : les {k} campagnes les plus récentes ; {h} plus ancienne(s) "
                     "restent dans le détail.").format(k=len(ringed), h=hidden))

    # CE QUE LE TAUX DIT, et le nombre de relevés derrière chaque barre.
    _mesure = par_camp[taux.notna()]
    if not _mesure.empty:
        _t = taux.dropna()
        meilleure = par_camp.loc[_t.idxmax(), 'campaign_name']
        zeros = int((par_camp['visits'].fillna(0) == 0).sum())
        st.caption(t(
            "hypeddit.conv_caption",
            "**{n} campagne(s)** comparée(s). Le **taux de conversion** est ce "
            "qui juge un smart link : sa raison d'être est de transformer une "
            "visite en clic vers une plateforme. Il va ici de **{mini:.0f} %** à "
            "**{maxi:.0f} %** — **{best}** convertit le mieux. Une visite qui ne "
            "clique pas est un budget dépensé pour rien.\n\n"
            "⚠️ {solo} campagne(s) ne portent qu'**un seul relevé** : leur anneau "
            "est un TOTAL de campagne, pas une journée. {zero}"
        ).format(n=len(par_camp), mini=_t.min(), maxi=_t.max(), best=meilleure,
                 solo=int((par_camp['releves'] == 1).sum()),
                 zero=(t("hypeddit.zero_campaigns",
                         "{k} campagne(s) n'ont que des relevés à zéro : leur conversion est incalculable, pas nulle.")
                       .format(k=zeros) if zeros else "")))


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


def ring_label(name: str, visits: float, clicks: float, meta: float | None = None) -> str:
    """The text under a ring: the campaign, its TOTALS (fiche 17), and the Meta spend in the
    14 days on each side of its release when known (R301). Pure."""
    fmt = lambda v: num(v, 0)   # noqa: E731
    out = (f"{_short(name)}<br>{fmt(visits)} " + t("hypeddit.ring_visits", "visites")
           + f" · {fmt(clicks)} " + t("hypeddit.ring_clicks", "clics"))
    if meta is not None and pd.notna(meta):
        out += "<br>" + t("hypeddit.ring_meta", "pub Meta ±14 j : {eur} €").format(eur=fmt(meta))
    return out


def rings_figure(ringed, taux, label: str):
    """One ring per campaign (R245): its conversion rate in the hole, its totals under it."""
    import math

    from plotly.subplots import make_subplots
    n = max(len(ringed), 1)
    cols, rows = min(n, _RINGS_PER_ROW), math.ceil(n / _RINGS_PER_ROW)
    fig = make_subplots(rows=rows, cols=cols, specs=[[{"type": "domain"}] * cols] * rows,
                        vertical_spacing=0.25)
    clicked, left = t("hypeddit.ring_clicked", "Ont cliqué"), t("hypeddit.ring_left", "Sont repartis")
    for i, (_, row) in enumerate(ringed.iterrows()):
        v, c = float(row['visits']), float(row['clicks'])
        fig.add_trace(go.Pie(
            values=[c, max(v - c, 0)], labels=[clicked, left], hole=0.62, sort=False,
            marker=dict(colors=[_HYP, "rgba(150,150,150,0.25)"]), textinfo="none",
            showlegend=(i == 0),
            title=dict(text=f"<b>{taux.loc[row.name]:.0f} %</b>", position="middle center",
                       font=dict(size=15)),
            hovertemplate="%{label} : %{value:,.0f}<extra></extra>"),
            row=i // cols + 1, col=i % cols + 1)
        dom = fig.data[i].domain
        fig.add_annotation(x=(dom.x[0] + dom.x[1]) / 2, y=dom.y[0] - 0.02, xref="paper",
                           yref="paper", showarrow=False, yanchor="top", xanchor="center",
                           align="center", text=ring_label(row['campaign_name'], v, c,
                                                           row.get('meta')),
                           font=dict(size=11))
    fig.update_layout(
        # Legend above the rings, under the title: below them it sat on the first ring's
        # label (seen on the rendered PNG at 1100 px, R476).
        height=300 * rows + 100, margin=dict(t=100, b=90),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0.5, xanchor="center"),
        title_text=t("hypeddit.chart_title", "Mes campagnes Hypeddit ({label})")
        .format(label=label))
    return fig


_META = PALETTE_LIGHT["meta"]


def comparison_figure(compared):
    """Visites, clics, pub Meta ±14 j — un panneau chacun, une barre par campagne (R443).

    Trois panneaux et pas un graphique groupé : les visites se comptent en centaines,
    les clics en dizaines et la pub en euros. Sur un axe commun, les clics seraient
    plats ; sur deux axes, la figure suggérerait une comparaison que les unités
    interdisent. Une campagne sans mesure n'a pas de barre (`NaN`), jamais un zéro.
    """
    from plotly.subplots import make_subplots

    names = [_short(n, lines=2, width=14) for n in compared['campaign_name']]
    has_meta = 'meta' in compared
    panels = [('visits', t("hypeddit.cmp_visits", "Visites"), _HYP),
              ('clicks', t("hypeddit.cmp_clicks", "Clics"), _HYP)]
    if has_meta:
        panels.append(('meta', t("hypeddit.cmp_meta", "Pub Meta ±14 j (€)"), _META))
    fig = make_subplots(rows=1, cols=len(panels),
                        subplot_titles=[title for _, title, _ in panels])
    for i, (col, title, colour) in enumerate(panels, start=1):
        vals = pd.to_numeric(compared[col], errors='coerce')
        fig.add_trace(go.Bar(
            x=names, y=vals, marker_color=colour, name=title, showlegend=False,
            text=[num(v, 0) if pd.notna(v) else "" for v in vals],
            textposition="outside", cliponaxis=False,
            hovertemplate="%{x}<br>" + title + " : %{y:,.0f}<extra></extra>"),
            row=1, col=i)
        # Headroom: the value written above the tallest bar must not touch the panel title.
        top = vals.max()
        fig.update_yaxes(range=[0, top * 1.25] if pd.notna(top) and top > 0 else None,
                         rangemode="tozero", showticklabels=False, row=1, col=i)
    fig.update_layout(
        height=320, margin=dict(t=70, b=60), bargap=0.35,
        title_text=t("hypeddit.cmp_title", "Volumes comparés, campagne par campagne"))
    return fig
