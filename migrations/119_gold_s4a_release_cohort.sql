-- ═══════════════════════════════════════════════════════════════════════════
-- 119 — Les sorties recalées sur J+0, et le rattachement qui perdait 59 %
-- ═══════════════════════════════════════════════════════════════════════════
-- LE DÉFAUT QUE CETTE VUE FERME
-- ------------------------------
-- `track_release_reference.title` porte le « ? » du vrai titre ; `s4a_song_timeline
-- .song` porte un « _ », parce que le nom du morceau ne figure PAS dans le CSV —
-- Spotify ne le met que dans le NOM DU FICHIER, et un système de fichiers ne peut
-- pas porter « ? ». Mesuré le 2026-09-14 sur le locataire 1 :
--
--     jointure par `title`      →  6 titres sur 11,  67 402 streams sur 163 088 (41 %)
--     jointure par la clé canon → 11 titres sur 11, 163 088 streams          (100 %)
--
-- Le titre perdu le plus gros est « Ca te dérange pas si je joue avec ton tapis? »,
-- **59 926 streams** — plus du double du suivant. « Qui a bu le crachoir du saloon ? »,
-- sur lequel 1 370 € de Meta ont été dépensés, disparaissait aussi.
--
-- Le rattachement passe donc par `track_platform_link` (`platform='s4a'`,
-- `status='confirmed'`), dont `platform_title` porte le nom S4A EXACT — jointure
-- stricte, aucune normalisation à l'exécution, aucun rapprochement flou. C'est la
-- règle que le dépôt s'est donnée pour les campagnes Meta (migration 116) et pour
-- Shazam, et elle vaut ici à l'identique. Un `status='rejected'` est une décision
-- explicite de NE PAS rattacher : il ne compte pas.
--
-- CONSÉQUENCE ASSUMÉE : un titre sans lien confirmé sort de la comparaison des
-- sorties. La surface doit le COMPTER et le NOMMER, avec le chemin pour le
-- rattacher — une exclusion muette serait le défaut qu'on vient de corriger, dans
-- l'autre sens.
--
-- POURQUOI LE CUMUL EST LÉGITIME ICI
-- -----------------------------------
-- S4A est une QUANTITÉ quotidienne, pas un compteur : le cumsum reconstruit un vrai
-- total, contrairement à YouTube et SoundCloud où il fabriquerait une histoire
-- (classe `cumulative-counter-drawn-as-its-own-history`, ×870 et ×306 mesurés).
-- Mais l'import étant épisodique, il ne vaut que sur une suite ININTERROMPUE :
-- `v_s4a_release_reach.contiguous_days` la mesure. Reprendre le cumul après un trou
-- dessinerait un palier qui n'a pas eu lieu et sous-estimerait tout ce qui suit.
--
-- Mesuré le 2026-09-14 : les 11 sorties démarrent à J+0 et sont contiguës sur
-- 647 à 1 018 jours — aucun trou aujourd'hui. Le mécanisme est là pour la suite.
--
-- LES 4 ÉCOUTES DE LA VEILLE, ET POURQUOI ELLES SE COMPTENT AU LIEU DE TOMBER
-- ---------------------------------------------------------------------------
-- `day >= release_date` ancre la cohorte sur J+0, et écarte donc ce qui précède.
-- Mesuré : **4 écoutes sur 3 titres**, toutes la VEILLE de la sortie —
-- `kimono a semelle de fer` (1), `qui a sali mon slip avec de la gadoue` (1),
-- `qui a bu le crachoir du saloon` (2). Ce n'est pas une anomalie : Spotify publie
-- à minuit dans le fuseau le plus en avance, et le rapport date dans un autre. La
-- roadmap porte déjà ce chantier — « Spotify et Apple datent dans LEUR fuseau ».
--
-- 4 écoutes sur 163 088 ne changent aucune décision. Mais les laisser tomber en
-- SILENCE est la forme qui se paie : le jour où une sortie mondiale en portera des
-- milliers, rien ne le dirait. `v_s4a_release_reach.pre_release_streams` les compte
-- donc, pour que la surface puisse les nommer plutôt que les perdre.

CREATE OR REPLACE VIEW v_s4a_release_cohort AS
    -- MATERIALIZED, et c'est mesuré : inlinée, cette CTE laisse le planificateur
    -- appliquer le filtre `trr.match_key = l.match_key` APRÈS avoir joint les 13 794
    -- lignes quotidiennes — 142 399 lignes produites puis jetées. Matérialisée, les
    -- 11 lignes de correspondance sont calculées une fois et hachées contre le fait.
    WITH linked AS MATERIALIZED (
        SELECT l.artist_id,
               l.match_key,
               l.platform_title AS song,
               trr.title,
               trr.release_date
          FROM track_platform_link l
          JOIN track_release_reference trr
            ON trr.artist_id = l.artist_id
           AND trr.match_key = l.match_key
         WHERE l.platform = 's4a'
           AND l.status   = 'confirmed'
           AND trr.release_date IS NOT NULL
    )
    SELECT d.artist_id,
           k.match_key,
           k.title,
           k.release_date,
           d.day,
           (d.day - k.release_date)::int AS day_index,
           d.streams,
           SUM(d.streams) OVER (PARTITION BY d.artist_id, k.match_key
                                ORDER BY d.day
                                ROWS UNBOUNDED PRECEDING)::bigint AS streams_cumulative
      FROM v_s4a_song_daily d
      JOIN linked k
        ON k.artist_id = d.artist_id
       AND k.song      = d.song
     WHERE d.day >= k.release_date;

COMMENT ON VIEW v_s4a_release_cohort IS
    'Couche OR (ADR-019) : les écoutes d''une sortie recalées sur J+0, au grain '
    '(locataire, sortie canonique, jour). Le rattachement passe par le LIEN CONFIRMÉ '
    'de track_platform_link, JAMAIS par le nom : joindre par titre perdait 5 sorties '
    'sur 11 et 59 % des écoutes, dont le plus gros titre du catalogue. Le cumul est '
    'calculé ici — S4A est une quantité quotidienne, donc le cumsum est légitime, '
    'contrairement à un compteur (YouTube, SoundCloud).';

-- ── L'HORIZON COMPARABLE, pour que la surface ne l'invente pas ──────────────────
--
-- UNE SEULE PASSE DE FENÊTRE, ET C'EST UNE CORRECTION MESURÉE.
-- La première version détectait les trous par « îlots » (day_index − ROW_NUMBER),
-- ce qui obligeait à référencer la CTE DEUX fois — une pour les îlots, une pour
-- l'agrégat — puis à les auto-joindre. Le planificateur estime **1 ligne** là où la
-- cohorte en rend 9 335 (le filtre de jointure `match_key` + `day >= release_date`
-- lui est opaque), choisit donc une boucle imbriquée, et réexécute tout le sous-plan
-- une fois par ligne : la vue dépassait 2 minutes quand la cohorte seule tourne en
-- 51 ms. Mesuré par EXPLAIN ANALYZE, pas deviné.
--
-- `LAG` répond à la même question en une passe : la suite se rompt au premier jour
-- dont le précédent n'est pas `day_index - 1`. Aucune auto-jointure, aucune double
-- référence, donc aucune prise pour une mauvaise estimation.
CREATE OR REPLACE VIEW v_s4a_release_reach AS
    WITH d AS (
        SELECT artist_id, match_key, title, release_date, day_index, day,
               LAG(day_index) OVER (PARTITION BY artist_id, match_key
                                    ORDER BY day_index) AS prev_index
          FROM v_s4a_release_cohort
    ), pre_release AS (
        -- UNE agrégation par sortie, jamais une par ligne.
        SELECT l.artist_id, l.match_key, SUM(dd.streams)::bigint AS streams
          FROM v_s4a_song_daily dd
          JOIN track_platform_link l
            ON l.artist_id = dd.artist_id AND l.platform = 's4a'
           AND l.status = 'confirmed'     AND l.platform_title = dd.song
          JOIN track_release_reference trr
            ON trr.artist_id = l.artist_id AND trr.match_key = l.match_key
         WHERE dd.day < trr.release_date
           AND dd.streams > 0
         GROUP BY l.artist_id, l.match_key
    ), agg AS (
        SELECT artist_id, match_key, title, release_date,
               MIN(day_index)::int AS first_index,
               MAX(day_index)::int AS last_day_index,
               COUNT(*)::int       AS days_measured,
               MAX(day)            AS last_measured,
               -- Le premier jour où la suite se rompt, ou NULL si elle ne se rompt pas.
               MIN(day_index) FILTER (
                   WHERE prev_index IS NOT NULL AND day_index <> prev_index + 1
               )::int AS first_gap_at
          FROM d
         GROUP BY artist_id, match_key, title, release_date
    )
    SELECT a.artist_id, a.match_key, a.title, a.release_date,
           a.first_index, a.last_day_index, a.days_measured, a.last_measured,
           -- LA SEULE LONGUEUR SUR LAQUELLE DEUX SORTIES SE COMPARENT : la suite
           -- ininterrompue de jours mesurés qui part de la sortie. Comparer 40 jours
           -- à 120 est la « comparaison qui n'a pas de sens » de Few, *Information
           -- Dashboard Design* p. 142 §7.1.5 — et elle est d'autant plus tentante que
           -- les deux courbes s'affichent côte à côte sans rien dire.
           (COALESCE(a.first_gap_at, a.last_day_index + 1) - a.first_index)::int
               AS contiguous_days,
           -- Ce que l'ancrage sur J+0 écarte, compté plutôt que perdu (voir en-tête).
           COALESCE(pre.streams, 0)::bigint AS pre_release_streams
      FROM agg a
      LEFT JOIN pre_release pre
             ON pre.artist_id = a.artist_id AND pre.match_key = a.match_key;

COMMENT ON VIEW v_s4a_release_reach IS
    'Couche OR (ADR-019) : jusqu''où chaque sortie est comparable. contiguous_days '
    'est la suite ININTERROMPUE de jours mesurés depuis J+0 — la seule longueur sur '
    'laquelle deux sorties se comparent (Few p.142 §7.1.5). first_index > 0 signale '
    'une sortie dont la mesure ne commence PAS au jour de sortie : elle s''exclut, '
    'elle ne se trace pas décalée. pre_release_streams compte ce que l''ancrage sur '
    'J+0 écarte — 4 écoutes de veille de sortie chez le locataire 1, artefact de '
    'fuseau de publication — pour qu''aucune écoute ne tombe en silence.';
