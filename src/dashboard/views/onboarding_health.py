"""Onboarding health — per-artist readiness matrix.

Type: Feature
Uses: get_db_connection, get_artist_id/is_admin, src.utils.artist_readiness
Triggers: nav "🚦 Santé onboarding"
Persists in: nothing (read-only view)

The visible end of the per-artist closed loop: for each artist × platform, did the artist
provide the IDENTITY and is data actually LANDING? Turns the silent per-tenant gaps the Benken
week exposed (connected-but-0-rows, account-not-shared, empty channel) into a status + the
exact next action. Admin sees every active artist; an artist sees their own row.
"""
import pandas as pd
import streamlit as st

from src.dashboard.utils.status_matrix import render_status_matrix

from src.dashboard.utils import get_db_connection
from src.dashboard.auth import get_artist_id, is_admin
from src.utils.artist_readiness import artist_readiness, NO_DATA
from src.dashboard.utils.guide_assets import credentials_guide_pdf
from src.dashboard.utils.i18n import t


def _matrix_df(matrix: list) -> pd.DataFrame:
    return pd.DataFrame([{
        "Plateforme": m["label"],
        "Statut": f"{m['icon']} {m['status_label']}",
        "Dernière donnée": str(m["last_dt"])[:16] if m["last_dt"] else "—",
        "Action": m["next_action"],
    } for m in matrix])


def show():
    st.title("🚦 Santé onboarding")
    st.caption(
        "Pour chaque artiste × plateforme : l'identité est-elle fournie, et les données "
        "arrivent-elles ? 🟢 OK · ⏸️ silence normal · 🟡 anciennes · 🔴 connecté mais "
        "aucune donnée · ⚪ à connecter."
    )

    db = get_db_connection()
    if db is None:
        st.error("Base de données injoignable.")
        return
    try:
        if is_admin():
            df = db.fetch_df("SELECT id, name FROM saas_artists WHERE active = TRUE ORDER BY id")
            artists = [(int(r["id"]), r["name"]) for _, r in df.iterrows()]
            if not artists:
                st.info("Aucun artiste actif.")
                return
        else:
            aid = get_artist_id()
            if aid is None:
                st.error("Session invalide.")
                return
            row = db.fetch_query("SELECT name FROM saas_artists WHERE id = %s", (aid,))
            artists = [(aid, row[0][0] if row else f"#{aid}")]

        total_red = 0
        for aid, name in artists:
            matrix = artist_readiness(db, aid)
            reds = [m for m in matrix if m["status"] == NO_DATA]
            total_red += len(reds)
            # L'IDENTIFIANT NE S'AFFICHE QUE POUR L'ADMIN. Signalé le 2026-09-06 :
            # « retire id=xx, inutile pour l'user ». Il l'est, et pas seulement par
            # encombrement : un artiste ne voit QUE sa propre ligne, donc le numéro ne
            # distingue rien — il ne peut pas se tromper d'artiste. Pour l'admin, qui
            # déroule la liste entière, c'est l'inverse : deux artistes peuvent porter
            # le même nom, et c'est ce numéro qu'il colle dans
            # `make artist-preflight ARTIST=<id>`.
            #
            # Le supprimer pour tout le monde aurait retiré à l'admin le seul endroit
            # de l'app où il lit cet identifiant.
            header = (f"{name} (id={aid}) — " if is_admin() else f"{name} — ")
            header += " ".join(m["icon"] for m in matrix)
            with st.expander(header, expanded=bool(reds) or not is_admin()):
                # The same renderer as the artist's own pages: an admin looking at a
                # blocked tenant must see exactly what that tenant sees, or the two
                # of them are talking about different screens.
                render_status_matrix(db, aid, key_suffix=f"health{aid}")

        if is_admin():
            if total_red:
                st.warning(f"🔴 {total_red} plateforme(s) connectée(s) sans données — action requise.")
            else:
                st.success("✅ Aucun blocage 'connecté sans données' sur les artistes actifs.")

        # ── Ce qui vient du « 📋 Guide de démarrage », supprimé le 2026-09-06 ──
        #
        # Cette page-là redisait en quatre listes à puces ce que l'assistant montre,
        # ce que les onglets de Credentials déplient et ce que la matrice ci-dessus
        # mesure. Deux de ses sections n'existaient nulle part ailleurs, et elles
        # atterrissent ICI parce que c'est ici qu'on est quand on se demande ce qui
        # manque : « ajouter le lien de téléchargement du guide dans l'onglet santé
        # onboarding, je pense que c'est le plus pertinent » (2026-09-06).
        st.markdown("---")
        _render_credentials_pdf()
        _render_csv_definitions()
        _render_remaining_steps(db)
    finally:
        db.close()


def _render_credentials_pdf() -> None:
    """Le PDF des identifiants — le même que celui joint à l'e-mail de vérification.

    Il n'existait QUE dans cet e-mail : perdu le mail, perdu le PDF, et aucun bouton
    nulle part dans l'application. Il vivait ensuite dans le guide de démarrage ;
    celui-ci supprimé, il se pose ici.

    `credentials_guide_pdf` préfère la copie pré-rendue et met le reste en cache : le
    régénérer à chaque rerun coûtait 573 ms mesurés en prod.
    """
    st.subheader(t("onboarding_health.cred_pdf_title",
                   "📘 Guide des identifiants (PDF, avec captures d'écran)"))
    lang = st.session_state.get("lang", "fr")
    pdf_bytes = credentials_guide_pdf(lang)
    if pdf_bytes:
        st.download_button(
            t("onboarding_health.cred_pdf_dl",
              "⬇️ Télécharger le guide des identifiants"),
            data=pdf_bytes,
            file_name=f"streamlytics_guide_identifiants_{lang}.pdf",
            mime="application/pdf",
            key="dl_cred_guide_pdf_health",
        )
        st.caption(t("onboarding_health.cred_pdf_note",
                     "C'est le même document que celui joint à ton e-mail de "
                     "vérification — plateforme par plateforme, avec les captures."))
    else:
        # WeasyPrint absent ou guide introuvable : on le dit, on ne casse pas.
        st.info(t("onboarding_health.cred_pdf_unavailable",
                  "Le PDF n'a pas pu être généré ici. Il reste disponible en pièce "
                  "jointe de ton e-mail de vérification, et les mêmes étapes sont "
                  "dépliables sur la page **🔑 Credentials API**."))


def _render_csv_definitions() -> None:
    """Ce que chaque CSV contient, et le fichier attendu.

    Les définitions vivent dans `content/csv_guides.py` — intitulé, colonnes
    attendues, nom de fichier — et n'étaient rendues que sur la page d'import, dans un
    dépliant fermé. Un artiste qui se demande « c'est quoi ce CSV ? » n'est pas en
    train d'en déposer un : il est là, devant une ligne qui lui dit qu'il en manque un.
    """
    st.subheader(t("onboarding_health.csv_defs_title",
                   "📄 Les CSV attendus, et ce qu'ils contiennent"))
    try:
        from src.dashboard.content.csv_guides import CSV_GUIDES
    except Exception:      # noqa: BLE001 — la page reste lisible sans cette section
        return
    for guide in CSV_GUIDES:
        with st.expander(f"{guide.icon} {guide.title}", expanded=False):
            st.markdown(guide.intro)
            for exp in guide.expected:
                st.markdown(
                    t("onboarding_health.csv_expected",
                      "**{label}** — fichier `{hint}`").format(
                          label=exp.label, hint=exp.filename_hint))
                if exp.columns:
                    st.caption(
                        t("onboarding_health.csv_columns",
                          "Colonnes attendues : {cols}")
                        .format(cols=", ".join(exp.columns)))


def _render_remaining_steps(db) -> None:
    """Ce qu'il RESTE à faire, LU dans la déclaration — jamais recopié ici.

    Demandé le 2026-09-12 : « rajouter dans mise en route + santé onboarding
    l'action de saisir mes ajouts en playlist S4A ».

    La tentation était d'écrire un second `_render_next_step_*` à la main. Ce serait
    une TROISIÈME liste des mêmes étapes — l'accueil en a une, `setup_completion` la
    déclare — et la classe que ce dépôt paie le plus souvent est exactement celle-là :
    une même question, plusieurs listes, qui divergent au premier ajout. L'étape
    suivante ajoutée au registre apparaîtra ici sans qu'on y touche.

    Ne montre que les étapes NON FAITES : cette page répond à « qu'est-ce qui me
    manque », et lister ce qui est déjà fait la transformerait en récapitulatif.

    Elle résout le locataire ELLE-MÊME. La variable `aid` de `show()` n'existe que
    dans la branche non-admin — la lui passer levait un `NameError` pour un admin,
    qui voit la page de TOUS les artistes. Sans locataire courant, il n'y a pas de
    geste personnel à proposer, et la section ne s'affiche pas.
    """
    from src.dashboard.auth import get_artist_plan
    from src.dashboard.utils.navigation import goto
    from src.dashboard.utils.setup_completion import (
        STEP_HINTS, STEP_LABELS, read_setup_state)

    artist_id = get_artist_id()
    if artist_id is None:
        return
    try:
        state = read_setup_state(db, artist_id, plan=get_artist_plan())
    except Exception:      # noqa: BLE001 — un renvoi absent vaut mieux qu'un écran mort
        return
    todo = [s for s in state.steps if not s.done]
    if not todo:
        return
    st.subheader(t("onboarding_health.next_title", "👉 Et ensuite"))
    for step in todo:
        if st.button(STEP_LABELS[step.key](), key=f"_health_goto_{step.key}",
                     width="stretch"):
            goto(step.page)
        hint = STEP_HINTS.get(step.key)
        if hint is not None:
            st.caption(hint())


def _render_next_step_mapping() -> None:
    """CONSERVÉE mais plus appelée — voir `_render_remaining_steps`.

    Le geste d'APRÈS, nommé là où l'on constate que le reste est fait.

    Demandé le 2026-09-06 : « je sais pas trop où mettre l'action de valider le
    mapping automatique une fois qu'on a terminé avec les credentials ».

    Un RENVOI, et pas une seconde copie de l'action. Le mapping garde son onglet — il
    porte un tableau, des suggestions et un backlog qui ne tiennent pas dans un
    encadré — et rendre son bouton ici en ferait deux surfaces pour un même geste,
    donc deux états, ce que ce dépôt a déjà payé (`two-widgets-for-one-gesture`).
    """
    st.subheader(t("onboarding_health.next_title", "🔗 Et ensuite : relier tes titres"))
    st.caption(t(
        "onboarding_health.next_body",
        "Une fois tes sources connectées, il reste à dire quelle campagne Meta "
        "correspond à quel titre. L'application propose des associations "
        "automatiques : il n'y a qu'à les valider."))
    if st.button(t("onboarding_health.next_cta",
                   "🔗 Ouvrir le mapping cross-plateforme →"),
                 key="_health_goto_mapping"):
        from src.dashboard.utils.navigation import goto
        goto("meta_mapping")
