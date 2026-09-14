-- ═══════════════════════════════════════════════════════════════════════════
-- 117 — L'audience Spotify : 889 jours collectés que rien n'affichait
-- ═══════════════════════════════════════════════════════════════════════════
-- `s4a_audience` porte 889 jours continus (2024-01-01 → 2026-06-07) de `listeners`,
-- `streams`, `followers`, `saves` et `playlist_adds`. `listeners` et `followers` n'y
-- sont vides AUCUN jour sur 889. Aucune vue Streamlit ne lisait cette table — seuls
-- le PDF et l'export CSV. L'artiste voyait ses auditeurs dans le PDF exporté et
-- jamais à l'écran.
--
-- Le chiffre que cette donnée porte, mesuré le 2026-09-14 sur le locataire 1 :
--
--     2024 : 113 494 écoutes / 48 955 auditeurs-jour = 2,32
--     2025 :  18 751 écoutes / 15 454 auditeurs-jour = 1,21
--     2026 :   4 575 écoutes /  4 016 auditeurs-jour = 1,14
--
-- Un auditeur écoutait 2,3 fois ; il écoute 1,14 fois. Il passe et ne revient pas.
-- C'est la métrique la plus décisive du jeu de données et elle n'était nulle part.
--
-- ⚠️ DEUX COLONNES « streams » QUI NE PEUVENT PAS S'ACCORDER
-- ---------------------------------------------------------
-- `v_s4a_song_daily` couvre 1 254 jours ; `s4a_audience.streams` en couvre 889. Ce
-- ne sont PAS deux calculs d'une même métrique, ce sont deux PÉRIMÈTRES issus de
-- deux exports S4A différents (la timeline par titre, et le rapport d'audience).
-- Conséquence non négociable : le ratio se calcule avec `s4a_audience.streams` au
-- numérateur — même ligne, même CSV, même jour que son dénominateur — et JAMAIS en
-- croisant les deux tables. Le total canonique du produit reste `v_s4a_song_daily`
-- (branche `spotify` de `v_platform_totals`). On nomme les deux périmètres au lieu
-- d'additionner l'un dans l'autre.
--
-- L'ABSENCE EST L'ABSENCE DE LIGNE
-- --------------------------------
-- Aucune génération de dates, aucun `COALESCE(…, 0)`. Un jour sans import n'est pas
-- un jour à zéro écoute. C'est la classe `an-unmeasured-platform-is-rendered-as-zero`,
-- déjà payée deux fois ici.

CREATE OR REPLACE VIEW v_s4a_audience_daily AS
    SELECT artist_id,
           date                  AS day,
           listeners::bigint     AS listeners,
           streams::bigint       AS streams,
           saves::bigint         AS saves,
           playlist_adds::bigint AS playlist_adds,
           -- ⚠️ UN NIVEAU, PAS UN FLUX. `followers` ne se somme jamais : c'est un
           -- stock au jour dit. Le nom porte la règle pour que personne n'ait à se
           -- souvenir de la lire ici.
           followers::bigint     AS followers_level
      FROM s4a_audience
     WHERE artist_id IS NOT NULL
       AND date IS NOT NULL;

COMMENT ON VIEW v_s4a_audience_daily IS
    'Couche OR (ADR-019) : l''audience Spotify du CSV S4A au grain (locataire, jour). '
    'PÉRIMÈTRE — ce n''est PAS la même mesure que v_s4a_song_daily : 889 jours ici, '
    '1 254 là, deux exports S4A différents. Ne JAMAIS croiser les deux colonnes '
    '« streams » dans un même nombre. followers_level est un NIVEAU : MAX, jamais SUM.';

-- ── Le grain MOIS, et c'est ICI que vit le ratio — nulle part ailleurs ──────────
CREATE OR REPLACE VIEW v_s4a_audience_monthly AS
    WITH m AS (
        SELECT artist_id,
               date_trunc('month', day)::date AS month,
               SUM(streams)::bigint           AS streams,
               SUM(listeners)::bigint         AS listener_days,
               SUM(saves)::bigint             AS saves,
               SUM(playlist_adds)::bigint     AS playlist_adds,
               MAX(followers_level)::bigint   AS followers_end,
               COUNT(*)::int                  AS days_measured,
               MIN(day)                       AS first_day,
               MAX(day)                       AS last_day
          FROM v_s4a_audience_daily
         GROUP BY artist_id, date_trunc('month', day)
    )
    SELECT m.artist_id, m.month, m.streams, m.listener_days, m.saves,
           m.playlist_adds, m.followers_end, m.days_measured, m.first_day, m.last_day,
           -- ⚠️ LE NOM DIT CE QUE LA MESURE EST.
           -- `listeners` compte les auditeurs UNIQUES PAR JOUR. Les sommer compte
           -- une fois par jour celui qui revient : le dénominateur est donc un
           -- nombre d'AUDITEURS-JOUR, pas de personnes. Appeler ce ratio « écoutes
           -- par auditeur » serait exact au calcul et faux au sens — c'est le
           -- « deficient measure » de Few, *Information Dashboard Design* p. 46
           -- §3.4 : exact ne veut pas dire juste.
           (m.streams::numeric / NULLIF(m.listener_days, 0))
               AS streams_per_listener_day,
           -- Le delta vit ICI. Une tuile qui soustrait deux nombres en pandas est
           -- invisible à tout garde SQL — c'est la forme qui a fait afficher le
           -- double à la tuile « Dépenses » de Meta Ads.
           LAG(m.streams::numeric / NULLIF(m.listener_days, 0))
               OVER (PARTITION BY m.artist_id ORDER BY m.month)
               AS streams_per_listener_day_prev,
           -- Un mois partiel ne se compare pas à un mois plein, et la surface n'a
           -- pas à redécouvrir la longueur d'un mois pour le savoir.
           (m.days_measured = EXTRACT(DAY FROM (m.month + INTERVAL '1 month'
                                                - INTERVAL '1 day'))::int)
               AS is_complete
      FROM m;

COMMENT ON VIEW v_s4a_audience_monthly IS
    'Couche OR (ADR-019) : l''audience Spotify au grain (locataire, mois), avec le '
    'ratio streams_per_listener_day et son delta (LAG) calculés ICI. Le dénominateur '
    'est un nombre d''AUDITEURS-JOUR — listeners est un compte d''uniques PAR JOUR, '
    'donc le sommer compte une fois par jour celui qui revient. is_complete distingue '
    'un mois plein d''un mois partiel : ils ne se comparent pas.';
