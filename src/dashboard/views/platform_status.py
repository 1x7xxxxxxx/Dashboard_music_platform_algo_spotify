"""📋 État de tes plateformes — où en est chaque source, et quoi faire ensuite.

Type: Feature
Uses: view_session, render_status_matrix
Depends on: src/dashboard/utils/status_matrix.py
Persists in: nothing (lecture seule)

Pourquoi une page à elle
------------------------
La matrice vivait en tête de 🔑 Credentials API. Demandé le 2026-09-04 : « créer un
onglet qui s'appelle *État de tes plateformes* et qui possède uniquement ce panneau —
on l'enlève de Credentials API pour faciliter la vie à l'utilisateur ».

Mesuré avant de la déplacer, et c'est ce qui tranche : elle occupait les **900
premiers pixels** d'une page de 2141, poussant le champ à remplir à y=1475 et la
capture d'écran qui l'explique à y=1569. Le même artiste a signalé QUATRE FOIS
qu'« il n'y a pas le screen ». Il y était — sous la ligne de flottaison d'une page de
configuration, ce qui revient exactement au même.

Les deux blocs ne répondent pas à la même question, et c'est la vraie raison de les
séparer : la matrice dit **où j'en suis**, Credentials dit **ce que je dois saisir**.
Mettre un bilan au-dessus d'un formulaire, c'est faire lire avant de faire agir.
"""
import streamlit as st

from src.dashboard.utils import view_session
from src.dashboard.utils.i18n import t
from src.dashboard.utils.status_matrix import render_status_matrix


def show() -> None:
    st.title(t("platform_status.title", "📋 État de tes plateformes"))
    st.caption(t(
        "platform_status.subtitle",
        "Une ligne par source. La dernière colonne dit le geste qui reste — "
        "cliquable quand il se fait ailleurs dans l'application."))
    st.markdown("---")

    with view_session() as (db, artist_id):
        # La légende vit DANS la matrice, à côté des colonnes qu'elle explique.
        # Trois surfaces en écrivaient chacune une version, et deux ne disaient pas
        # ce que « Répond » et « Données » veulent dire.
        render_status_matrix(db, artist_id, key_suffix="status_page")


if __name__ == "__main__":
    show()
