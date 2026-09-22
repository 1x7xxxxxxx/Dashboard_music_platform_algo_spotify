"""Les définitions de la couche or qui DOIVENT coïncider, et la preuve qu'elles coïncident.

Type: Utility
Uses: nothing (stdlib only — importable sans Airflow, comme value_monitor)
Triggers: alert_monitor.check_gold_invariants, tests/test_the_gold_layer_agrees_with_itself.py
Depends on: les vues or (migrations 097, 101-111)
Persists in: nothing

Le trou que ce module ferme
---------------------------
ADR-019 garantit qu'une métrique a **une seule définition**. Elle ne garantit pas que
deux définitions *censées* coïncider coïncident — et c'est une propriété différente,
qu'il faut vérifier sur les DONNÉES, pas sur le code.

Mesuré le 2026-09-12 : `meta_insights_performance` et `meta_insights_performance_day`
répondent à la même question et divergeaient d'un **facteur deux** (6 165,65 € contre
3 087,82 € pour l'artiste 1, en production, depuis des semaines). Le code était
cohérent de chaque côté ; aucun test ne comparait les deux côtés.

Ce que `check_metric_bounds` couvre déjà, et ce qu'il ne couvre pas
-------------------------------------------------------------------
`src/utils/metric_bounds.py` réconcilie déjà deux PORTES Python
(`platform_totals` contre `daily_streams_by_platform`) pour **trois** plateformes —
`KINDS = {spotify, soundcloud, youtube}`. Il ne regarde ni Apple, ni Meta, ni le
revenu, et surtout il compare des portes, pas des VUES : une vue or qui diverge de sa
vue sœur lui est invisible.

Depuis les migrations 101-111 il y a **quatorze vues or et une fonction**. Les
définitions derrière trois d'entre elles sont réconciliées. Ce module couvre les
autres.

Pourquoi une ÉGALITÉ et pas un seuil
-------------------------------------
Chaque paire ci-dessous est la même somme, des mêmes lignes, par deux chemins. Un
écart n'est pas « une dérive à surveiller » : c'est une erreur, aujourd'hui, dans un
chiffre affiché. La tolérance ne couvre donc que la représentation flottante —
Moses/Gavish/Vorwerck, *Data Quality Fundamentals* p. 107, distinguent explicitement
le suivi d'une distribution (un seuil) de l'assertion (une égalité) ; ce sont des
assertions.

Ce que ce module ne fait PAS
-----------------------------
Il ne détecte pas une dérive graduelle, ni une valeur aberrante, ni un changement de
distribution. Ces trois-là relèvent du pilier « distribution » et ont leurs propres
détecteurs (`value_monitor` pour le retour à zéro d'un cumul, `check_row_dips` pour le
volume). Ici on ne pose qu'une question : **ces deux chemins rendent-ils le même
nombre ?**
"""
from __future__ import annotations

from dataclasses import dataclass

# La représentation flottante, rien de plus. Un écart relatif masquerait le défaut :
# le double, sur une base à un euro près, est un écart relatif de 100 % — mais sur un
# locataire à 3 €, un facteur deux fait 3 € et passerait sous n'importe quel seuil
# relatif « raisonnable ». C'est la raison pour laquelle ce n'est pas un seuil.
TOLERANCE = 1e-6


@dataclass(frozen=True)
class Invariant:
    name: str
    left_sql: str
    right_sql: str
    left_label: str
    right_label: str
    why: str


# Chaque invariant rend (artist_id, valeur). La comparaison est par locataire : un
# total de flotte qui s'équilibre peut cacher deux locataires qui se compensent.
INVARIANTS: tuple[Invariant, ...] = (
    Invariant(
        name="meta_spend_two_grains",
        left_sql="SELECT artist_id, SUM(spend) FROM v_meta_daily GROUP BY 1",
        right_sql="SELECT artist_id, SUM(spend) FROM v_meta_campaign_daily GROUP BY 1",
        left_label="v_meta_daily",
        right_label="v_meta_campaign_daily",
        why="LE défaut du 2026-09-12. Les deux vues lisent deux tables différentes "
            "qui portent la même dépense ; l'une d'elles contenait 21 lignes de cumul "
            "à vie d'un ancien collecteur, et la page affichait le double. La vue or "
            "les écarte — cet invariant est ce qui le prouve chaque nuit.",
    ),
    Invariant(
        name="meta_spend_creative_vs_adset",
        left_sql="SELECT artist_id, SUM(spend) FROM v_meta_creative_daily GROUP BY 1",
        right_sql="SELECT artist_id, SUM(spend) FROM v_meta_adset_daily GROUP BY 1",
        left_label="v_meta_creative_daily",
        right_label="v_meta_adset_daily",
        why="La même dépense à deux mailles (créative, ad set), par deux chaînes de "
            "jointures distinctes. Un euro qui tombe d'un côté et pas de l'autre est "
            "une jointure qui a perdu une ligne — la classe que la migration 106 "
            "nomme et que la 108 a vue se reproduire.",
    ),
    Invariant(
        name="meta_spend_totals_vs_daily",
        left_sql="SELECT artist_id, SUM(spend) FROM v_meta_spend_totals GROUP BY 1",
        right_sql="SELECT artist_id, SUM(spend) FROM v_meta_daily GROUP BY 1",
        left_label="v_meta_spend_totals",
        right_label="v_meta_daily",
        why="Le TOTAL et son grain temporel, lus sur la même table de fait. "
            "`v_meta_spend_totals` n'avait aucun lecteur au 2026-09-12 ; un objet or "
            "que rien ne lit dérive sans bruit, et c'est le premier à le faire.",
    ),
    Invariant(
        name="spotify_total_vs_song_grain",
        left_sql="SELECT artist_id, SUM(total) FROM v_platform_totals "
                 "WHERE platform = 'spotify' GROUP BY 1",
        right_sql="SELECT artist_id, SUM(streams) FROM v_s4a_song_daily GROUP BY 1",
        left_label="v_platform_totals[spotify]",
        right_label="v_s4a_song_daily",
        why="Le total et le grain TITRE. Depuis la migration 107 le total DÉRIVE du "
            "grain, donc l'invariant est vrai par construction — et c'est exactement "
            "pour ça qu'il est ici : le jour où quelqu'un réécrit la branche spotify "
            "en repartant de la table brute, cette égalité casse avant l'affichage.",
    ),
    Invariant(
        name="soundcloud_total_vs_track_grain",
        left_sql="SELECT artist_id, SUM(total) FROM v_platform_totals "
                 "WHERE platform = 'soundcloud' GROUP BY 1",
        right_sql="SELECT artist_id, SUM(playback_count) FROM v_soundcloud_track_latest "
                  "GROUP BY 1",
        left_label="v_platform_totals[soundcloud]",
        right_label="v_soundcloud_track_latest",
        why="Idem pour un COMPTEUR : le total est la somme du dernier relevé de chaque "
            "titre. La version d'avant le 2026-09-12 dédupliquait sans le locataire, "
            "et deux artistes partageant un titre n'en gardaient qu'un.",
    ),
    Invariant(
        name="sacem_revenue_vs_statement_grain",
        left_sql="SELECT artist_id, SUM(revenue_eur) FROM v_artist_monthly_revenue "
                 "WHERE source = 'sacem' GROUP BY 1",
        right_sql="SELECT artist_id, SUM(amount) FROM v_sacem_monthly "
                  "WHERE line_type = 'repartition' GROUP BY 1",
        left_label="v_artist_monthly_revenue[sacem]",
        right_label="v_sacem_monthly[repartition]",
        why="Le prédicat `line_type = 'repartition'` était écrit DEUX fois avant la "
            "migration 111 — dans la vue de revenu et dans la page SACEM, qui sommait "
            "en pandas. Il n'est plus écrit qu'une fois ; cet invariant garde qu'il le "
            "reste.",
    ),
    Invariant(
        name="revenue_net_gross_vs_revenue_view",
        left_sql="SELECT artist_id, SUM(gross_eur) FROM v_artist_monthly_revenue_net "
                 "GROUP BY 1",
        right_sql="SELECT artist_id, SUM(revenue_eur) FROM v_artist_monthly_revenue "
                  "GROUP BY 1",
        left_label="v_artist_monthly_revenue_net[gross]",
        right_label="v_artist_monthly_revenue",
        why="Le BRUT est désormais lisible par deux vues or : l'ancienne, que huit "
            "surfaces lisent, et la colonne `gross_eur` de la vue brut+net (migration "
            "115). Les deux doivent rendre le même nombre — sinon un artiste lit un "
            "brut sur la page revenu et un autre sur la page SACEM, ce qu'ADR-019 "
            "interdit. Le NET n'a pas d'invariant ici, et c'est délibéré : il n'égale "
            "la somme des virements qu'une fois tout distribué, donc l'égalité est "
            "FAUSSE entre deux trimestres. Un contrôle rouge en régime normal est la "
            "classe `a-check-that-can-never-pass`.",
    ),
    Invariant(
        name="meta_attribution_campaign_count_vs_campaign_grain",
        left_sql="SELECT artist_id, SUM(campaigns) FROM v_meta_track_attribution "
                 "GROUP BY 1",
        right_sql="SELECT artist_id, COUNT(DISTINCT campaign_name) "
                  "FROM v_meta_campaign_daily WHERE artist_id IS NOT NULL GROUP BY 1",
        left_label="v_meta_track_attribution[campaigns]",
        right_label="v_meta_campaign_daily",
        why="La vue d'attribution (migration 116) dit combien de campagnes ce "
            "locataire porte, et combien sont rattachées à un titre. Le premier des "
            "deux nombres est le MÊME que le compte de la vue au grain campagne : "
            "s'ils divergent, l'encart de la page Meta annonce une population que "
            "les graphes d'à côté ne dessinent pas. Le second nombre — les "
            "rattachées — n'a pas de sœur à confronter, et c'est le point : il "
            "vaut zéro sur tout le parc, et ne pourra être réconcilié que le jour "
            "où une campagne sera étiquetée.",
    ),
    # ── Les six vues Spotify de la refonte du 2026-09-14 ────────────────────────
    Invariant(
        name="s4a_audience_day_vs_month",
        left_sql="SELECT artist_id, SUM(streams) FROM v_s4a_audience_daily GROUP BY 1",
        right_sql="SELECT artist_id, SUM(streams) FROM v_s4a_audience_monthly GROUP BY 1",
        left_label="v_s4a_audience_daily",
        right_label="v_s4a_audience_monthly",
        why="Le grain mois n''est qu''un regroupement du grain jour. L''égalité est "
            "vraie par construction — et c''est pour ça qu''elle est ici : le jour où "
            "quelqu''un ajoute un prédicat au mois sans le mettre au jour, les deux "
            "surfaces qui les lisent annonceront deux nombres.".replace("''", "'"),
    ),
    Invariant(
        name="s4a_span_vs_song_grain",
        left_sql="SELECT artist_id, SUM(streams_total) FROM v_s4a_song_measured_span "
                 "GROUP BY 1",
        right_sql="SELECT artist_id, SUM(streams) FROM v_s4a_song_daily GROUP BY 1",
        left_label="v_s4a_song_measured_span",
        right_label="v_s4a_song_daily",
        why="L'horloge par titre porte aussi le total du titre : il doit être celui "
            "du grain dont elle dérive. Sans cette égalité, le bandeau de la page "
            "pourrait classer les titres autrement que la figure d'à côté.",
    ),
    Invariant(
        name="s4a_release_cohort_loses_nothing",
        left_sql="SELECT artist_id, SUM(streams) FROM v_s4a_release_cohort GROUP BY 1",
        right_sql="SELECT s.artist_id, SUM(s.streams_total) - COALESCE(MAX(p.pre), 0) "
                  "FROM v_s4a_song_measured_span s "
                  "LEFT JOIN (SELECT artist_id, SUM(pre_release_streams) AS pre "
                  "             FROM v_s4a_release_reach GROUP BY 1) p "
                  "       ON p.artist_id = s.artist_id "
                  "WHERE EXISTS (SELECT 1 FROM track_platform_link l "
                  "               WHERE l.artist_id = s.artist_id AND l.platform = 's4a' "
                  "                 AND l.status = 'confirmed' AND l.platform_title = s.song) "
                  "GROUP BY s.artist_id",
        left_label="v_s4a_release_cohort",
        right_label="span[titres liés] − pre_release",
        why="LE plus utile des six. La cohorte ancre sur J+0, donc elle ÉCARTE ce qui "
            "précède la sortie — 4 écoutes de veille chez le locataire 1, artefact de "
            "fuseau de publication. Cette égalité dit que rien d'autre ne tombe : "
            "163 084 tracés + 4 comptés = 163 088. Le jour où un rattachement casse, "
            "elle rougit avant l'écran — et c'est exactement le défaut qui perdait "
            "59 % des écoutes avant le 2026-09-14.",
    ),
    Invariant(
        name="s4a_reach_vs_cohort_days",
        left_sql="SELECT artist_id, SUM(days_measured) FROM v_s4a_release_reach GROUP BY 1",
        right_sql="SELECT artist_id, COUNT(*) FROM v_s4a_release_cohort GROUP BY 1",
        left_label="v_s4a_release_reach[days_measured]",
        right_label="v_s4a_release_cohort",
        why="L'horizon de comparaison compte les jours de la cohorte qu'il résume. "
            "Une divergence signifierait que la figure compare sur une longueur que "
            "la donnée ne porte pas — la comparaison sans objet de Few p.142 §7.1.5.",
    ),
    Invariant(
        name="spotify_followers_csv_branch",
        left_sql="SELECT artist_id, COUNT(*) FROM v_spotify_followers_daily "
                 "WHERE source = 's4a_csv' GROUP BY 1",
        right_sql="SELECT artist_id, COUNT(*) FROM v_s4a_audience_daily "
                  "WHERE followers_level IS NOT NULL AND followers_level > 0 GROUP BY 1",
        left_label="v_spotify_followers_daily[s4a_csv]",
        right_label="v_s4a_audience_daily",
        why="La branche CSV de la vue des abonnés EST la colonne followers du grain "
            "jour. Les deux prédicats sont écrits deux fois ; cet invariant garde "
            "qu'ils restent le même. La branche API n'a pas de sœur à confronter — "
            "c'est la seule source de son propre chiffre.",
    ),
    Invariant(
        name="instagram_followers_level_vs_raw",
        left_sql="SELECT artist_id, MAX(followers) FROM v_instagram_followers_daily "
                 "GROUP BY 1",
        right_sql="SELECT artist_id, MAX(followers_count) FROM instagram_daily_stats "
                  "WHERE artist_id IS NOT NULL GROUP BY 1",
        left_label="v_instagram_followers_daily",
        right_label="instagram_daily_stats",
        why="La vue (migration 121) ne fait que poser une règle — le niveau d'un JOUR "
            "est le MAX de ce jour — sans rien perdre ni inventer. Le maximum sur "
            "toute l'histoire doit donc être identique des deux côtés. Elle a retiré "
            "de la porte quatre sous-requêtes imbriquées qui portaient cette règle "
            "sans la nommer, et c'est la dernière lecture de bronze que R108 laissait "
            "derrière elle.",
    ),
    Invariant(
        name="apple_total_vs_function",
        left_sql="SELECT artist_id, SUM(total) FROM v_platform_totals "
                 "WHERE platform = 'apple' GROUP BY 1",
        right_sql="SELECT DISTINCT artist_id, gold_apple_lifetime(artist_id, 'plays') "
                  "FROM apple_songs_performance WHERE artist_id IS NOT NULL",
        left_label="v_platform_totals[apple]",
        right_label="gold_apple_lifetime()",
        why="La seule règle en PL/pgSQL du dépôt (ADR-022) : sélection gloutonne "
            "d'intervalles non chevauchants. Une fonction procédurale ne se relit pas "
            "en diff ; cet invariant est la seule façon de savoir qu'elle rend encore "
            "ce que la vue annonce. Son ajout en surcharge avait déjà fait afficher "
            "**zéro** à la tuile « Total Streams ».",
    ),
    # ── Les quatre suivants confrontent une vue or à CE QU'ELLE RÉSUME ─────────
    #
    # Ils sont d'une autre nature que les sept ci-dessus : ceux-là comparent deux
    # définitions or entre elles, ceux-ci comparent une vue or à la table qu'elle
    # agrège. C'est un invariant plus faible — il ne dit rien de la RÈGLE, seulement
    # qu'aucune ligne ne s'est perdue en chemin. Mais « une jointure a perdu des
    # lignes » est la moitié des défauts de cette famille, et un objet or que rien
    # ne confronte est le premier à dériver en silence.
    Invariant(
        name="levels_vs_total_youtube",
        left_sql="SELECT DISTINCT ON (artist_id) artist_id, level FROM v_platform_levels "
                 "WHERE platform = 'youtube' ORDER BY artist_id, day DESC",
        right_sql="SELECT artist_id, SUM(total) FROM v_platform_totals "
                  "WHERE platform = 'youtube' GROUP BY 1",
        left_label="v_platform_levels[youtube] au dernier jour",
        right_label="v_platform_totals[youtube]",
        why="Le meilleur des onze : deux calculs VRAIMENT différents du même "
            "compteur. Les niveaux reportent en avant le dernier relevé de chaque "
            "vidéo jour par jour ; le total prend le dernier relevé de chaque vidéo. "
            "Ils doivent finir au même nombre, et c'est la figure de l'accueil qui "
            "lit les premiers pendant que la tuile lit le second — les deux "
            "surfaces où ×2,7 avait été mesuré le 2026-09-10.",
    ),
    Invariant(
        name="levels_vs_total_soundcloud",
        left_sql="SELECT DISTINCT ON (artist_id) artist_id, level FROM v_platform_levels "
                 "WHERE platform = 'soundcloud' ORDER BY artist_id, day DESC",
        right_sql="SELECT artist_id, SUM(total) FROM v_platform_totals "
                  "WHERE platform = 'soundcloud' GROUP BY 1",
        left_label="v_platform_levels[soundcloud] au dernier jour",
        right_label="v_platform_totals[soundcloud]",
        why="Même propriété sur l'autre compteur. Elle vaut d'être vérifiée "
            "séparément : les niveaux filtrent `playback_count > 0` et non "
            "`IS NOT NULL`, parce qu'une collecte ratée écrit des ZÉROS — une "
            "distinction qui n'existe que d'un côté.",
    ),
    Invariant(
        name="hypeddit_view_loses_no_row",
        left_sql="SELECT artist_id, SUM(visits) FROM v_hypeddit_daily GROUP BY 1",
        right_sql="SELECT artist_id, SUM(visits) FROM hypeddit_daily_stats "
                  "WHERE artist_id IS NOT NULL GROUP BY 1",
        left_label="v_hypeddit_daily",
        right_label="hypeddit_daily_stats",
        why="La vue est un pur `GROUP BY` : elle ne doit RIEN perdre. Un écart veut "
            "dire qu'un prédicat s'est glissé dans la vue, ou que le `artist_id IS "
            "NOT NULL` écarte des lignes que la page affichait encore la veille.",
    ),
    Invariant(
        name="meta_active_budget_matches_its_filter",
        left_sql="SELECT artist_id, SUM(lifetime_budget) FROM v_meta_active_budget "
                 "GROUP BY 1",
        right_sql="SELECT artist_id, SUM(COALESCE(lifetime_budget, 0)) FROM meta_campaigns "
                  "WHERE artist_id IS NOT NULL AND status = 'ACTIVE' GROUP BY 1",
        left_label="v_meta_active_budget",
        right_label="meta_campaigns[status=ACTIVE]",
        why="Le prédicat `status = 'ACTIVE'` vivait recopié dans quatre branches de "
            "deux fichiers avant la migration 110. Il n'est plus écrit qu'une fois ; "
            "cet invariant garde qu'il dit encore la même chose que ce qu'il "
            "remplaçait — c'est la seule façon de savoir qu'un repointage n'a pas "
            "silencieusement changé le sens.",
    ),
    Invariant(
        name="instagram_view_loses_no_post_that_has_a_date",
        left_sql="SELECT artist_id, SUM(likes) FROM v_instagram_media_monthly GROUP BY 1",
        right_sql="SELECT artist_id, SUM(COALESCE(like_count, 0)) FROM instagram_media "
                  "WHERE artist_id IS NOT NULL AND timestamp IS NOT NULL GROUP BY 1",
        left_label="v_instagram_media_monthly",
        right_label="instagram_media[timestamp non nul]",
        why="⚠️ Le côté droit porte `timestamp IS NOT NULL` parce que la VUE le "
            "porte : un post sans date de publication est EXCLU du mensuel, et "
            "aligner l'invariant sur la vue est la seule façon qu'il ne sonne pas "
            "chaque fois qu'Instagram rend un post sans horodatage. C'est aussi une "
            "information sur le produit — ces posts-là ne sont comptés nulle part, "
            "et personne ne le dit à l'écran.",
    ),
    Invariant(
        name="pi_view_keeps_every_reading_of_a_linked_track",
        left_sql="SELECT artist_id, SUM(popularity) FROM v_spotify_track_pi_daily "
                 "GROUP BY 1",
        right_sql="SELECT p.artist_id, SUM(p.popularity) FROM track_popularity_history p "
                  "JOIN track_platform_link sp ON sp.artist_id = p.artist_id "
                  "AND sp.platform = 'spotify' AND sp.status = 'confirmed' "
                  "AND sp.platform_ref_id = p.track_id "
                  "JOIN track_platform_link s4a ON s4a.artist_id = sp.artist_id "
                  "AND s4a.match_key = sp.match_key AND s4a.platform = 's4a' "
                  "AND s4a.status = 'confirmed' GROUP BY 1",
        left_label="v_spotify_track_pi_daily",
        right_label="track_popularity_history[liens confirmés]",
        why="L'indice de popularité passe par DEUX liens — le lien Spotify, qui "
            "porte le `track_id`, et le lien S4A, qui porte le nom de fichier du "
            "CSV. Une jointure qui perd une jambe ne rend pas une erreur : elle "
            "change QUI entre, sans qu'aucune ligne ne soit fausse. ⚠️ Le côté "
            "droit est la définition que la vue applique, délibérément : "
            "l'invariant ne demande pas que tout relevé de popularité entre — un "
            "titre sans lien confirmé n'a pas à entrer, et c'est ce qui écarte la "
            "ligne `track_id='test_track_001'` (PI 50) qui faisait un pic ×5,6 "
            "dans le PDF client jusqu'au 2026-09-21. "
            "MUTATIONS JOUÉES LE 2026-09-21, y compris celles qui n'ont PAS mordu : "
            "retirer la jambe S4A de la vue → 1187 des deux côtés, VERT ; joindre "
            "par `platform_title = track_name` au lieu du `track_id` → 1187, VERT "
            "aussi (pour 'spotify' les deux champs coïncident aujourd'hui). Les "
            "deux sont muettes parce que sur cette base les 11 liens Spotify ont "
            "tous leur jumeau S4A. Il MORD dès que cet état cesse, et c'est un "
            "état ordinaire — un artiste qui rattache Spotify avant S4A : la "
            "jambe retirée rend alors **1237 contre 1187**, ROUGE, les 50 points "
            "de la ligne de test rentrant par la porte qu'on vient de fermer.",
    ),
    Invariant(
        name="apple_cumulative_keeps_both_sources",
        left_sql="SELECT artist_id, SUM(plays) FROM v_apple_song_cumulative GROUP BY 1",
        right_sql="SELECT artist_id, SUM(plays) FROM ("
                  "  SELECT DISTINCT ON (artist_id, song_name, day) artist_id, plays FROM ("
                  "    SELECT artist_id, song_name, snapshot_date AS day, plays::bigint, 0 AS p"
                  "      FROM apple_songs_performance WHERE snapshot_date IS NOT NULL"
                  "    UNION ALL"
                  "    SELECT artist_id, song_name, date, plays::bigint, 1"
                  "      FROM apple_songs_history WHERE date IS NOT NULL) z"
                  "  ORDER BY artist_id, song_name, day, p) y GROUP BY 1",
        left_label="v_apple_song_cumulative",
        right_label="apple_songs_performance union apple_songs_history",
        why="LE defaut du 2026-09-21, rapporte par l'artiste : « j'avais pourtant "
            "download les derniers csv » alors que la page disait « la derniere "
            "mesure remonte au 2025-12-11 ». Les deux avaient raison — ils "
            "parlaient de deux TABLES. L'import ecrit `apple_songs_performance` ; "
            "`apple_songs_history` n'est ecrite par rien depuis des mois, et trois "
            "surfaces la lisaient. La vue reunit les deux ; cet invariant garde "
            "qu'elle ne perd aucune des deux JAMBES. Retirer celle d'heritage fait "
            "tomber le total de 9 196 a 3 267 chez le locataire 1 — mesure.",
    ),
    Invariant(
        name="apple_gains_telescope_to_the_cumulative",
        left_sql="SELECT artist_id, SUM(daily_plays) FROM v_apple_song_daily GROUP BY 1",
        right_sql="SELECT artist_id, SUM(mx - mn) FROM ("
                  "  SELECT artist_id, song_name, MAX(plays) AS mx, MIN(plays) AS mn"
                  "    FROM v_apple_song_cumulative GROUP BY 1, 2) s GROUP BY 1",
        left_label="v_apple_song_daily[somme des gains]",
        right_label="v_apple_song_cumulative[dernier moins premier]",
        why="Une somme de differences successives doit valoir la difference des "
            "extremes — un telescopage, vrai par construction TANT QUE le `LAG` "
            "partitionne sur le bon titre et ordonne sur le bon jour. C'est "
            "exactement ce qui casse quand on ajoute une colonne a la partition ou "
            "qu'on change la source sous la fenetre, et ca ne leve pas : la figure "
            "dessine simplement des gains faux. Attention : il suppose les cumuls "
            "MONOTONES ; Apple corrige parfois ses chiffres a la baisse, et une "
            "correction ferait diverger cet invariant a juste titre — c'est un fait "
            "a connaitre, pas une derive a taire.",
    ),
    Invariant(
        name="soundcloud_catalog_equals_its_tracks",
        left_sql="SELECT artist_id, SUM(plays) FROM v_soundcloud_catalog_daily GROUP BY 1",
        right_sql="SELECT artist_id, SUM(plays) FROM v_soundcloud_track_daily GROUP BY 1",
        left_label="v_soundcloud_catalog_daily",
        right_label="v_soundcloud_track_daily",
        why="Le total du catalogue et la somme de ses titres, au meme grain de jour. "
            "Les deux vues derivent de la MEME sous-requete — le dernier releve de "
            "chaque titre dans la journee — donc l'egalite est vraie par "
            "construction, et c'est assume : elle garde qu'un futur remaniement ne "
            "fasse pas diverger les deux deduplications (317 horodatages pour "
            "19 jours, mesure). ATTENTION, MUTATION JOUEE ET MUETTE le 2026-09-21 : "
            "inverser le sens de la deduplication (premier releve du jour au lieu "
            "du dernier) rend 422 048 des deux cotes — sur cette base les valeurs "
            "d'un meme jour sont identiques. L'invariant ne mord donc PAS sur cette "
            "mutation-la ; il mord sur un titre perdu d'un seul cote.",
    ),
    Invariant(
        name="soundcloud_latest_is_the_last_readable_day",
        left_sql="SELECT artist_id, SUM(playback_count) FROM v_soundcloud_track_latest "
                 "GROUP BY 1",
        right_sql="SELECT DISTINCT ON (artist_id) artist_id, plays "
                  "FROM v_soundcloud_catalog_daily WHERE lisible "
                  "ORDER BY artist_id, day DESC",
        left_label="v_soundcloud_track_latest[total]",
        right_label="v_soundcloud_catalog_daily[dernier jour lisible]",
        why="LE defaut du 2026-09-21, rapporte par l'artiste : « pourquoi il y a un "
            "bump le 1er juin ». Le 2026-06-01, les 19 titres etaient ecrits a ZERO "
            "— une collecte ratee persistee. MUTATION JOUEE, et elle a corrige ce "
            "que j'allais ecrire : en simulant une DERNIERE collecte ratee (19 "
            "lignes a zero, en transaction annulee), le cote GAUCHE tombe a **0** "
            "quand le dernier jour lisible vaut **23 486**. Ce n'est donc pas la "
            "courbe qui aurait menti, ce sont LES TUILES — "
            "`v_soundcloud_track_latest` ne porte aucun verdict de lisibilite. La "
            "page lit desormais le dernier jour LISIBLE ; cet invariant garde "
            "qu'elle continue.",
    ),
    Invariant(
        name="cashflow_revenue_vs_net_source",
        left_sql="SELECT artist_id, SUM(amount_eur) FROM v_artist_monthly_cashflow "
                 "WHERE flux = 'revenu' GROUP BY 1",
        right_sql="SELECT artist_id, SUM(net_eur) FROM v_artist_monthly_revenue_net "
                  "WHERE net_eur IS NOT NULL GROUP BY 1",
        left_label="v_artist_monthly_cashflow (revenus)",
        right_label="v_artist_monthly_revenue_net",
        why="Le côté REVENU de la trésorerie et sa source. Le défaut que cet "
            "invariant attrape a été vu au navigateur le 2026-09-21, dans un seul "
            "écran : le tiroir affichait 43,06 € de SACEM sous une figure qui en "
            "dessinait 36,49 €. Les deux nombres étaient justes — l'un BRUT, "
            "l'autre NET de 6,57 € de charges et de TVA — et rien ne disait lequel "
            "on lisait. La page ne lit plus que le net ; cet invariant garde que la "
            "trésorerie n'en perde ni n'en invente une ligne."),
    Invariant(
        name="cashflow_meta_spend_vs_gold",
        left_sql="SELECT artist_id, SUM(amount_eur) FROM v_artist_monthly_cashflow "
                 "WHERE source = 'meta_ads' GROUP BY 1",
        right_sql="SELECT artist_id, SUM(spend) FROM v_meta_daily "
                  "GROUP BY 1 HAVING SUM(spend) > 0",
        left_label="v_artist_monthly_cashflow (meta_ads)",
        right_label="v_meta_daily",
        why="La dépense publicitaire est désormais une LIGNE de la trésorerie, et "
            "elle entre dans le point mort de l'artiste. Elle passe par une "
            "agrégation au mois qui lui est propre : un mois perdu par le "
            "regroupement ne ferait pas rougir la page, il avancerait la date du "
            "point mort — c'est-à-dire qu'il rendrait la réponse OPTIMISTE, la "
            "direction où l'on ne va pas vérifier."),
    Invariant(
        name="spread_costs_vs_raw_entries",
        left_sql="SELECT artist_id, SUM(amount_eur) FROM v_artist_monthly_costs "
                 "WHERE amount_eur > 0 GROUP BY 1",
        # ⚠️ L'AUTRE CÔTÉ NE DOIT PAS DESCENDRE DE LA MÊME VUE, et le premier jet
        # de cet invariant le faisait — il comparait `v_artist_monthly_cashflow`
        # (qui LIT `v_artist_monthly_costs`) à `v_artist_monthly_costs`. Testé le
        # 2026-09-21 en retirant un mois à `generate_series` : **zéro désaccord**.
        # Les deux côtés bougeaient ensemble, par construction. Un invariant qui
        # compare une vue à elle-même ne peut pas échouer.
        #
        # Ici le compte de mois est refait par ARITHMÉTIQUE sur les bornes, sans
        # `generate_series` : c'est une seconde dérivation, et une erreur de
        # bornes dans la vue la fait rougir.
        right_sql="""
            SELECT artist_id, SUM(
                CASE billing_period
                    WHEN 'one_off' THEN amount_eur
                    WHEN 'monthly' THEN amount_eur * n_mois
                    WHEN 'yearly'  THEN ROUND(amount_eur / 12.0, 2) * n_mois
                END)
            FROM (
                SELECT artist_id, amount_eur, billing_period,
                       GREATEST(1, (
                           (EXTRACT(YEAR FROM LEAST(
                                COALESCE(date_trunc('month', end_month)::date,
                                         date_trunc('month', CURRENT_DATE)::date),
                                date_trunc('month', CURRENT_DATE)::date)) * 12
                            + EXTRACT(MONTH FROM LEAST(
                                COALESCE(date_trunc('month', end_month)::date,
                                         date_trunc('month', CURRENT_DATE)::date),
                                date_trunc('month', CURRENT_DATE)::date)))
                           - (EXTRACT(YEAR FROM date_trunc('month', start_month)) * 12
                              + EXTRACT(MONTH FROM date_trunc('month', start_month)))
                           + 1)::int) AS n_mois
                FROM artist_cost_entries
                WHERE amount_eur > 0
            ) c GROUP BY artist_id""",
        left_label="v_artist_monthly_costs (étalement)",
        right_label="artist_cost_entries (arithmétique des bornes)",
        why="L'étalement des coûts saisis, et le même compte refait SANS "
            "`generate_series`. Un abonnement annuel est divisé par douze et "
            "répété tant qu'il est actif ; un `one_off` tombe sur son seul mois. "
            "Une erreur de bornes répéterait un coût ou en perdrait un sans rien "
            "casser : le point mort bougerait, et ce serait tout ce qu'on verrait. "
            "⚠️ Le premier jet de cet invariant comparait la trésorerie à la vue "
            "d'étalement — deux côtés qui DESCENDENT l'un de l'autre. Muté le "
            "2026-09-21 en retirant un mois à la série : zéro désaccord."),
)


def compare(left: dict[int, float], right: dict[int, float],
            tolerance: float = TOLERANCE) -> list[tuple[int, float, float]]:
    """Les locataires où les deux côtés diffèrent : (locataire, gauche, droite).

    Un locataire absent d'UN SEUL côté compte comme un désaccord — c'est la moitié
    des défauts de cette famille : une jointure qui perd des lignes fait disparaître
    un locataire entier, et comparer les seules clés communes rendrait ça invisible.
    `None` des deux côtés n'existe pas ici : un côté absent vaut zéro, et zéro contre
    un nombre est un désaccord.
    """
    out: list[tuple[int, float, float]] = []
    for tenant in sorted(set(left) | set(right)):
        a = float(left.get(tenant) or 0.0)
        b = float(right.get(tenant) or 0.0)
        if abs(a - b) > tolerance:
            out.append((tenant, a, b))
    return out


def finding(inv: Invariant, tenant: int, left: float, right: float) -> str:
    """Le constat, dans la forme que l'e-mail consolidé sait rendre."""
    gap = abs(left - right)
    ratio = f" (×{max(left, right) / min(left, right):.2f})" if min(left, right) else ""
    return (f"artiste {tenant} — {inv.name} : {inv.left_label} = {left:,.2f} mais "
            f"{inv.right_label} = {right:,.2f}, écart {gap:,.2f}{ratio}. {inv.why}")


def run(db) -> tuple[list[str], int]:
    """`(constats, couples comparés)` — le contrôle entier, hors d'Airflow.

    Il vit ICI et pas dans le DAG pour deux raisons. La première est un cliquet :
    `alert_monitor.py` ne grandit pas, et ce qui y entre doit en faire sortir
    autant. La seconde est la bonne : un contrôle enfermé dans un DAG n'est
    testable que par Airflow, et ce dépôt a mesuré que **aucun DAG n'était
    importable hors conteneur** — un prédicat qu'on ne peut pas lancer est un
    prédicat qu'on n'exerce pas.

    Le second membre du tuple n'est pas décoratif : « zéro désaccord » sur zéro
    couple comparé est vrai et ne dit rien. L'appelant doit pouvoir le journaliser.
    """
    findings: list[str] = []
    compared = 0

    def side(sql: str) -> dict[int, float]:
        rows = db.fetch_query(sql) or []
        return {int(t): float(v or 0) for t, v in rows if t is not None}

    for inv in INVARIANTS:
        left, right = side(inv.left_sql), side(inv.right_sql)
        compared += len(set(left) | set(right))
        findings += [finding(inv, t, a, b) for t, a, b in compare(left, right)]
    return findings, compared


def email_section(findings: list[str], escape) -> str:
    """Le bloc HTML du courriel consolidé, ou une chaîne vide.

    `escape` est injecté plutôt qu'importé : ce module ne dépend de rien, et c'est
    ce qui le rend importable depuis un test, un DAG et un script.
    """
    if not findings:
        return ""
    items = "".join(f"<li>{escape(m)}</li>" for m in findings)
    return f"""
        <h2 style="color:#c0392b;border-left:4px solid #c0392b;padding-left:10px">
          🧮 Définitions or en désaccord ({len(findings)})
        </h2>
        <p style="color:#888;font-size:0.9em">Deux définitions de la couche or qui
          doivent rendre le MÊME nombre n'en rendent pas le même. Ce n'est pas une
          dérive à surveiller : c'est un chiffre faux, aujourd'hui, sur une surface
          que quelqu'un lit. Chaque ligne nomme le défaut qu'elle attrape.</p>
        <ul style="font-size:0.9em">{items}</ul>"""
