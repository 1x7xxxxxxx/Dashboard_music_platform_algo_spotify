"""Credentials — Streamlit render/form helpers + save handler.

Type: Sub
Uses: streamlit, pandas, requests, _core, _registry, AirflowTrigger
Pure relocation from the former credentials.py — no logic change.
"""
import pandas as pd
import logging

import streamlit as st

from src.dashboard.utils.i18n import t

from src.utils.tenant_identity import (
    PLATFORM_IDENTITIES,
    malformed_identities,
)
from ._core import (
    find_identity_conflict,
    dags_for_save,
    _STATE_ICON,
    PLATFORM_TO_DAGS,
    _decode_row,
    _encrypt_secrets,
    _mask,
    _save_credentials,
    extract_spotify_artist_id,
)
from ._registry import CONNECTION_TESTS

logger = logging.getLogger(__name__)
from src.dashboard.content.credential_guides_st import (
    guide_screenshots, render_credential_guide_for,
)
from src.utils.tenant_identity import mirrored_columns, write_platform_identity
from src.dashboard.utils.tz import to_local_datetime
from src.dashboard.auth import is_admin


# Le verdict de la dernière sauvegarde, porté d'un run à l'autre.
#
# `_handle_save` finit par `st.rerun()` — il le doit, c'est ce qui fait réapparaître
# la page avec l'identifiant enregistré et la matrice à jour. Conséquence : tout ce
# qu'il écrivait à l'écran juste avant était effacé dans la milliseconde. Le
# « ✅ Credentials spotify enregistrés » qui vivait là n'a donc jamais été lu par
# personne, et la sonde tournait déjà — son résultat partait en base et nulle part
# ailleurs. L'artiste voyait un spinner, puis une page rechargée : « j'ai enregistré,
# et je ne sais pas si ça marche ». C'est la remarque du 2026-09-04.
#
# (plateforme, ok | None, raison). `ok is None` = la sonde n'a pas pu conclure —
# distinct de `ok is False`, qui est un vrai refus de la plateforme.
VERDICT_KEY = "_cred_last_verdict"


def platform_label(platform_key: str) -> str:
    """Le nom que l'artiste voit sur l'onglet, jamais la clé technique.

    « Vérification de la connexion meta… » nommait une clé de dictionnaire dans une
    phrase adressée à quelqu'un qui n'a jamais vu ce mot ailleurs que là.
    """
    from ._registry import PLATFORMS
    return (PLATFORMS.get(platform_key) or {}).get('label', platform_key)


def _verdict_from_probes(probes: dict, platform_key: str) -> tuple:
    """(plateforme, ok, raison) depuis la mémoire des sondes. Jamais d'exception.

    Une plateforme absente de `probes` n'est PAS un échec : c'est « la sonde n'a rien
    pu dire » (pas de sonde pour cette plateforme, API injoignable, table absente).
    Le rendre comme un ❌ enverrait un artiste réparer une connexion qui n'a jamais
    été mise en défaut.
    """
    remembered = (probes or {}).get(platform_key)
    if not remembered:
        return (platform_key, None, "")
    ok, reason = remembered[0], remembered[1]
    return (platform_key, bool(ok), reason or "")


def render_save_verdict(next_platform: tuple | None,
                        selection_complete: bool = False) -> None:
    """Le verdict de la sauvegarde qui vient d'avoir lieu, en gros, une seule fois.

    Rendu DANS l'onglet, au-dessus de « Saisir tes identifiants » — et il a fait
    l'aller-retour, ce qui vaut d'être écrit.

    Le 2026-09-04 il en a été SORTI, pour une raison réelle : la page se réordonnait
    au rerun pour ouvrir la plateforme suivante, donc l'onglet qui portait « ✅
    Spotify est connecté » n'était plus celui qui s'ouvrait, et le verdict
    s'affichait dans un onglet fermé.

    Le 2026-09-05, le réordonnancement a disparu avec la sélection : l'ordre des
    onglets est désormais fixe (`setup_columns`). La cause du déplacement n'existe
    plus, et l'endroit demandé — « au-dessus de saisir tes identifiants » — est celui
    où l'on regarde après avoir collé une valeur.

    **Un seul onglet l'appelle.** `pop` consomme le verdict : appelée depuis les cinq
    onglets, la fonction le verrait disparaître dans le premier rendu par Streamlit,
    qui n'est pas celui qu'on regarde. Le routeur désigne donc `verdict_owner`, et
    `_render_platform_tab` ne l'appelle que si c'est lui.

    Lequel ? Après un enregistrement RÉUSSI, l'onglet de la plateforme SUIVANTE — la
    page la met en tête, c'est donc elle qui s'ouvre, et le verdict doit s'afficher là
    où l'artiste regarde. Après un ÉCHEC, l'onglet de la plateforme saisie : il faut
    corriger là où l'on a saisi.

    Consommé (`pop`) : c'est le compte rendu d'une action, pas un état. Laissé en
    place, il réapparaîtrait à chaque rerun de la page, y compris des jours plus
    tard, et finirait par contredire la matrice — qui, elle, est un état.
    """
    pending = st.session_state.get(VERDICT_KEY)
    if not pending:
        return
    st.session_state.pop(VERDICT_KEY, None)
    platform_key, ok, reason = pending
    label = platform_label(platform_key)

    if ok:
        st.markdown("## " + t("credentials.verdict_ok",
                              "✅ {platform} est connecté.").format(platform=label))
        if next_platform:
            _nxt_key, nxt_label = next_platform
            # Pas de « — son onglet est ci-dessus » ajouté ici : `_next_label` porte
            # déjà l'onglet quand il diffère du nom de la plateforme, et la phrase
            # complète disait « Suivante : Instagram — dans l'onglet Meta /
            # Instagram — son onglet est ci-dessus » (vu au navigateur le
            # 2026-09-04). Deux surfaces qui ajoutent chacune leur moitié de phrase
            # produisent une redite que ni l'une ni l'autre ne voit seule.
            st.markdown("### " + t(
                "credentials.verdict_next", "👉 Suivante : **{label}**"
            ).format(label=nxt_label))
        elif selection_complete:
            # « Tout est connecté » ne se dit QUE d'une sélection qu'on peut compter.
            # Un artiste arrivé ici hors parcours de mise en route n'a pas de
            # sélection : lui annoncer que tout est connecté serait une affirmation
            # sur des plateformes auxquelles il n'a jamais touché.
            st.markdown("### " + t(
                "credentials.verdict_all_done",
                "🎉 Toutes les plateformes que tu as choisies sont connectées. Les "
                "premières données arrivent sous ~2 min."))
            if st.button(t("credentials.verdict_go_home", "🏠 Aller au dashboard →"),
                         type="primary", key=f"_verdict_home_{platform_key}"):
                from src.dashboard.utils.navigation import goto
                goto('home')
        return

    if ok is False:
        st.markdown("## " + t("credentials.verdict_ko",
                              "❌ {platform} : enregistré, mais la plateforme ne "
                              "répond pas encore.").format(platform=label))
        if reason:
            st.error(reason)
        st.markdown("### " + t(
            "credentials.verdict_ko_what_now",
            "Corrige ci-dessous puis **💾 Enregistre** à nouveau — on retestera "
            "tout de suite."))
        return

    # `ok is None` : rien à affirmer. Le dire vaut mieux qu'un ✅ optimiste, qui est
    # exactement ce que la page faisait avant en écrivant « Credentials enregistrés »
    # sans avoir rien vérifié.
    st.markdown("## " + t("credentials.verdict_saved",
                          "💾 {platform} enregistré.").format(platform=label))
    st.info(t("credentials.verdict_unknown",
              "La vérification n'a rien pu conclure pour l'instant. Utilise "
              "**🔌 Tester la connexion** ci-dessous, ou reviens dans quelques "
              "minutes — la collecte de cette nuit tranchera de toute façon."))


def _declared_from_rows(existing: dict) -> set:
    """{platform: row} → the logical platforms carrying a non-empty identity."""
    import json

    from src.utils.tenant_identity import declared_identities

    extra_by_platform = {}
    for platform, row in (existing or {}).items():
        extra = (row or {}).get("extra_config") or {}
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except ValueError:
                extra = {}
        extra_by_platform[platform] = extra if isinstance(extra, dict) else {}
    return declared_identities(extra_by_platform)


# `_render_global_kpi` lived here until 2026-08-22 and was replaced by
# `src/dashboard/utils/status_matrix.render_status_matrix`. Two reasons, both
# measured, and both worth keeping written down so it does not come back:
#
#   * its second axis was `_fetch_dag_last_states()` — the last run of each DAG
#     ACROSS THE FLEET. It could read 🟢 while this particular artist had zero rows,
#     which is precisely the state two beta sessions were spent on.
#   * it iterated `PLATFORMS`, the four form TABS, while five logical platforms
#     exist. Instagram — whose identity is a field of the Meta tab — had no column,
#     so a tenant whose only identity was `ig_user_id` read "à connecter" while
#     `instagram_daily` collected for them.
#
# The per-tab DAG badge below said, until 2026-08-30, that it could stay "because the
# caption shows exactly what it claims". That was wrong, and an artist found it in one
# reading: the caption names a DAG ID and a state. Nothing in "DAG `spotify_api_daily`
# — 🟢 success" tells a reader it describes the FLEET rather than their own account,
# and a brand-new artist read it as proof their collection had already run. It is now
# rendered to admins only, at the bottom of the tab.


def _render_dag_status_badge(platform_key: str, dag_states: dict) -> None:
    """Inline status badge inside a platform tab."""
    dags = PLATFORM_TO_DAGS.get(platform_key, [])
    if not dags or not dag_states:
        return
    for dag_id in dags:
        info = dag_states.get(dag_id, {})
        state = info.get('state')
        icon = _STATE_ICON.get(state, '⚫')
        date = info.get('date', '—')
        state_label = state or t("credentials.dag_state_never", "jamais exécuté")
        st.caption(t("credentials.dag_badge",
                     "DAG `{dag_id}` — {icon} **{state}** — dernier run : {date}").format(
                         dag_id=dag_id, icon=icon, state=state_label, date=date))


def _render_platform_tab(db, platform_key, platform_info, artist_id,
                         existing_row, fernet_ok, dag_states: dict | None = None,
                         artist_name: str | None = None,
                         next_platform: tuple | None = None):
    # Un champ `admin_only` est une surcharge d'exploitant : l'artiste ne doit ni
    # le voir ni pouvoir l'écrire. Filtré ICI, donc `_handle_save` ne le lit pas non
    # plus — le filtre porte sur la définition, pas seulement sur l'affichage.
    fields_def = [f for f in platform_info['fields']
                  if not f.get('admin_only') or is_admin()]

    # L'ordre de cet onglet a été inversé le 2026-08-30, après le premier parcours
    # artiste complet. Il était : état du DAG → mode d'emploi → statut → formulaire.
    # L'action — la seule chose que l'artiste ait à FAIRE ici — arrivait donc en
    # quatrième position, sous un sélecteur d'OS et un pavé qu'il faut déplier.
    # Il est maintenant : statut → ACTION → test → mode d'emploi → (admin) DAG.

    # ── Statut actuel ──────────────────────────────────────────────────
    if existing_row:
        updated = existing_row.get('updated_at')
        updated_str = (
            to_local_datetime(updated).strftime('%d/%m/%Y %H:%M') if updated else '?'
        )
        # Expiry badge for platforms that use expiring tokens (Meta)
        expires_at = existing_row.get('expires_at')
        if expires_at is not None:
            try:
                # Both sides tz-aware in UTC. The previous form parsed a
                # `timestamptz` (hence AWARE) and subtracted
                # `pd.Timestamp.utcnow().tz_localize(None)` (NAIVE), which raises
                # `TypeError: Cannot subtract tz-naive and tz-aware datetime-like
                # objects` — verified 2026-08-30. It never fired only because no row
                # carries `expires_at` yet: the first Meta token with an expiry would
                # have broken the Credentials page, the one an artist uses to connect.
                exp = to_local_datetime(expires_at)
                days_left = (exp - pd.Timestamp.now(tz="UTC")).days
                if days_left <= 0:
                    st.error(t("credentials.token_expired",
                               "Token **expiré** depuis le {date}. Renouvellement requis.").format(
                                   date=exp.strftime('%d/%m/%Y')))
                elif days_left <= 15:
                    st.warning(t("credentials.token_expiring",
                                 "Token expire dans **{days} jour(s)** ({date}) — renouvellement recommandé.").format(
                                     days=days_left, date=exp.strftime('%d/%m/%Y')))
                else:
                    st.success(t("credentials.creds_saved_valid",
                                 "Credentials enregistrés — mise à jour : {updated} · Token valide jusqu'au {date} ({days}j)").format(
                                     updated=updated_str, date=exp.strftime('%d/%m/%Y'), days=days_left))
            except Exception:
                st.success(t("credentials.creds_saved",
                             "Credentials enregistrés — mise à jour : {updated}").format(updated=updated_str))
        else:
            # « Credentials ENREGISTRÉS » et rien d'autre : c'est tout ce que cette
            # ligne peut affirmer. Signalé le 2026-09-05 — « SoundCloud me dit que
            # j'ai : Credentials enregistrés… or c'est faux » : la valeur ÉTAIT
            # enregistrée, et l'horodatage juste (01:14 UTC = 03:14 à Paris). Ce qui
            # était faux est ce que la phrase laisse croire, à côté d'une sonde qui
            # échoue : « enregistré » se lit « ça marche ».
            #
            # `st.caption` et non `st.success` : le vert est un verdict, et le verdict
            # appartient à la sonde. Une valeur en base n'est pas une connexion.
            st.caption(t("credentials.creds_saved",
                         "Valeur enregistrée le {updated} — enregistrée ne veut pas "
                         "dire vérifiée : c'est le test ci-dessous qui le dit."
                         ).format(updated=updated_str))
        existing_values = _decode_row(existing_row, fields_def)
    else:
        # RIEN. « Aucun credential enregistré pour cette plateforme » était la
        # PREMIÈRE ligne de la page pour un artiste qui vient s'inscrire — elle lui
        # annonçait l'absence de ce qu'il vient faire, avant même de lui montrer où
        # le faire. Un formulaire vide dit déjà qu'il est vide.
        #
        # L'état, lui, vit sur « 📋 État de tes plateformes », dont c'est le sujet et
        # où il est lisible pour les six sources d'un coup au lieu d'une à la fois.
        existing_values = {}

    st.markdown("---")

    # ── DEUX COLONNES : la saisie à gauche, son mode d'emploi à droite ─────
    #
    # Le guide vivait SOUS le formulaire, replié. Deux conséquences, signalées le
    # 2026-09-04 : « il n'y a toujours pas l'onglet saisir tes identifiants dans la
    # même section que Spotify — obtenir les identifiants », et « il n'y a toujours
    # pas le screen » — la capture d'écran du menu Partager EST dans le guide depuis
    # ce matin, mais personne ne déplie un pavé pour aller la chercher pendant qu'il
    # remplit un champ. Une consigne qu'il faut ouvrir pour lire n'est pas à côté de
    # l'action : elle est ailleurs.
    #
    # Côte à côte, et le guide DÉPLIÉ : on lit à droite, on colle à gauche, sans
    # rien ouvrir. Sur un écran étroit, Streamlit empile les colonnes — la saisie
    # reste au-dessus, ce qui est le bon ordre quand on ne peut pas avoir les deux.
    # TROIS BANDES, pas deux colonnes. Demandé le 2026-09-04, après avoir essayé les
    # deux : « garder la section saisir tes identifiants tout en haut au centre, et
    # l'explication textuelle en bas à gauche, alignée avec le screen ».
    #
    #   1. le formulaire, PLEINE LARGEUR — c'est le geste, il vient en premier ;
    #   2. les étapes du guide, à gauche ;
    #   3. la capture, à droite, en face du texte qui la décrit.
    #
    # Ce que la mise en page à deux colonnes coûtait : le champ à remplir était
    # comprimé à 3/5 de la largeur pour laisser la place à une consigne qu'on lit une
    # fois. Et la capture, rendue DANS le fil des étapes, tombait sous elles au lieu
    # d'être en face.
    #
    # Les images sont sorties du guide (`with_images=False`) et posées ici : les
    # rendre aux deux endroits est exactement ce qui a produit « il y a 2 screen ».
    _shots = guide_screenshots(platform_key)

    def _render_guide_below() -> None:
        _col_text, _col_shot = st.columns(2, gap="large")
        with _col_text:
            render_credential_guide_for(platform_key, artist_name=artist_name,
                                        expanded=True, with_images=not _shots)
        with _col_shot:
            for _path, _caption in _shots:
                st.image(str(_path), caption=_caption, use_container_width=True)

    # Le verdict de la sauvegarde qui vient d'avoir lieu, AU-DESSUS de tout le reste
    # de cet onglet — donc au-dessus de « Saisir tes identifiants ».
    # `verdict_owner` et non `platform_key` : après un enregistrement réussi, la page
    # met la plateforme SUIVANTE en tête, donc c'est SON onglet qui s'ouvre. Le
    # verdict — « ✅ Spotify est connecté / 👉 Suivante : SoundCloud » — doit s'afficher
    # là où l'artiste regarde, pas dans l'onglet qu'il vient de quitter.
    #
    # Hors de ce cas, l'appelant passe `platform_key` : chaque onglet ne rend que le
    # sien, et `pop` ne mange pas le verdict d'un autre.
    # SANS filtre : depuis la refonte du 2026-09-05, un seul panneau est rendu — celui
    # de l'onglet actif. `verdict_owner` existait parce que `st.tabs` rendait les cinq
    # et que `pop` faisait disparaître le message dans le premier venu ; le filtre est
    # devenu la rustine d'un problème qui n'existe plus.
    #
    # Il a d'ailleurs survécu une heure de trop : le routeur avait cessé de le passer,
    # sa valeur par défaut `None` ne valait jamais `platform_key`, et le verdict ne
    # s'affichait plus du tout. Vu au navigateur, pas en relisant.
    render_save_verdict(next_platform)

    def _render_form() -> None:
        """Le formulaire, extrait pour pouvoir vivre DANS une colonne.

        Deux dispositions, décidées par la présence d'une capture — demandé le
        2026-09-05 : « pour SoundCloud, vu qu'on n'a pas de photo à coller, garde
        saisir tes id à gauche et les éléments textuels à droite et alignés ».

          * AVEC capture (Spotify, YouTube, Meta) : formulaire pleine largeur en
            haut, puis texte à gauche et image à droite. L'image a besoin de place ;
            la comprimer au tiers la rend illisible.
          * SANS capture (SoundCloud) : formulaire à gauche, guide à droite, côte à
            côte. Il n'y a rien à mettre sous le formulaire, donc l'étaler sur toute
            la largeur pour poser trois lignes de texte dessous crée un vide au
            milieu de l'écran.

        C'est la MÊME règle dans les deux cas — le texte est en face de ce qu'il
        décrit — et elle donne deux mises en page parce que les contenus diffèrent.
        """
        # ── Meta : l'assistant qui trouve le numéro de compte ─────────
        # AU-DESSUS du formulaire, parce que c'est l'étape qui précède la saisie : il
        # produit la valeur que le champ attend. Hors du `st.form` — un formulaire ne
        # rend rien tant qu'on ne l'a pas soumis, donc le numéro trouvé n'apparaîtrait
        # qu'après un enregistrement, c'est-à-dire trop tard pour aider à le remplir.
        if platform_key == 'meta':
            from ._platform_meta import render_ad_account_picker
            render_ad_account_picker(artist_id)
            st.markdown("---")

        # ── Formulaire standard (toutes plateformes) ─────────────────────
        with st.form(f"cred_{platform_key}_{artist_id}"):
            # « Mettre à jour » sur un formulaire vierge : signalé par un artiste en test
            # le 2026-08-30 — « on ne met pas à jour la première fois ». Le titre doit
            # nommer l'action qu'il a devant lui, pas celle qu'il fera plus tard.
            # `:orange-background[…]` est du markdown Streamlit documenté (≥ 1.32), donc
            # une couleur qui survit à une montée de version. Un `<style>` visant les
            # classes internes de Streamlit — l'autre façon de colorer un bloc — se
            # casserait en silence, et un fond qui disparaît ne lève aucune exception.
            # La consigne de la séance : l'ACTION en gros, en gras, en surbrillance ;
            # l'information en caption.
            if existing_row:
                st.markdown("### :orange-background[✏️ "
                            + t("credentials.form.update", "Mettre à jour") + "]")
                st.caption(t(
                    "credentials.form.caption",
                    "🔒 Champs secrets chiffrés • Laissez vide pour conserver la valeur actuelle"
                ))
            else:
                st.markdown("### :orange-background[👉 "
                            + t("credentials.form.enter", "Saisir tes identifiants") + "]")
                # Rien sous le titre. « 🔒 Chiffrés à l'enregistrement. C'est la seule
                # action à faire sur cette page. » disait deux choses justes et
                # inutiles ici : le chiffrement, que personne ne vérifie au moment de
                # coller, et l'unicité de l'action, qu'un formulaire à un champ montre
                # déjà. La ligne équivalente du cas « déjà rempli » reste, elle : elle
                # explique un COMPORTEMENT — laisser vide conserve la valeur.

            form_values = {}
            pairs = [fields_def[i:i + 2] for i in range(0, len(fields_def), 2)]

            for pair in pairs:
                cols = st.columns(len(pair))
                for col, field in zip(cols, pair):
                    key = field['key']
                    existing_val = existing_values.get(key, '')
                    field_label = t(f"credentials.field.{key}", field['label'])

                    if field['secret']:
                        val = col.text_input(
                            field_label,
                            type='password',
                            placeholder=_mask(existing_val) if existing_val
                            else t("credentials.form.undefined", "Non défini"),
                            help=t("credentials.form.secret_help",
                                   "🔒 Chiffré en base — laisser vide pour conserver"),
                            key=f"{platform_key}_{artist_id}_{key}",
                        )
                    elif field.get('multiline'):
                        val = col.text_area(
                            field_label,
                            value=existing_val or field.get('default', ''),
                            key=f"{platform_key}_{artist_id}_{key}",
                            height=90,
                        )
                    else:
                        val = col.text_input(
                            field_label,
                            value=existing_val or field.get('default', ''),
                            key=f"{platform_key}_{artist_id}_{key}",
                            placeholder=field.get('example', ''),
                        )
                    form_values[key] = val

                    # L'exemple SOUS le champ, et plus dans un bloc « Les valeurs à
                    # coller » au bas du guide. Demandé le 2026-09-04 : « intègre
                    # sous le champ ». Le `placeholder` ci-dessus le montre déjà
                    # DANS le champ tant qu'il est vide — c'est la forme la plus
                    # directe — et cette ligne le garde lisible une fois qu'on a
                    # commencé à taper.
                    if field.get('example') and not field['secret']:
                        col.caption(t("credentials.form.example_inline",
                                      "ex. {ex}").format(ex=field['example']))

            # La capture, DANS le formulaire, juste sous le champ qu'elle explique.
            #
            # Elle était sous le bouton « Enregistrer », donc après l'action : « il
            # n'y a toujours pas la capture à côté ou juste en dessous de saisir tes
            # identifiants ». Une image qui montre OÙ trouver la valeur doit être lue
            # AVANT de la saisir, pas après avoir validé.
            # Pas de capture ICI. Elle y a vécu du 2026-09-04 au soir du même
            # jour, et pour une raison qui s'est révélée fausse : le guide de droite
            # portait déjà la sienne, mais elle ne s'affichait pas EN PRODUCTION —
            # `assets/` n'était pas dans l'image Docker. J'ai donc ajouté une
            # deuxième copie pour compenser un fichier manquant.
            #
            # Le fichier livré, il en restait deux, à 100 px l'une de l'autre :
            # « il y a 2 screen, c'est très moche ». Celle qui part est celle-ci, et
            # pas l'autre : l'image montre le menu `•••` SUR LE SITE DE SPOTIFY,
            # donc elle illustre l'étape 1 du guide, pas le champ. À côté du champ
            # elle ne répond à rien — quand on y arrive, le lien est déjà copié.
            #
            # Le lien entre les deux colonnes est la flèche de l'étape 3 : « Colle le
            # lien ⬅ dans **URL profil artiste** ».

            submitted = st.form_submit_button(
                t("credentials.form.save", "💾 Enregistrer"),
                type="primary",
                disabled=not fernet_ok,
            )

            if submitted and fernet_ok:
                _handle_save(
                    db=db,
                    platform_key=platform_key,
                    fields_def=fields_def,
                    artist_id=artist_id,
                    form_values=form_values,
                    existing_values=existing_values,
                )

        # Les « titres hébergés sur d'autres comptes » vivaient ici et sont partis
        # sur ☁️ SoundCloud — Performance le 2026-09-04. Ils n'ont jamais été un
        # identifiant : c'est une déclaration de catalogue, qu'on fait en regardant
        # ses chiffres et en constatant qu'un titre manque, pas en collant un lien de
        # profil. Voir `views/soundcloud_claims.py`.

        # Le guide, SOUS le formulaire et sur toute la largeur : texte à gauche,
        # capture à droite, en face du texte qui la décrit.
        st.markdown("---")

    if _shots:
        _render_form()
        _render_guide_below()
    else:
        _col_form, _col_guide = st.columns([3, 2], gap="large")
        with _col_form:
            _render_form()
        with _col_guide:
            render_credential_guide_for(platform_key, artist_name=artist_name,
                                        expanded=True)

    # ── Test de connexion (hors form) ─────────────────────────────────
    if existing_row and platform_key in CONNECTION_TESTS:
        st.markdown("---")
        if st.button(
            t("credentials.test_button", "🔌 Tester la connexion"),
            key=f"test_{platform_key}_{artist_id}",
        ):
            with st.spinner(t("credentials.testing", "Test en cours…")):
                test_fields = _decode_row(existing_row, fields_def)
                # Who is asking — the SoundCloud probe reads this tenant's declared
                # tracks, so that an artist released under a label is not told to fix
                # the one thing that is already correct.
                test_fields["_artist_id"] = artist_id
                ok, msg = CONNECTION_TESTS[platform_key](test_fields)
                if ok:
                    st.success(msg)
                else:
                    st.error(t("credentials.test_failed",
                               "Connexion échouée : {msg}").format(msg=msg))

    # ── Statut DAG — ADMIN SEULEMENT ──────────────────────────────────
    # Un artiste qui vient de créer son compte lisait ici « DAG spotify_api_daily —
    # 🟢 success — dernier run : … » et l'a compris comme SA collecte. C'est l'état
    # de la FLOTTE : le run de l'admin. Exactement la classe décrite en tête de ce
    # fichier — la même que `_render_global_kpi`, retirée le 2026-08-22 pour cette
    # raison — et le commentaire d'alors affirmait que ce badge-ci pouvait rester
    # « parce que la légende dit bien ce qu'elle montre ». Elle ne le dit pas : elle
    # nomme un identifiant de DAG, que rien ne permet de lire comme « toute la
    # flotte ». Balayage du 2026-08-30 : les deux autres lecteurs d'état de flotte
    # (`views/airflow_kpi.py`, page admin-only, et `views/home.py`, gardé le même
    # jour) étaient déjà couverts ; celui-ci était le dernier vivant.
    if dag_states is not None and is_admin():
        _render_dag_status_badge(platform_key, dag_states)

    # The Meta token refresh UI lived here until 2026-08-22. It is gone, not fixed.
    #
    # It read `app_id` / `app_secret` / `access_token` out of the tenant's saved
    # fields — and the meta tab declares only `account_id` and `ig_user_id`. So the
    # three were always empty strings, the button always answered "App ID ou App
    # Secret manquant — renseigner d'abord ces champs", and it named fields the form
    # does not have. Every artist who pressed it was sent looking for something that
    # does not exist.
    #
    # The right home for that statement is central, not per-artist: under ADR-006 the
    # Meta token is an APP credential read from META_ACCESS_TOKEN, it is a System User
    # token that does not expire, and `src/utils/central_apps.py::check_meta` already
    # calls /debug_token with the app credentials. Putting a CENTRAL failure on a
    # PER-ARTIST page is what made two beta testers read "my credentials are broken".

_RESOLVE_MESSAGES = {
    "empty": "Collez d'abord le lien de votre profil SoundCloud.",
    "app_not_configured": ("L'app SoundCloud de la plateforme n'est pas configurée — "
                           "ce n'est pas vous, c'est nous. Signalez-le à l'administrateur."),
    "token_refused": ("SoundCloud n'a pas délivré de jeton à la plateforme — ce n'est "
                      "pas vous. Réessayez dans quelques minutes."),
    "not_found": ("SoundCloud ne connaît pas ce lien. Vérifiez qu'il s'agit bien de "
                  "l'adresse de votre profil, par exemple https://soundcloud.com/votre-nom"),
    "upstream_error": "SoundCloud n'a pas répondu. Réessayez dans quelques minutes.",
    "is_a_track": ("Ce lien pointe vers un titre, pas vers un profil. Cliquez sur votre "
                   "nom d'artiste en haut de la page, puis copiez l'adresse."),
}


def resolve_message(code: str) -> str:
    """The artist-facing sentence for a resolution failure code.

    Rendered HERE and not raised from `src/utils/`: nothing built from a caught
    exception may reach the UI in a credentials module (those pass credentials in
    query strings, so an exception's text can carry one —
    `test_no_probe_surfaces_a_whole_exception`). Going through `t()` also means an
    English reader gets English, which a sentence hardcoded in the resolver could not.
    """
    return t(f"credentials.resolve.{code}",
             _RESOLVE_MESSAGES.get(code, _RESOLVE_MESSAGES["upstream_error"]))


def _handle_save(db, platform_key, fields_def, artist_id, form_values, existing_values):
    """Prépare et sauvegarde les credentials chiffrés."""
    try:
        secrets = {}
        extra = {}

        for field in fields_def:
            key = field['key']
            new_val = form_values.get(key, '').strip()

            # Secret vide → conserver l'ancienne valeur
            if not new_val and field['secret']:
                new_val = existing_values.get(key, '')

            if field['secret']:
                secrets[key] = new_val
            elif new_val:
                extra[key] = new_val
            else:
                # Do NOT persist an empty identity. `{"user_id": ""}` is falsy, so
                # every consumer that wrote `creds.get('user_id') or os.getenv(...)`
                # silently switched to the ADMIN's env identity. An artist who opens
                # a tab and saves without filling it in must stay "not connected",
                # not inherit someone else's account.
                extra.pop(key, None)

        # Spotify: the artist supplies their profile URL/ID — normalise it and sync to
        # saas_artists.spotify_artist_id, the per-tenant key both spotify_api_daily
        # (collection list) and the track→tenant bridge read. Store the bare ID back in
        # extra_config too so the form round-trips the normalised value.
        if platform_key == 'spotify':
            sp_id = extract_spotify_artist_id(extra.get('spotify_artist_id', ''))
            # Only write it back when there IS one. This assignment used to be
            # unconditional and ran AFTER the empty-pop above, so Spotify was the
            # single platform that could persist `{"spotify_artist_id": ""}` — the
            # exact shape the pop exists to prevent, and a row that reads as
            # "connected" to every surface that counts rows instead of identities.
            if sp_id:
                extra['spotify_artist_id'] = sp_id
            else:
                extra.pop('spotify_artist_id', None)

        # SoundCloud: the artist supplies their PROFILE URL; the pipeline needs the
        # numeric user id. Normalised HERE, at write time, for the same reason the
        # Meta block below is: the connection test resolving it would prove the link
        # good and still persist the URL, and `soundcloud_daily` reads the column, not
        # the test. Until 2026-09-03 the guide bridged this by hand: open /discover,
        # display the page's HTML source, hunt for the `soundcloud:users:` marker and
        # copy the digits. (The keyboard shortcut is deliberately not spelled out here:
        # `guide-single-os-shortcut` greps for it, and a comment DESCRIBING the old
        # step would fire the detector for the step itself.)
        # `runbook-artist-test-session.md:127` calls that gesture one to do on a screen
        # share; 2 of the 4 tenants who reached this page never got past it.
        if platform_key == 'soundcloud':
            typed = str(extra.get('user_id', '')).strip()
            if typed and not typed.isdigit():
                from src.utils.platform_identity_resolver import (
                    ResolutionError,
                    soundcloud_user_id_from_url,
                )
                try:
                    resolved, permalink = soundcloud_user_id_from_url(typed)
                except ResolutionError as exc:
                    # Refuse the save rather than store a URL in a numeric column.
                    # A row that looks filled but cannot collect is worse than an
                    # empty one: every surface that counts rows reads it as connected.
                    st.error(resolve_message(exc.code))
                    return
                extra['user_id'] = resolved
                st.caption(t("credentials.soundcloud.resolved",
                             "Lien reconnu : soundcloud.com/{p} → User ID **{i}**")
                           .format(p=permalink, i=resolved))

        # Meta: N comptes publicitaires → une liste canonique (R53 / ADR-013).
        # Fait AVANT le contrôle de forme, pour que celui-ci voie la valeur qui sera
        # réellement écrite : normaliser après aurait validé la saisie et stocké
        # autre chose.
        if platform_key == 'meta':
            import re as _re

            from src.utils.tenant_identity import (
                malformed_meta_accounts,
                with_meta_accounts,
            )
            typed_extra = extra.pop('extra_account_ids', '')
            accounts = [extra.get('account_id', ''),
                        *[p for p in _re.split(r"[,\n;]+", typed_extra)]]
            extra = with_meta_accounts(extra, accounts)
            bad_accounts = malformed_meta_accounts(extra)
            if bad_accounts:
                st.error(t(
                    "credentials.meta.accounts_malformed",
                    "❌ Compte(s) publicitaire(s) au mauvais format : {bad}. "
                    "Chiffres uniquement, éventuellement préfixés par `act_`, "
                    "**un par ligne**."
                ).format(bad=", ".join(bad_accounts)))
                return

        # Refuse a malformed identity BEFORE anything else touches it. These values
        # are interpolated into REST paths and `requests` does not percent-encode
        # `/` in a path you build, so a free-text id is a URL the tenant chooses.
        # Verified 2026-08-22: ig_user_id = "me/accounts" turned the platform probe
        # into a call to /me/accounts carrying the shared System User token.
        bad = malformed_identities({platform_key: extra})
        if bad:
            logical, value = next(iter(bad.items()))
            spec = PLATFORM_IDENTITIES[logical]
            st.error(t(
                "credentials.identity_malformed",
                "❌ **{field}** n'a pas le format attendu. Attendu : `{shape}`. "
                "Copie l'identifiant seul, sans URL ni caractère autour."
            ).format(field=spec.field, shape=spec.pattern))
            return

        # Refuse an identity another tenant already claims. Nothing in the schema
        # prevents it, and the consequence is not cosmetic: both accounts would
        # collect the same upstream data, and the Spotify DAG refuses to guess
        # whose catalogue it is. Better a clear "no" now than two wrong dashboards.
        #
        # Checked for EVERY logical identity this tab carries, not for the tab.
        # Called with the tab key, the meta tab resolved to `account_id` only and
        # `ig_user_id` was never compared against anyone — the uniqueness rule was
        # present, derived, tested, and unreachable from the one call site that
        # matters. The test passed because it called with the logical name, which
        # the save path never does.
        for logical, spec in PLATFORM_IDENTITIES.items():
            if spec.storage != platform_key or not extra.get(spec.field):
                continue
            conflict = find_identity_conflict(db, artist_id, logical, extra)
            if not conflict:
                continue
            # `_other` is the tenant holding it — never rendered, see _core.py.
            field, value, _other = conflict
            st.error(t(
                "credentials.identity_taken",
                "❌ **{field} = {value}** est déjà rattaché à un autre compte. "
                "Un identifiant de plateforme ne peut appartenir qu'à un seul "
                "artiste — vérifie que c'est bien le tien. Si tu penses qu'il "
                "s'agit d'une erreur, contacte l'administrateur."
            ).format(field=field, value=value))
            # L'artiste ne doit pas apprendre qui d'autre existe sur la plateforme ;
            # l'admin, lui, doit pouvoir trancher sans ouvrir psql — c'est lui que
            # le message ci-dessus invite à contacter.
            if is_admin():
                st.caption(t("credentials.identity_taken_admin",
                             "🛠️ Détenu par l'artiste #{other}.").format(other=_other))
            return

        # `''` means "do not touch the stored secret", NOT "erase it" — see the
        # contract in `_save_credentials`. The soundcloud and meta tabs declare no
        # secret field at all, so they ALWAYS land here with an empty blob while
        # their rows hold a rotated refresh_token / the System User token.
        encrypted_blob = _encrypt_secrets(secrets) if any(secrets.values()) else ''
        _save_credentials(db, artist_id, platform_key, encrypted_blob, extra)

        # Spotify's identity is mirrored on saas_artists.spotify_artist_id, which is
        # what spotify_api_daily reads. The mirror list lives in one module so a second
        # writer cannot miss it — tools/create_canary.py did, and produced a tenant that
        # looked connected everywhere and collected nothing (2026-08-21).
        _mirror = mirrored_columns().get(platform_key)
        if _mirror:
            write_platform_identity(db, artist_id, platform_key, extra)

        # No Meta token expiry probe here — deliberately.
        #
        # It called _fetch_meta_token_expiry(access_token, app_id, app_secret) with
        # three values the meta tab never collects (it declares account_id and
        # ig_user_id only), so the probe returned None every time and the else-branch
        # fired on EVERY save, for EVERY artist: "⚠️ Impossible de récupérer la date
        # d'expiration du token Meta … Le renouvellement automatique ne fonctionnera
        # pas". A permanent warning about a central credential, shown on a per-artist
        # page, is indistinguishable from "your credentials are broken" — which is
        # what two beta testers reported.
        #
        # The token is a System User APP credential (ADR-006) that does not expire;
        # its health is reported by src/utils/central_apps.py::check_meta, which the
        # nightly alert_monitor reads.

        # Auto-trigger the first data pull for every identity this save declared.
        # One tab can carry several: saving the Meta tab with both an ad account and
        # an Instagram business account must start BOTH collections. Keyed on the tab
        # it only ever started meta_ads_api_daily, so an artist who connected
        # Instagram got no first pull at all.
        # Non-blocking: a DAG-trigger failure must NOT invalidate the credential save.
        for dag_id in dags_for_save(platform_key, extra):
            try:
                import os
                from src.utils.airflow_trigger import AirflowTrigger
                # Accept either env naming: the dashboard container exposes the Airflow
                # admin creds as AIRFLOW_USERNAME/AIRFLOW_PASSWORD (docker-compose), while
                # AIRFLOW_ADMIN_* is the .env name. A hard os.environ[...] on the wrong
                # name silently broke every post-save auto-trigger ("credentials OK but
                # no data"). Read both; never KeyError.
                trigger = AirflowTrigger(
                    base_url=os.getenv('AIRFLOW_BASE_URL', 'http://localhost:8080'),
                    username=(os.getenv('AIRFLOW_ADMIN_USERNAME')
                              or os.getenv('AIRFLOW_USERNAME', 'admin')),
                    password=(os.getenv('AIRFLOW_ADMIN_PASSWORD')
                              or os.getenv('AIRFLOW_PASSWORD', '')),
                )
                result = trigger.trigger_dag(dag_id, conf={'artist_id': artist_id})
                if result.get('success'):
                    # The artist reads the DAG status right after this toast. The
                    # cached view of "latest run per DAG" is now wrong by definition,
                    # so drop it here rather than letting the TTL decide: this is the
                    # one moment staleness is felt as the page lying.
                    from src.dashboard.utils.airflow_monitor import cached_last_run_per_dag
                    cached_last_run_per_dag.clear()
                    st.toast(t("credentials.collect_started",
                               "🚀 Collecte {platform} lancée — données disponibles dans ~2 min").format(
                                   platform=platform_key), icon="✅")
                else:
                    # `trigger_dag` RETURNS {'success': False} on an HTTP error — it
                    # never raises, so the `except` below could not see the most
                    # likely failures (Airflow unreachable, wrong credentials, 403).
                    # The artist read "✅ Credentials enregistrés", no first pull ever
                    # ran, and nothing said so: literally "I connected it and nothing
                    # happened". Same class as `delivery-failure-logged-as-success`,
                    # one layer up.
                    logger.error("post-save trigger of %s failed for artist %s: %s",
                                 dag_id, artist_id, result.get('error'))
                    st.warning(t(
                        "credentials.dag_trigger_refused",
                        "⚠️ Identifiants enregistrés, mais la première collecte "
                        "**{dag}** n'a pas pu démarrer. Tes données arriveront à la "
                        "prochaine collecte automatique (cette nuit). Si rien n'est "
                        "arrivé demain, préviens-nous."
                    ).format(dag=dag_id))
            except Exception as trigger_err:
                logger.error("post-save trigger of %s raised for artist %s: %s",
                             dag_id, artist_id, type(trigger_err).__name__)
                st.warning(t("credentials.dag_trigger_failed",
                             "⚠️ Identifiants enregistrés, mais la première collecte "
                             "n'a pas pu démarrer ({err}). Elle repartira cette nuit."
                             ).format(err=type(trigger_err).__name__))

        # ── The verdict, now, instead of tonight ────────────────────────────
        # `make artist-preflight` and the nightly `alert_monitor` both answer "does
        # this tenant actually work". The nightly one runs at 23h: an artist who
        # connects a platform at 15h had no answer for eight hours, and the manual
        # command is not something an artist can run.
        #
        # This is the first moment in the whole flow where the question HAS an
        # answer — credentials exist, the identity is stored, the API can be called.
        # Verification time is too early (nothing configured yet, five reds carrying
        # no information); the nightly run is too late.
        #
        # `run_probes_now` reuses the probe the "🔌 Vérifier maintenant" button runs
        # and REMEMBERS the verdict in `tenant_platform_probe`, so the matrix on
        # Home, Onboarding and this page shows it without anyone pressing anything.
        # It never raises and never opens a connection of its own (rule #9): `db` is
        # the one this view already holds.
        try:
            from src.dashboard.utils.status_matrix import read_probes, run_probes_now
            with st.spinner(t(
                    "credentials.probing_now",
                    "⏳ Configuration de **{platform}** en cours — on interroge la "
                    "plateforme pour savoir si elle répond…").format(
                        platform=platform_label(platform_key))):
                run_probes_now(db, artist_id, [platform_key])
                # Le verdict est ÉCRIT par `run_probes_now`, qui ne rend qu'un
                # compteur ; on le relit à sa source, celle que la matrice lit.
                # Le porter en session est obligatoire : le `st.rerun()` ci-dessous
                # efface tout ce qui vient d'être écrit à l'écran — c'est pour ça que
                # le `st.success` qui vivait ici n'a jamais été lu par personne.
                st.session_state[VERDICT_KEY] = _verdict_from_probes(
                    read_probes(db, artist_id), platform_key)
        except Exception as probe_err:  # noqa: BLE001 — a verdict is a bonus, never a blocker
            logger.warning("post-save probe of %s failed for artist %s: %s",
                           platform_key, artist_id, type(probe_err).__name__)
            st.session_state[VERDICT_KEY] = (platform_key, None, "")

        st.rerun()

    except Exception as e:
        st.error(t("credentials.save_error",
                   "❌ Erreur lors de la sauvegarde : {err}").format(err=e))
