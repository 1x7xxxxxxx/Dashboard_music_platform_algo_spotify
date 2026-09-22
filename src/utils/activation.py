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


def _livraisons_cte(window_days: int) -> str:
    """La CTE `livraisons` : une plateforme par ligne RÉELLEMENT en base.

    ⚠️ ELLE NE LIT PLUS `etl_run_log`, ET LA RAISON EST MESURÉE EN PRODUCTION.
    -------------------------------------------------------------------------
    Le prédicat d'origine était `status = 'success' AND rows_inserted > 0`. Il est
    faux, et le docstring de ce module se contredisait lui-même en le justifiant :
    il citait l'artiste 13 (« trente `success` à zéro ligne sur SoundCloud ») pour
    prouver qu'il fallait exiger `rows_inserted > 0`, **et il annonçait UNE
    plateforme pour l'artiste 12, qui en a DEUX.**

    Relevé en production le 2026-09-22, les deux cas côte à côte :

    ==========================  =========================  ==================
    (artiste, plateforme)        `etl_run_log`              la table de données
    ==========================  =========================  ==================
    12 / youtube                32 `success`, **0 ligne**   **95 lignes**, la
                                                            plus récente du JOUR
    13 / soundcloud             31 `success`, 0 ligne       0 ligne
    12 / soundcloud (témoin)    31 `success`, 31 à >0       672 lignes
    ==========================  =========================  ==================

    `rows_inserted = 0` signifie donc « la collecte n'a rien inséré CETTE FOIS » —
    ce qui est vrai d'un upsert idempotent qui ne trouve rien de neuf — et jamais
    « cette plateforme ne livre pas ». Sur les deux paires où le compteur est à
    zéro partout, **une sur deux est un mensonge** : YouTube alimente Benken tous
    les jours, et l'activation ne le voyait pas.

    La question « cette plateforme a-t-elle livré ? » se lit donc dans la TABLE DE
    DONNÉES, jamais dans le journal d'exécution. C'est déjà ce que fait
    `get_source_freshness` ; ce module était la dernière surface à croire le journal.

    Le SQL est composé depuis `src.utils.source_registry`, le tronc de R154 — donc
    une source ajoutée au registre entre ici sans qu'on y touche. Les noms de tables
    et de colonnes viennent d'un `frozenset` d'allowlist dérivé du registre avant
    interpolation (règle transverse 8) ; l'identifiant du locataire reste un `%s`.
    """
    from src.utils.source_registry import SOURCES, colonne_de_mesure

    # Règle 8 : l'allowlist est DÉRIVÉE du registre, donc elle ne peut pas s'en
    # écarter. Un nom qui n'y est pas ne s'interpole pas.
    tables = frozenset(s.table for s in SOURCES)
    colonnes = frozenset(colonne_de_mesure(s.cle) for s in SOURCES)
    cols_locataire = frozenset(s.artist_col for s in SOURCES if s.artist_col)
    ponts = frozenset(s.artist_filter for s in SOURCES if s.artist_filter)

    branches = []
    for src in SOURCES:
        mesure = colonne_de_mesure(src.cle)
        if src.table not in tables or mesure not in colonnes:
            raise ValueError(f"{src.cle}: table ou colonne hors allowlist")
        if src.artist_col:
            if src.artist_col not in cols_locataire:
                raise ValueError(f"{src.cle}: colonne de locataire hors allowlist")
            scope = f"{src.artist_col} = a.id"
        else:
            if src.artist_filter not in ponts:
                raise ValueError(f"{src.cle}: pont hors allowlist")
            # Le pont porte un `%s` pour la flotte ; ici on corrèle sur `a.id`.
            scope = src.artist_filter.replace("%s", "a.id")
        # ⚠️ `EXISTS`, PAS `SELECT … LIMIT 1`. Le premier jet écrivait
        # `SELECT … FROM t WHERE … LIMIT 1` dans chaque branche : **Postgres refuse un
        # `LIMIT` dans une branche d'`UNION ALL` sans parenthèses** — « syntax error at
        # or near UNION », rejoué sur la base de production le 2026-09-22. Et
        # retirer le `LIMIT` sans rien d'autre aurait été pire que l'erreur : le
        # `COUNT(*)` extérieur aurait compté les LIGNES, pas les plateformes, et une
        # source à 672 lignes aurait rendu une activation de 672.
        # `EXISTS` rend au plus une ligne par branche, sans parenthèses ni `LIMIT`, et
        # il court-circuite dès la première ligne trouvée.
        branches.append(
            f"            SELECT {src.cle!r} AS plateforme WHERE EXISTS (\n"
            f"                 SELECT 1 FROM {src.table}\n"
            f"                  WHERE {scope}\n"
            f"                    AND {mesure} > NOW() - INTERVAL "
            f"'{int(window_days)} days')")
    return "\n            UNION ALL\n".join(branches)


def activation_sql(window_days: int = ACTIVATION_WINDOW_DAYS) -> str:
    """Le SQL qui rend (activés, total) parmi les locataires HUMAINS.

    Le prédicat de livraison est **une ligne présente dans la table de données**, dans
    la fenêtre, et rien d'autre. Voir `_livraisons_cte` pour la mesure de production
    qui a écarté `etl_run_log.rows_inserted > 0`.
    """
    from src.utils.tenant_kind import HUMAN_TENANTS

    return f"""
        SELECT COUNT(*) FILTER (WHERE l.plateformes >= {int(ACTIVATION_MIN_PLATFORMS)})
                   AS actives,
               COUNT(*) AS total
          FROM saas_artists a
          CROSS JOIN LATERAL (
              SELECT COUNT(*) AS plateformes FROM (
{_livraisons_cte(window_days)}
              ) AS s
          ) AS l
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
        SELECT a.id,
               a.name,
               a.created_at::date                 AS inscrit_le,
               (NOW()::date - a.created_at::date) AS jours,
               a.promo_plan_expires_at::date      AS essai_jusquau,
               l.plateformes                      AS plateformes
          FROM saas_artists a
          CROSS JOIN LATERAL (
              SELECT COUNT(*) AS plateformes FROM (
{_livraisons_cte(window_days)}
              ) AS s
          ) AS l
         WHERE {HUMAN_TENANTS}
           AND l.plateformes < {int(ACTIVATION_MIN_PLATFORMS)}
         ORDER BY a.created_at
    """
