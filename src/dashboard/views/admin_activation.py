"""Le panneau d'activation de la supervision admin — R149.

Type: Sub
Uses: src.utils.activation, streamlit, pandas
Triggers: views/admin.py (_render_supervision)
Persists in: nothing

Sorti de `views/admin.py` le 2026-09-22, le jour où ce fichier a franchi 1 200
lignes. Le cliquet `tests/test_a_file_only_gets_shorter.py` le dit sans détour :
« les ajouter à FROZEN fige la dette ; les découper la retire ». Ce panneau est le
candidat évident — il ne partage aucun état avec le reste de la vue et ne lit que
`src/utils/activation.py`.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src.dashboard.utils.i18n import t


def _render_activation(db) -> None:
    """LA métrique — R149, et elle a été choisie par la mesure, pas par goût.

    *Lean Analytics* : « at any given time, there's one metric you should care about
    above all else. » Ce panneau en portait sept, dont MRR et ARPU, à un stade où
    les comptes se comptent sur les doigts d'une main.

    Mesuré le 2026-09-22 en production : **deux locataires humains activés sur
    cinq**. Trois comptes n'ont jamais reçu une seule ligne — l'un depuis cent
    jours. Leur `etl_run_log` ne porte aucun échec, il porte `skipped` : le garde
    d'identité les saute parce qu'ils n'ont déclaré aucun identifiant de
    plateforme, et `alert_monitor` dit explicitement que `skipped` n'est pas un
    signalement. Correct pour l'exploitation, aveugle pour le commerce.

    Le MRR et l'ARPU ne disparaissent pas — ils passent sous un repli. Ce n'est
    pas une opinion sur leur valeur, c'est l'ordre de lecture : tant que trois
    comptes sur cinq regardent un écran vide, le revenu par client répond à une
    question que personne n'a encore le droit de poser.
    """
    from src.utils.activation import (ACTIVATION_WINDOW_DAYS, activation_sql,
                                      dormant_tenants_sql)

    rows = db.fetch_query(activation_sql())
    actives, total = (rows[0] if rows else (0, 0))
    actives, total = int(actives or 0), int(total or 0)

    st.subheader(t("admin.activation_header",
                   "🎯 Activation — la métrique du stade actuel"))
    c1, c2 = st.columns([1, 2])
    c1.metric(
        t("admin.metric_activation", "Artistes activés"),
        f"{actives}/{total}",
        delta=f"{actives / total:.0%}" if total else None,
        delta_color="off",
    )
    c2.caption(t(
        "admin.activation_def",
        "**Activé** = au moins une plateforme a livré au moins une ligne dans les "
        "{j} derniers jours. Ni une connexion, ni un identifiant saisi, ni un DAG "
        "qui tourne : une donnée RENDUE à l'artiste."
    ).format(j=ACTIVATION_WINDOW_DAYS))

    dormants = db.fetch_query(dormant_tenants_sql())
    if not dormants:
        st.success(t("admin.activation_all",
                     "✅ Tous les comptes reçoivent au moins une plateforme."))
        return

    # Nommés, pas comptés : un ratio ne se rattrape pas, un compte si.
    st.warning(t(
        "admin.activation_dormant",
        "**{n} compte(s) n'ont jamais reçu de donnée.** Chacun s'est inscrit, a reçu "
        "trente jours de Premium, et regarde un tableau de bord vide."
    ).format(n=len(dormants)))
    st.dataframe(
        pd.DataFrame(dormants, columns=[
            t("admin.act_col_id", "ID"),
            t("admin.act_col_name", "Artiste"),
            t("admin.act_col_signup", "Inscrit le"),
            t("admin.act_col_days", "Jours"),
            t("admin.act_col_trial", "Essai jusqu'au"),
            t("admin.act_col_plats", "Plateformes"),
        ]),
        hide_index=True, width="stretch",
    )
