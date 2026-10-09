"""Aperçu : déclencher les algos — ce que Road to Algo fait, en trois figures d'exemple. GRATUIT.

Type: Feature
Uses: example_figures (ALGO_PREVIEW), plan_gate.est_verrouille, navigation.goto, i18n
Depends on: src/dashboard/assets/examples/*.png (built by `make example-charts`)
Persists in: — (lecture seule)

R193 (2026-09-26), décision du propriétaire : « tes données sont gratuites, les prédictions
sont payantes » (ADR-029) — et un APERÇU gratuit de Road to Algo, juste au-dessus de la page
payante, sans cadenas.

R456 (2026-10-07, commentaires vocaux C8 et C10) : « reprendre les graphiques de la mise en
route, diminuer leur taille — là ça prend toute la page — et en dessous, supprimer tout le
texte » ; plus « un aperçu SHAP de l'impact de chaque paramètre sur Discover Weekly, Radio
et Release Radar, avec des données factices et une toute petite phrase ».

La page ne lit donc plus rien du locataire. Ce qu'elle montrait jusque-là — par algorithme
la porte la plus proche, l'écart, le levier, le budget en ordre de grandeur, et la liste des
critères devinés (R410) — a été RETIRÉ, pas déplacé : c'est le contenu de Road to Algo, que
le bouton ouvre. Trois figures égales en trois colonnes : l'image prend un tiers de la
largeur au lieu de toute la page.

R487 (2026-10-09, W10) : la figure SHAP gagne « Ta track » (score par critère + dépense
Meta), la phrase sous les figures disparaît, et un compte gratuit voit « Passer Premium »,
qui mène à Facturation, au lieu d'un cadenas vers Road to Algo.
"""
from __future__ import annotations

import streamlit as st

from src.dashboard.utils.example_figures import ALGO_PREVIEW, render_example
from src.dashboard.utils.i18n import t
from src.dashboard.utils.navigation import goto
from src.dashboard.utils.plan_gate import est_verrouille


def show() -> None:
    st.subheader(t("algo_preview.title", "Aperçu : déclencher les algos Spotify"))
    for col, name in zip(st.columns(len(ALGO_PREVIEW), gap="medium"), ALGO_PREVIEW):
        with col:
            render_example(name)
    # R487 (W10) : « Ouvrir Road to Algo » → un bouton vers Facturation pour qui n'est pas
    # premium. Le texte sous les figures est retiré : la figure SHAP porte ses légendes.
    # Le libellé suit la cible : jamais un bouton qui promet une page qu'on ne verra pas.
    locked = est_verrouille("trigger_algo")
    label = (t("algo_preview.upgrade", "⭐ Passer Premium") if locked
             else t("algo_preview.open", "🚀 Ouvrir Road to Algo"))
    if st.button(label, key="algo_preview_cta", type="primary", width="stretch"):
        goto("billing" if locked else "trigger_algo")
