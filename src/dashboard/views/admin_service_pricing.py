"""Les trois prix de la prestation, réglés depuis l'application — R150.

Type: Sub
Uses: streamlit, src.dashboard.utils.app_settings, src.dashboard.utils.service_offer
Triggers: views/admin.py (_tab_reglages)
Persists in: PostgreSQL spotify_etl (app_settings)

Sorti de `views/admin.py` le 2026-09-22, le jour même où ce panneau l'a fait
franchir 1 200 lignes — 1 211 exactement. Le cliquet
`tests/test_a_file_only_gets_shorter.py` laisse deux issues, et elles ne se valent
pas : « les ajouter à FROZEN fige la dette ; les découper la retire ». C'est le
deuxième geste, et c'est le même que `admin_activation.py` le matin même.

Ce panneau ne partage aucun état avec le reste de la vue Admin : il lit et écrit
trois réglages, et ne connaît du reste de la page que la connexion qu'on lui passe.
"""
from __future__ import annotations

import streamlit as st

from src.dashboard.utils.i18n import t


def render_service_pricing(db) -> None:
    """Les trois prix de la prestation — le seul endroit où ils s'écrivent.

    ⚠️ **Aucun montant n'est écrit dans le code**, et c'est délibéré : un prix
    figé dans l'arbre est un prix qui demande un redéploiement pour bouger, donc
    un prix qui ne bouge jamais. Tant que les trois ne sont pas posés, la page
    `service` ne montre AUCUNE grille à l'artiste et affiche ici même un rappel.

    Les trois, pas un seul : montrer un prix sur la seule colonne remplie ferait
    de l'option la moins chère la seule visible, soit l'inverse exact de ce que
    trois options servent à faire (Enns, *Pricing Creativity* p. 29).
    """
    from src.dashboard.utils.app_settings import (
        ReglageInvalide, env_impose, get_setting, set_setting)
    from src.dashboard.utils.service_offer import OPTIONS, grille_complete
    from src.dashboard.utils.ui import flash

    st.markdown(t("admin.settings_prices_header",
                  "**🎯 Prix de la prestation d'optimisation**"))
    st.caption(t(
        "admin.settings_prices_help",
        "Un nombre entier d'euros, sans décimale — `450`. Tant que les **trois** "
        "ne sont pas posés, l'artiste voit la prestation sans sa grille de prix."))

    valeurs = {o.cle_prix: get_setting(db, o.cle_prix, "") for o in OPTIONS}
    if not grille_complete(valeurs):
        st.warning(t(
            "admin.settings_prices_missing",
            "⚠️ La grille est incomplète : la page **🎯 Faire piloter mes "
            "campagnes** ne montre pas de prix. Renseigne les trois."))

    with st.form("reglage_prix_prestation"):
        saisies = {}
        for option in OPTIONS:
            impose = env_impose(option.cle_prix)
            saisies[option.cle_prix] = st.text_input(
                option.nom,
                value="" if impose else valeurs[option.cle_prix],
                disabled=impose,
                help=(t("admin.settings_prices_env",
                        "Imposé par l'environnement — retire la variable pour "
                        "reprendre la main ici.") if impose else option.perimetre))
        enregistrer = st.form_submit_button(
            t("admin.settings_save_prices", "💾 Enregistrer les trois prix"),
            width="stretch")

    if not enregistrer:
        return
    try:
        for cle, valeur in saisies.items():
            if not env_impose(cle):
                set_setting(db, cle, valeur)
    except ReglageInvalide as e:
        st.error(t("admin.settings_refused", "❌ {raison}").format(raison=e))
    else:
        flash(t("admin.settings_prices_saved",
                "✅ Prix enregistrés — ils s'appliquent dès maintenant sur la page "
                "de prestation."))
        st.rerun()
