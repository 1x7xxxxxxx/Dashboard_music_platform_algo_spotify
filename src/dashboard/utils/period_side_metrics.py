"""Les métriques de période qui ne sont PAS des écoutes — en UN aller-retour.

Type: Sub
Uses: platform_timeseries._q
Depends on: v_meta_daily, v_meta_campaign_daily, v_hypeddit_daily, gold_apple_lifetime,
            instagram_daily_stats, ml_song_predictions, track_platform_link
Persists in: nothing

Pourquoi ce module existe
-------------------------
`platform_timeseries.py` a franchi 1 200 lignes le 2026-09-13 en gagnant Shazam puis
Hypeddit, et le cliquet `tests/test_a_file_only_gets_shorter.py` a refusé — « les
ajouter à FROZEN fige la dette ; les découper la retire ».

**La couture était déjà écrite dans le docstring du module d'origine.** Celui-ci
parle d'ÉCOUTES et de la distinction entre une quantité du jour et un compteur
cumulé ; cette fonction-ci dit d'elle-même qu'elle porte « les métriques de période
qui ne sont PAS des écoutes ». Instagram compte des abonnés, Meta des euros, Hypeddit
un taux de clic, Shazam un relevé de dépôt, le ML des probabilités : aucune n'entre
dans `platform_totals`, qui refuse par contrat d'additionner deux formes.

Ce qui ne change pas, et c'est l'essentiel
------------------------------------------
**UNE seule requête, et c'est une contrainte, pas une élégance.** L'accueil est à 13
allers-retours pour un plafond de 13 (`test_a_page_asks_the_same_question_once`), et
ce plafond ne monte pas. Chaque métrique ajoutée depuis le 2026-09-12 — le meilleur
CPR, les trois portes de la dernière sortie, les deux chiffres Shazam, le taux
Hypeddit — est entrée comme une CTE ou une sous-requête scalaire de CETTE requête.
Découper le fichier ne découpe pas la requête.

⚠️ `_q` EST IMPORTÉE, PAS RECOPIÉE. Elle lit `platform_timeseries._FETCH`, le crochet
de cache posé par le processus : une copie locale regarderait un autre global et
perdrait le cache sans que rien ne le signale. L'import est à sens unique — le module
d'origine n'importe pas celui-ci, donc aucun cycle.
"""
from __future__ import annotations

import logging

from src.dashboard.utils.platform_timeseries import _q

logger = logging.getLogger(__name__)


def period_side_metrics(db, artist_id, since=None, until=None) -> dict:
    """Les métriques de période qui ne sont PAS des écoutes, en UN aller-retour.

    Instagram compte des abonnés, Meta Ads des euros : ni l'un ni l'autre n'entre
    dans `platform_totals`, qui ne parle que d'écoutes et refuse par contrat
    d'additionner deux formes. Ils ont pourtant leur place dans le récapitulatif de
    l'accueil — demandé le 2026-09-12 — à condition d'y porter leur unité.

    **BORNÉES À LA PÉRIODE, comme tout ce tableau.** C'est la leçon du 2026-09-10 :
    les tuiles avaient été retirées parce qu'elles affichaient des compteurs DEPUIS
    LE DÉBUT à côté d'une courbe bornée, et qu'aucune prose ne rattrape deux nombres
    qui ne répondent pas à la même question. Instagram rend donc un ÉCART d'abonnés
    (`dernier − premier` sur la fenêtre), pas un effectif ; Meta rend la dépense de
    la fenêtre, pas celle du compte.

    **UNE SEULE REQUÊTE, et c'est une contrainte, pas une élégance.** L'accueil est
    à 13 allers-retours pour un plafond de 13 (`test_a_page_asks_the_same_question_once`),
    et ce plafond ne monte pas. Cette fonction REMPLACE l'appel à
    `get_instagram_followers` : son `last` porte le même effectif courant, donc la
    page gagne deux métriques sans gagner une requête.

    **DEUX MÉTRIQUES DE PLUS le 2026-09-12, et toujours UN aller-retour.** Le
    meilleur CPR de la période et la plus haute probabilité de déclenchement sont
    demandés pour le récapitulatif ; le plafond de la page est atteint, donc elles
    entrent comme des CTE de CETTE requête et non comme deux appels. C'est la
    contrainte qui a dicté la forme, pas l'inverse.

    ⚠️ `best_algo_p` est une **probabilité PRÉDITE**, jamais un taux observé. Le taux
    observé demanderait `s4a_song_algo_outcomes`, qui porte **0 ligne** (mesuré le
    2026-09-12, tous locataires confondus) : personne n'a jamais saisi l'issue d'une
    prédiction. Rendre une prédiction sous le nom « taux de déclenchement » serait
    l'inventer — la surface qui l'affiche DOIT dire qu'elle prédit.

    Rend `None` par métrique quand rien n'a été mesuré — jamais `0`, qui affirmerait
    qu'il ne s'est rien passé.
    """
    if db is None or artist_id is None:
        return {}
    try:
        rows = _q(db, """
            WITH best_cpr AS (
                -- ── LA CAMPAGNE DE LA DERNIÈRE SORTIE, PAS LA MEILLEURE DE TOUS
                --    LES TEMPS ──────────────────────────────────────────────────
                --
                -- « met en automatique la dernière release et pas forcément les
                -- meilleurs résultats qu'on a obtenu toute campagne confondue »
                -- (2026-09-12). Le `ORDER BY cpr ASC` d'avant rendait le RECORD
                -- historique : un excellent coût obtenu il y a deux ans sur une
                -- audience qui n'existe plus ne dit rien de ce qui marche
                -- aujourd'hui, et il est irréfutable — on ne peut pas faire mieux
                -- qu'un record, donc la métrique ne bouge jamais.
                --
                -- ⚠️ LA CAMPAGNE LA PLUS RÉCENTE, ET NON UNE CORRESPONDANCE DE NOM
                -- avec le titre de la sortie. Mesuré le 2026-09-12 sur l'artiste 1 :
                -- la dernière sortie est « Ô Chiotte l'arbitre Tucome Back -
                -- Original » et sa campagne « O chiotte l'arbitre Tucome Back » —
                -- accent, casse et suffixe diffèrent tous les trois. Un
                -- rapprochement flou qui se trompe de campagne en SILENCE est pire
                -- qu'une règle simple que l'artiste peut vérifier d'un coup d'œil :
                -- le nom de la campagne retenue est affiché avec le chiffre.
                SELECT campaign_name, spend, spend / results AS cpr
                  FROM (SELECT campaign_name, SUM(spend) AS spend,
                               SUM(results) AS results, MAX(day) AS last_day
                          FROM v_meta_campaign_daily
                         WHERE artist_id = %s
                           AND (%s::date IS NULL OR day >= %s)
                           AND (%s::date IS NULL OR day <= %s)
                         GROUP BY campaign_name
                        HAVING SUM(results) > 0 AND SUM(spend) > 0) q
                 ORDER BY last_day DESC
                 LIMIT 1
            ), last_release AS (
                -- ── LA DERNIÈRE SORTIE, SANS JOINTURE ET SANS DATE ──────────────
                --
                -- `track_release_reference.release_date` est NULL pour deux titres
                -- sur trois de l'artiste 1 (mesuré le 2026-09-12) : s'y fier
                -- écarterait justement les sorties les plus récentes, celles que
                -- personne n'a encore rapprochées d'une référence. `days_since_release`
                -- vit dans la prédiction elle-même et est renseigné partout.
                --
                -- La dernière sortie est donc le titre au plus PETIT âge, sur la
                -- prédiction la plus RÉCENTE. Les deux critères comptent : sans le
                -- second on lirait un classement figé d'une ancienne exécution du
                -- modèle.
                SELECT song, days_since_release,
                       COALESCE(dw_probability, 0)    AS dw,
                       COALESCE(rr_probability, 0)    AS rr,
                       COALESCE(radio_probability, 0) AS radio
                  FROM ml_song_predictions
                 WHERE artist_id = %s
                   AND prediction_date = (
                        SELECT MAX(prediction_date) FROM ml_song_predictions
                         WHERE artist_id = %s)
                   AND days_since_release IS NOT NULL
                 ORDER BY days_since_release ASC
                 LIMIT 1
            ), best_algo AS (
                -- PROBABILITÉ PRÉDITE, pas taux observé : voir le docstring.
                SELECT song, prediction_date,
                       GREATEST(COALESCE(dw_probability, 0),
                                COALESCE(rr_probability, 0),
                                COALESCE(radio_probability, 0))  AS p,
                       CASE WHEN COALESCE(radio_probability, 0)
                                 >= GREATEST(COALESCE(dw_probability, 0),
                                             COALESCE(rr_probability, 0))
                            THEN 'Radio'
                            WHEN COALESCE(dw_probability, 0)
                                 >= COALESCE(rr_probability, 0)
                            THEN 'Discover Weekly'
                            ELSE 'Release Radar' END              AS algo
                  FROM ml_song_predictions
                 WHERE artist_id = %s
                   AND (%s::date IS NULL OR prediction_date >= %s)
                   AND (%s::date IS NULL OR prediction_date <= %s)
                   AND GREATEST(COALESCE(dw_probability, 0),
                                COALESCE(rr_probability, 0),
                                COALESCE(radio_probability, 0)) > 0
                 ORDER BY p DESC
                 LIMIT 1
            ), apple_song AS (
                -- ── LE TITRE APPLE DE LA DERNIÈRE SORTIE, PAR LE LIEN CONFIRMÉ ──
                --
                -- Shazam vit dans `apple_songs_performance.song_name`, la dernière
                -- sortie dans `ml_song_predictions.song` : deux titres LIBRES qui ne
                -- coïncident pas. Mesuré en production le 2026-09-13, artiste 1 :
                --
                --   sortie (S4A)  « Ô Chiotte l'arbitre Tucome Back - Original »
                --   titre Apple   « Ô Chiotte l'arbitre Tucome Back »
                --   égalité exacte des deux → **0 ligne**
                --
                -- Le suffixe «  - Original » suffit à tout faire rater. C'est le
                -- rapprochement humain de `track_platform_link` qui tient, et lui
                -- seul : 11 liens `apple`/`confirmed` existent pour ce locataire.
                --
                -- ⚠️ AUCUN RAPPROCHEMENT FLOU. C'est la règle que ce dépôt s'est
                -- donnée pour les campagnes Meta le 2026-09-12, et pour la même
                -- raison : un rapprochement approximatif qui se trompe de titre en
                -- SILENCE est pire qu'un chiffre absent, que l'artiste peut voir.
                SELECT l.platform_title
                  FROM track_platform_link l
                  JOIN track_release_reference trr
                    ON trr.artist_id = l.artist_id
                   AND trr.match_key = l.match_key
                 WHERE l.artist_id = %s
                   AND l.platform = 'apple'
                   AND l.status = 'confirmed'
                   AND trr.title = (SELECT song FROM last_release)
                 LIMIT 1
            ), hypeddit_release AS (
                -- ── LE MEILLEUR TAUX DE CLIC DE LA DERNIÈRE SORTIE ─────────────
                --
                -- « intègre le meilleur rapport visits/click dans la page d'accueil
                -- pour hypeddit obtenue pour la dernière release » (2026-09-13).
                -- Hypeddit est dans le cœur du produit (ADR-025) et n'avait AUCUNE
                -- occurrence sur l'accueil.
                --
                -- ⚠️ AUCUN SIGNE POUR CENT DANS CE COMMENTAIRE, ET CE N'EST PAS
                -- une coquetterie : psycopg2 interpole ce signe dans TOUTE la
                -- chaîne, commentaires SQL compris. En écrire un seul ici a fait
                -- échouer la requête entière sur `IndexError: tuple index out of
                -- range`, avec 35 emplacements pour 35 paramètres — le compte était
                -- juste, le signe de trop était dans la PROSE. Le doubler, ou dire
                -- « pour cent » en toutes lettres.
                --
                -- Je l'ai écrit DEUX FOIS : la première dans le commentaire du
                -- ratio, la seconde dans ce paragraphe même, en décrivant le
                -- défaut. D'où la formulation ci-dessus, qui n'en contient aucun.
                --
                -- ⚠️ LE RATIO EST CELUI DES SOMMES, PAS LA MOYENNE DES RATIOS. Ces
                -- deux nombres diffèrent dès que les jours n'ont pas le même volume,
                -- et c'est le premier qui répond à « quel taux ce lien a-t-il
                -- obtenu ».
                --
                -- ⚠️ ET SURTOUT PAS LA COLONNE `ctr` DE LA TABLE, bien qu'elle
                -- existe : son déclencheur (`calculate_hypeddit_metrics`) écrit
                -- **0** quand `visits = 0`. Un jour non mesuré y est donc
                -- indiscernable d'un jour à zéro clic — un zéro inventé, la classe
                -- que cette couche existe pour tenir. `NULLIF` rend NULL, et le
                -- `HAVING` écarte les campagnes sans la moindre visite.
                --
                -- LE RAPPROCHEMENT PASSE PAR LE LIEN CONFIRMÉ, jamais par le nom :
                -- la sortie est « Ô Chiotte l'arbitre Tucome Back - Original » et la
                -- campagne « Ô Chiotte l'arbitre tucome back » — casse et suffixe
                -- diffèrent. Mesuré le 2026-09-13, 6 liens `hypeddit`/`confirmed`.
                --
                -- « MEILLEUR » SE JOUE ENTRE CAMPAGNES, PAS ENTRE JOURS. Un jour à
                -- trois visites et un clic afficherait 33 pour cent, et choisir un plancher
                -- de visites serait inventer un seuil. Mesuré : la seule campagne
                -- multi-jours du parc porte UN jour mesuré et dix jours à zéro.
                SELECT h.campaign_name,
                       SUM(h.visits) AS visits, SUM(h.clicks) AS clicks,
                       SUM(h.clicks)::numeric
                           / NULLIF(SUM(h.visits), 0) * 100 AS ctr
                  FROM v_hypeddit_daily h
                  JOIN track_platform_link l
                    ON l.artist_id = h.artist_id
                   AND l.platform = 'hypeddit'
                   AND l.status = 'confirmed'
                   AND l.platform_title = h.campaign_name
                  JOIN track_release_reference trr
                    ON trr.artist_id = l.artist_id
                   AND trr.match_key = l.match_key
                 WHERE h.artist_id = %s
                   AND trr.title = (SELECT song FROM last_release)
                 GROUP BY h.campaign_name
                HAVING SUM(h.visits) > 0
                 ORDER BY ctr DESC
                 LIMIT 1
            )
            SELECT
              -- ── LE NIVEAU D'ABONNÉS, DEPUIS LA COUCHE OR (migration 121) ──
              --
              -- Ces deux valeurs venaient de QUATRE sous-requêtes imbriquées sur
              -- `instagram_daily_stats`, et elles portaient deux règles que rien ne
              -- nommait : le niveau d'un JOUR est le MAX de ce jour (le collecteur
              -- peut relever plusieurs fois, et un niveau ne s'additionne pas), et
              -- le GAIN d'une période est le dernier jour MESURÉ moins le premier —
              -- jamais « aujourd'hui moins il y a 30 jours », qui suppose une mesure
              -- ces jours-là. Écrites dans une sous-requête, elles étaient invisibles
              -- à tout garde et se seraient recopiées à la surface suivante.
              --
              -- `DISTINCT ON` plutôt que le MIN/MAX imbriqué : une seule passe, et
              -- le premier/dernier JOUR MESURÉ de la fenêtre se lit directement.
              (SELECT followers FROM v_instagram_followers_daily
                 WHERE artist_id = %s AND (%s::date IS NULL OR day >= %s)
                   AND (%s::date IS NULL OR day <= %s)
                 ORDER BY day ASC LIMIT 1)                                    AS ig_first,
              (SELECT followers FROM v_instagram_followers_daily
                 WHERE artist_id = %s AND (%s::date IS NULL OR day >= %s)
                   AND (%s::date IS NULL OR day <= %s)
                 ORDER BY day DESC LIMIT 1)                                   AS ig_last,
              (SELECT SUM(spend) FROM v_meta_daily
                 WHERE artist_id = %s AND (%s::date IS NULL OR day >= %s)
                   AND (%s::date IS NULL OR day <= %s))                       AS spend,
              (SELECT cpr FROM best_cpr)                            AS best_cpr,
              (SELECT campaign_name FROM best_cpr)                  AS best_cpr_name,
              (SELECT spend FROM best_cpr)                          AS best_cpr_spend,
              (SELECT p FROM best_algo)                             AS best_algo_p,
              (SELECT algo FROM best_algo)                          AS best_algo_name,
              (SELECT song FROM best_algo)                          AS best_algo_song,
              (SELECT song FROM last_release)                       AS release_song,
              (SELECT days_since_release FROM last_release)         AS release_age,
              (SELECT dw FROM last_release)                         AS release_dw,
              (SELECT rr FROM last_release)                         AS release_rr,
              (SELECT radio FROM last_release)                      AS release_radio,
              -- ── SHAZAM : LE CATALOGUE, PUIS LA DERNIÈRE SORTIE ──────────────
              --
              -- ADR-025 met Shazam dans le cœur du produit ; il n'était sur aucun
              -- écran. Les deux chiffres entrent ICI et non dans un appel à part,
              -- parce que l'accueil est à 13 allers-retours pour un plafond de 13
              -- (`test_a_page_asks_the_same_question_once`) et que ce plafond ne
              -- monte pas. La règle elle-même n'est pas recopiée : c'est la
              -- fonction or de la migration 114, la même qui sert le total Apple.
              gold_apple_lifetime(%s, 'shazam_count')               AS shazam_total,
              -- ⚠️ LE `CASE` N'EST PAS DÉCORATIF. `p_song = NULL` veut dire « tout
              -- le catalogue » pour la fonction or : sans cette porte, un locataire
              -- SANS aucune prédiction verrait son total de catalogue s'afficher
              -- sous le libellé « dernière sortie ». Une absence deviendrait une
              -- autre mesure — la classe `absence-rendered-as-a-measurement`, sur
              -- une surface neuve. Pas de `ELSE` : le `CASE` rend NULL.
              CASE WHEN EXISTS (SELECT 1 FROM last_release)
                   THEN gold_apple_lifetime(%s, 'shazam_count',
                            COALESCE((SELECT platform_title FROM apple_song),
                                     (SELECT song FROM last_release)))
                   END                                              AS shazam_release,
              -- ── HYPEDDIT : LE TAUX, ET LES DEUX NOMBRES QUI LE FONT ─────────
              -- Un ratio sans son dénominateur ne se vérifie pas : un taux plein sur
              -- deux visites et 46 pour cent sur 7 828 se ressemblent dans une
              -- tuile. Les trois
              -- voyagent ensemble.
              (SELECT ctr FROM hypeddit_release)           AS hypeddit_ctr,
              (SELECT visits FROM hypeddit_release)        AS hypeddit_visits,
              (SELECT clicks FROM hypeddit_release)        AS hypeddit_clicks,
              (SELECT campaign_name FROM hypeddit_release) AS hypeddit_campaign,
              -- ── CE QUI EST SORTI, ET CE QUI EST RENTRE ──────────────────────
              --
              -- Deux sommes simples sur la vue or du flux de tresorerie. Non
              -- bornees a la periode, comme Shazam et Hypeddit ci-dessus, et pour
              -- la meme raison : ces vues n'ont que l'annee et le mois. Les borner
              -- a des DATES elargirait ou retrecirait la fenetre sans le dire.
              -- L'infobulle l'annonce, exactement comme les deux autres.
              --
              -- LA VUE OR, JAMAIS LA TABLE. Une somme de
              -- `sacem_statement.mouvement_eur` rend ZERO : c'est un grand livre ou
              -- un versement est un mouvement NEGATIF, et la repartition reelle est
              -- ailleurs. Le defaut a ete paye le 2026-09-14 (21,49 affiches a un
              -- artiste qui avait recu 36,49) et je l'ai reproduit en mesurant, le
              -- 2026-09-22, avant d'ecrire cette ligne.
              --
              -- `direction` n'est PAS applique : on veut deux totaux separes, pas
              -- un solde. Le solde est le point mort, il se calcule ailleurs.
              (SELECT SUM(amount_eur) FROM v_artist_monthly_cashflow
                 WHERE artist_id = %s AND flux = 'depense')  AS cash_sorti,
              (SELECT SUM(amount_eur) FROM v_artist_monthly_cashflow
                 WHERE artist_id = %s AND flux = 'revenu')   AS cash_rentre,
              -- ── LES TROIS AXES DE LA PUBLICITE, EN JSON ────────────────────
              --
              -- On remonte les LIGNES, pas un verdict : le classement vit dans
              -- `utils/meta_axes.py`, un module pur qui s'eprouve sur des valeurs.
              -- Le faire en SQL le rendrait intestable et le dupliquerait du cote
              -- du CPR Optimizer, qui pose la meme question autrement.
              --
              -- `json_agg` parce qu'une sous-requete scalaire ne rend qu'UNE valeur,
              -- et qu'on en veut N. Cout : trois sous-requetes dans la meme
              -- instruction, donc ZERO aller-retour de plus. L'accueil est a son
              -- plafond.
              --
              -- ⚠️ AUCUN plancher de fiabilite ici. Il vit dans `meta_axes`, avec la
              -- raison qui le justifie et le garde qui l'eprouve. L'ecrire aussi en
              -- SQL en ferait deux, et deux seuils divergent.
              (SELECT json_agg(x) FROM (
                 SELECT age_range AS v, SUM(spend) AS d, SUM(results) AS r
                   FROM meta_insights_performance_age
                  WHERE artist_id = %s AND age_range IS NOT NULL
                  GROUP BY 1) x)                             AS axe_age,
              (SELECT json_agg(x) FROM (
                 SELECT country AS v, SUM(spend) AS d, SUM(results) AS r
                   FROM meta_insights_performance_country
                  WHERE artist_id = %s AND country IS NOT NULL
                  GROUP BY 1) x)                             AS axe_pays,
              (SELECT json_agg(x) FROM (
                 SELECT platform || ' / ' || placement AS v,
                        SUM(spend) AS d, SUM(results) AS r
                   FROM meta_insights_performance_placement
                  WHERE artist_id = %s AND placement IS NOT NULL
                  GROUP BY 1) x)                             AS axe_placement
        """, (artist_id, since, since, until, until,     # best_cpr
              artist_id, artist_id,                       # apple_song, last_release
              artist_id, since, since, until, until,      # hypeddit_release
              artist_id, artist_id,                       # best_algo
              # ig_first / ig_last : 5 paramètres chacun depuis la migration 121
              # (ils en demandaient 8 et 6 quand la règle vivait en sous-requêtes).
              artist_id, since, since, until, until,      # ig_first
              artist_id, since, since, until, until,      # ig_last
              artist_id, since, since, until, until,      # spend
              artist_id, artist_id,                       # shazam
              artist_id, artist_id,                       # cash sorti / rentré
              artist_id, artist_id, artist_id))           # axes age / pays / placement
    except Exception as e:      # noqa: BLE001 — le récapitulatif se rend sans ces lignes
        logger.warning("side metrics unreadable: %s", type(e).__name__)
        return {}
    if not rows:
        return {}
    (ig_first, ig_last, spend, best_cpr, best_cpr_name, best_cpr_spend,
     best_algo_p, best_algo_name, best_algo_song,
     release_song, release_age, release_dw, release_rr, release_radio,
     shazam_total, shazam_release,
     hypeddit_ctr, hypeddit_visits, hypeddit_clicks, hypeddit_campaign,
     cash_sorti, cash_rentre, axe_age, axe_pays, axe_placement) = rows[0]
    return {
        "ig_followers": ig_last,
        "ig_delta": (None if ig_first is None or ig_last is None
                     else int(ig_last) - int(ig_first)),
        "meta_spend": float(spend) if spend is not None else None,
        "best_cpr": float(best_cpr) if best_cpr is not None else None,
        "best_cpr_name": best_cpr_name,
        "best_cpr_spend": (float(best_cpr_spend)
                           if best_cpr_spend is not None else None),
        # `best_algo_p` est une PRÉDICTION. Le nom de la clé le dit, et la surface
        # qui l'affiche doit le dire aussi — voir le docstring.
        "best_algo_p": float(best_algo_p) if best_algo_p is not None else None,
        "best_algo_name": best_algo_name,
        "best_algo_song": best_algo_song,
        # LA DERNIÈRE SORTIE ET SES TROIS PROBABILITÉS — chacune séparément, jamais
        # leur maximum. « la meilleure probabilité pour la dernière release de
        # trigger : DW Radio et RR : 3 kpi » (2026-09-12) : trois portes distinctes,
        # trois chiffres. Le `GREATEST` d'`best_algo` répond à une autre question —
        # quel titre du catalogue est le mieux placé — et il la garde.
        "release_song": release_song,
        "release_age": int(release_age) if release_age is not None else None,
        "release_dw": float(release_dw) if release_dw else None,
        "release_rr": float(release_rr) if release_rr else None,
        "release_radio": float(release_radio) if release_radio else None,
        # SHAZAM — un RELEVÉ de dépôt, pas une quantité datée : ces deux nombres ne
        # se découpent pas par période, exactement comme la tuile Apple. La surface
        # qui les affiche doit le dire.
        #
        # `is not None` ET NON une vérité booléenne : un titre qui existe chez Apple
        # avec **zéro** Shazam est un fait mesuré, et `if shazam_total` le
        # transformerait en « jamais mesuré ». C'est la distinction que la fonction
        # or tient en rendant NULL, et qu'un `or` de confort effacerait juste après.
        "shazam_total": int(shazam_total) if shazam_total is not None else None,
        "shazam_release": (int(shazam_release)
                           if shazam_release is not None else None),
        # HYPEDDIT — le taux de clic de la dernière sortie, et son volume. NON BORNÉ
        # par le filtre, et c'est délibéré : la question est « qu'a obtenu CETTE
        # sortie », pas « qu'a-t-elle obtenu ces trente jours ». Bornée, la tuile
        # serait vide presque toujours — la campagne de l'artiste 1 date du
        # 2024-08-30. La surface qui l'affiche doit dire qu'elle ne suit pas le
        # filtre.
        "hypeddit_ctr": (float(hypeddit_ctr)
                         if hypeddit_ctr is not None else None),
        "hypeddit_visits": (int(hypeddit_visits)
                            if hypeddit_visits is not None else None),
        "hypeddit_clicks": (int(hypeddit_clicks)
                            if hypeddit_clicks is not None else None),
        "hypeddit_campaign": hypeddit_campaign,
        # ⚠️ `None` ET NON `0` quand rien n'est déposé. Un artiste qui n'a jamais
        # importé de relevé de distributeur lirait « 0 € rentré » comme une
        # faillite, là où il n'y a qu'un fichier manquant. C'est la règle « une
        # tuile ne montre jamais un zéro qu'elle n'a pas mesuré », transposée à
        # l'euro — et l'appelant renvoie alors vers la carte d'absence.
        "cash_sorti": float(cash_sorti) if cash_sorti is not None else None,
        "cash_rentre": float(cash_rentre) if cash_rentre is not None else None,
        # Les lignes BRUTES des trois axes. Le classement, le plancher de fiabilité
        # et le refus de conclure vivent dans `utils/meta_axes.py` — ici on ne fait
        # que transporter.
        "axes": {"age": axe_age or [], "pays": axe_pays or [],
                 "placement": axe_placement or []},
    }
