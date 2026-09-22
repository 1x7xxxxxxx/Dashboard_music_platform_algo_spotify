"""L'activation — la seule métrique qui compte au stade où en est streaMLytics.

Type: Utility
Uses: nothing (rend du SQL, ne l'exécute pas)
Triggers: dashboard admin (supervision), alert_monitor
Persists in: nothing

Pourquoi ce module existe — MESURÉ EN PRODUCTION LE 2026-09-22
--------------------------------------------------------------

R149 demandait de choisir UNE métrique au sens de l'OMTM de *Lean Analytics* :
« at any given time, there's one metric you should care about above all else. »
Le panneau de supervision en portait sept — inscriptions 7 j, inscriptions 30 j,
comptes vérifiés, artistes actifs, MRR, abonnés payants, ARPU — et aucune ne
répondait à la question du stade.

La mesure a tranché toute seule. Sur les **sept locataires non-propriétaires** en
production :

===========================  =====
plateformes qui LIVRENT      artistes
===========================  =====
zéro                         **4**  (11, 13, 17, 18)
une                          1      (12)
trois                        1      (14)
cinq                         1      (le propriétaire)
===========================  =====

Quatre comptes sur sept n'ont **jamais vu une seule ligne de donnée**. Leur
`etl_run_log` ne porte pas d'échec : il porte `skipped`, quarante-neuf fois pour
l'un d'eux. Le garde d'identité fait son travail — un locataire qui n'a déclaré
aucun identifiant est sauté, et c'est correct — mais **`alert_monitor` le dit
explicitement : « `skipped` is deliberately NOT a finding »**. Correct côté
exploitation, aveugle côté commerce : rien, nulle part, ne signale qu'un compte
en essai de trente jours regarde un tableau de bord vide depuis trois semaines.

C'est la même observation que R147 vue de l'autre bout : trois essais arrivés à
terme, zéro conversion. Ce n'est pas une énigme de prix — **les essais n'ont
jamais eu de produit à essayer**. Discuter du tarif (R148), d'un axe de valeur
(R152) ou d'options de prestation (R150) avant d'avoir corrigé ça reviendrait à
optimiser la caisse d'un magasin dont la porte est fermée.

Ce que l'activation N'EST PAS
------------------------------
Ni une connexion, ni un identifiant saisi, ni un DAG qui tourne. **Une ligne
livrée**, et rien d'autre : c'est le premier instant où le produit rend quelque
chose à celui qui s'est inscrit. Les trois autres définitions étaient déjà
mesurées ailleurs et aucune n'a vu le trou.
"""
from __future__ import annotations

# Trente jours : une plateforme qui a livré au trimestre dernier et plus rien
# depuis n'active personne aujourd'hui. La fenêtre est la même que celle des
# compteurs d'inscription, pour qu'un ratio garde un sens.
ACTIVATION_WINDOW_DAYS = 30

# Une seule plateforme suffit. Le seuil n'est pas « toutes » : un artiste qui
# ne publie que sur Spotify est pleinement servi avec une source.
ACTIVATION_MIN_PLATFORMS = 1


def activation_sql(window_days: int = ACTIVATION_WINDOW_DAYS) -> str:
    """Le SQL qui rend (activés, total) parmi les locataires HUMAINS.

    Le prédicat de livraison est `status = 'success' AND rows_inserted > 0` — les
    deux conditions, pas une. Mesuré : un `success` à zéro ligne existe (l'artiste
    13 en porte trente sur SoundCloud) et ne montre rien à personne.
    """
    from src.utils.tenant_kind import HUMAN_TENANTS

    return f"""
        WITH livraisons AS (
            SELECT artist_id, COUNT(DISTINCT platform) AS plateformes
              FROM etl_run_log
             WHERE status = 'success'
               AND rows_inserted > 0
               AND created_at > NOW() - INTERVAL '{int(window_days)} days'
             GROUP BY artist_id
        )
        SELECT COUNT(*) FILTER (
                   WHERE COALESCE(l.plateformes, 0) >= {int(ACTIVATION_MIN_PLATFORMS)}
               ) AS actives,
               COUNT(*) AS total
          FROM saas_artists a
          LEFT JOIN livraisons l ON l.artist_id = a.id
         WHERE {HUMAN_TENANTS}
    """


def dormant_tenants_sql(window_days: int = ACTIVATION_WINDOW_DAYS) -> str:
    """Les comptes qui n'ont RIEN reçu — nommés, pas comptés.

    Un ratio ne se rattrape pas ; un compte, si. La liste porte l'âge du compte et
    la fin de son essai, parce que les deux disent ce qu'il reste de temps pour
    faire quelque chose.
    """
    from src.utils.tenant_kind import HUMAN_TENANTS

    return f"""
        WITH livraisons AS (
            SELECT artist_id, COUNT(DISTINCT platform) AS plateformes
              FROM etl_run_log
             WHERE status = 'success'
               AND rows_inserted > 0
               AND created_at > NOW() - INTERVAL '{int(window_days)} days'
             GROUP BY artist_id
        )
        SELECT a.id,
               a.name,
               a.created_at::date                                   AS inscrit_le,
               (NOW()::date - a.created_at::date)                   AS jours,
               a.promo_plan_expires_at::date                        AS essai_jusquau,
               COALESCE(l.plateformes, 0)                           AS plateformes
          FROM saas_artists a
          LEFT JOIN livraisons l ON l.artist_id = a.id
         WHERE {HUMAN_TENANTS}
           AND COALESCE(l.plateformes, 0) < {int(ACTIVATION_MIN_PLATFORMS)}
         ORDER BY a.created_at
    """
